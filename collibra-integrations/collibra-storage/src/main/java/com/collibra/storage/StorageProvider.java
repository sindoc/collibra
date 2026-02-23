package com.collibra.storage;

import com.collibra.storage.model.StorageObject;
import com.collibra.storage.model.StoragePath;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;

/**
 * SPI for reading data files used by Collibra integrations.
 *
 * <p>Implementations cover AWS S3 ({@link com.collibra.storage.s3.S3StorageProvider}),
 * Dropbox ({@link com.collibra.storage.dropbox.DropboxStorageProvider}), and local
 * filesystem ({@link com.collibra.storage.local.LocalStorageProvider}).
 *
 * <p>All paths use {@link StoragePath} to abstract away URI differences between
 * providers (s3://bucket/key vs /abs/path vs /dropbox/folder/file).
 */
public interface StorageProvider {

    /**
     * Returns the provider type identifier.
     * @return e.g. "S3", "DROPBOX", "LOCAL"
     */
    String getProviderType();

    /**
     * Lists all objects/files under the given path prefix.
     *
     * @param prefix the path prefix to list; use {@link StoragePath#ROOT} for the root
     * @return ordered list of {@link StorageObject} descriptors (no content loaded)
     */
    List<StorageObject> list(StoragePath prefix) throws IOException;

    /**
     * Opens an {@link InputStream} for the object at the given path.
     * Callers are responsible for closing the stream.
     *
     * @param path the full path to the object
     * @return a readable stream of the object's contents
     */
    InputStream open(StoragePath path) throws IOException;

    /**
     * Reads the full content of the object at {@code path} into a byte array.
     *
     * @param path the full path to the object
     * @return object contents as bytes
     */
    byte[] readBytes(StoragePath path) throws IOException;

    /**
     * Reads the full content of the object at {@code path} as a UTF-8 string.
     */
    default String readString(StoragePath path) throws IOException {
        return new String(readBytes(path), java.nio.charset.StandardCharsets.UTF_8);
    }

    /**
     * Returns {@code true} if an object exists at the given path.
     */
    boolean exists(StoragePath path) throws IOException;

    /**
     * Returns metadata for the object at the given path without loading content.
     */
    StorageObject stat(StoragePath path) throws IOException;

    /**
     * Closes any open connections / clients held by this provider.
     */
    void close() throws IOException;
}
