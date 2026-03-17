package com.collibra.storage.local;

import com.collibra.storage.StorageProvider;
import com.collibra.storage.model.StorageObject;
import com.collibra.storage.model.StoragePath;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

/**
 * {@link StorageProvider} backed by the local filesystem.
 *
 * <h2>Configuration</h2>
 * <pre>
 *   // Use an absolute root directory:
 *   LocalStorageProvider provider = LocalStorageProvider.rooted("/data/collibra");
 *
 *   // Or use the process working directory as root:
 *   LocalStorageProvider provider = LocalStorageProvider.workingDirectory();
 * </pre>
 *
 * <h2>Usage</h2>
 * <pre>
 *   // List all .xlsx files under /data/collibra/imports:
 *   provider.list(StoragePath.of("imports"))
 *
 *   // Read a specific file:
 *   byte[] bytes = provider.readBytes(StoragePath.of("imports/glossary.xlsx"));
 * </pre>
 *
 * <p>Paths in {@link StoragePath} are resolved relative to the configured root
 * directory.  Absolute paths (starting with "/") are also accepted but must
 * remain inside the root (path-traversal is rejected).
 */
public class LocalStorageProvider implements StorageProvider {

    private static final Logger log = LoggerFactory.getLogger(LocalStorageProvider.class);

    private final Path root;

    private LocalStorageProvider(Path root) {
        this.root = root.toAbsolutePath().normalize();
        log.info("LocalStorageProvider root: {}", this.root);
    }

    public static LocalStorageProvider rooted(String rootPath) {
        return new LocalStorageProvider(Path.of(rootPath));
    }

    public static LocalStorageProvider workingDirectory() {
        return new LocalStorageProvider(Path.of(""));
    }

    @Override public String getProviderType() { return "LOCAL"; }

    @Override
    public List<StorageObject> list(StoragePath prefix) throws IOException {
        Path dir = resolve(prefix);
        List<StorageObject> results = new ArrayList<>();

        if (!Files.exists(dir)) {
            log.warn("LocalStorageProvider: directory does not exist: {}", dir);
            return results;
        }

        try (Stream<Path> stream = Files.walk(dir)) {
            stream.sorted(Comparator.naturalOrder()).forEach(p -> {
                try {
                    results.add(toStorageObject(p));
                } catch (IOException e) {
                    log.warn("Could not stat {}: {}", p, e.getMessage());
                }
            });
        }

        log.debug("Local list '{}' returned {} objects", prefix, results.size());
        return results;
    }

    @Override
    public InputStream open(StoragePath path) throws IOException {
        Path file = resolve(path);
        checkSafe(file);
        log.debug("Opening local file: {}", file);
        return Files.newInputStream(file, StandardOpenOption.READ);
    }

    @Override
    public byte[] readBytes(StoragePath path) throws IOException {
        Path file = resolve(path);
        checkSafe(file);
        return Files.readAllBytes(file);
    }

    @Override
    public boolean exists(StoragePath path) throws IOException {
        return Files.exists(resolve(path));
    }

    @Override
    public StorageObject stat(StoragePath path) throws IOException {
        return toStorageObject(resolve(path));
    }

    @Override
    public void close() {
        // No resources to release for local filesystem
        log.debug("LocalStorageProvider closed");
    }

    // ------------------------------------------------------------------

    private Path resolve(StoragePath path) {
        String key = path.getKey();
        if (key.isBlank()) return root;
        // Strip leading s3:// / dropbox: prefixes if present
        if (key.startsWith("/")) key = key.substring(1);
        return root.resolve(key).normalize();
    }

    /**
     * Prevents path-traversal attacks by ensuring the resolved path
     * stays within the configured root directory.
     */
    private void checkSafe(Path resolved) throws IOException {
        if (!resolved.startsWith(root)) {
            throw new IOException("Path traversal rejected: '" + resolved +
                    "' is outside root '" + root + "'");
        }
    }

    private StorageObject toStorageObject(Path p) throws IOException {
        BasicFileAttributes attrs = Files.readAttributes(p, BasicFileAttributes.class);
        StoragePath sp = StoragePath.of(p.toString());
        return StorageObject.builder(sp)
                .sizeBytes(attrs.isDirectory() ? 0 : attrs.size())
                .lastModified(attrs.lastModifiedTime().toInstant())
                .isDirectory(attrs.isDirectory())
                .build();
    }
}
