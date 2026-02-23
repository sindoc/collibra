package com.collibra.storage.dropbox;

import com.collibra.storage.StorageProvider;
import com.collibra.storage.model.StorageObject;
import com.collibra.storage.model.StoragePath;
import com.dropbox.core.DbxException;
import com.dropbox.core.DbxRequestConfig;
import com.dropbox.core.v2.DbxClientV2;
import com.dropbox.core.v2.files.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * {@link StorageProvider} backed by Dropbox using the Dropbox Java SDK v5.
 *
 * <h2>Configuration</h2>
 * <pre>
 *   DropboxStorageProvider provider = DropboxStorageProvider.builder()
 *       .accessToken("sl.your-dropbox-access-token")
 *       .clientIdentifier("collibra-integration/1.0")
 *       .build();
 * </pre>
 *
 * <h2>Paths</h2>
 * Dropbox paths are relative to the app folder root and must start with "/":
 * <pre>
 *   provider.list(StoragePath.of("dropbox:/collibra/imports"))
 *   provider.readBytes(StoragePath.of("dropbox:/collibra/imports/glossary.xlsx"))
 * </pre>
 *
 * <h2>Permissions required</h2>
 * The Dropbox app needs at minimum {@code files.metadata.read} and
 * {@code files.content.read} scopes.
 */
public class DropboxStorageProvider implements StorageProvider {

    private static final Logger log = LoggerFactory.getLogger(DropboxStorageProvider.class);

    private final DbxClientV2 client;

    private DropboxStorageProvider(Builder b) {
        DbxRequestConfig config = DbxRequestConfig.newBuilder(b.clientIdentifier).build();
        this.client = new DbxClientV2(config, b.accessToken);
    }

    @Override public String getProviderType() { return "DROPBOX"; }

    @Override
    public List<StorageObject> list(StoragePath prefix) throws IOException {
        String folder = dropboxPath(prefix);
        List<StorageObject> results = new ArrayList<>();

        try {
            ListFolderResult result = client.files().listFolder(folder);
            while (true) {
                for (Metadata meta : result.getEntries()) {
                    results.add(toStorageObject(meta));
                }
                if (!result.getHasMore()) break;
                result = client.files().listFolderContinue(result.getCursor());
            }
        } catch (DbxException e) {
            throw new IOException("Dropbox list failed for '" + folder + "': " + e.getMessage(), e);
        }

        log.debug("Dropbox list '{}' returned {} objects", prefix, results.size());
        return results;
    }

    @Override
    public InputStream open(StoragePath path) throws IOException {
        try {
            return client.files().download(dropboxPath(path)).getInputStream();
        } catch (DbxException e) {
            throw new IOException("Dropbox download failed for '" + path + "': " + e.getMessage(), e);
        }
    }

    @Override
    public byte[] readBytes(StoragePath path) throws IOException {
        try (InputStream is = open(path);
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            is.transferTo(baos);
            return baos.toByteArray();
        }
    }

    @Override
    public boolean exists(StoragePath path) throws IOException {
        try {
            client.files().getMetadata(dropboxPath(path));
            return true;
        } catch (GetMetadataErrorException e) {
            if (e.errorValue.isPath() && e.errorValue.getPathValue().isNotFound()) return false;
            throw new IOException("Dropbox metadata check failed: " + e.getMessage(), e);
        } catch (DbxException e) {
            throw new IOException("Dropbox exists() failed for '" + path + "': " + e.getMessage(), e);
        }
    }

    @Override
    public StorageObject stat(StoragePath path) throws IOException {
        try {
            return toStorageObject(client.files().getMetadata(dropboxPath(path)));
        } catch (DbxException e) {
            throw new IOException("Dropbox stat failed for '" + path + "': " + e.getMessage(), e);
        }
    }

    @Override
    public void close() {
        // Dropbox SDK client does not hold persistent connections
        log.debug("DropboxStorageProvider closed");
    }

    // ------------------------------------------------------------------

    private static String dropboxPath(StoragePath path) {
        String key = path.getKey();
        // Dropbox paths must start with "/" or be "" (root)
        if (key.isBlank()) return "";
        return key.startsWith("/") ? key : "/" + key;
    }

    private static StorageObject toStorageObject(Metadata meta) {
        StoragePath path = StoragePath.of("dropbox:" + meta.getPathLower());
        StorageObject.Builder builder = StorageObject.builder(path);

        if (meta instanceof FileMetadata file) {
            builder.sizeBytes(file.getSize())
                   .lastModified(file.getServerModified().toInstant())
                   .etag(file.getRev())
                   .isDirectory(false);
        } else if (meta instanceof FolderMetadata) {
            builder.isDirectory(true).sizeBytes(0);
        }
        return builder.build();
    }

    // ------------------------------------------------------------------

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private String accessToken      = "";
        private String clientIdentifier = "collibra-dropbox-integration/1.0";

        public Builder accessToken(String token)           { this.accessToken      = token;  return this; }
        public Builder clientIdentifier(String identifier) { this.clientIdentifier = identifier; return this; }

        public DropboxStorageProvider build() {
            if (accessToken.isBlank()) throw new IllegalStateException("accessToken must not be blank");
            return new DropboxStorageProvider(this);
        }
    }
}
