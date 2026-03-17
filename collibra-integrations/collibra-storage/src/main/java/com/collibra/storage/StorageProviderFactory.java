package com.collibra.storage;

import com.collibra.storage.dropbox.DropboxStorageProvider;
import com.collibra.storage.local.LocalStorageProvider;
import com.collibra.storage.model.StoragePath;
import com.collibra.storage.s3.S3StorageProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

/**
 * Factory that creates the correct {@link StorageProvider} based on a URI hint
 * or an explicit configuration map.
 *
 * <h2>Auto-detection from URI</h2>
 * <pre>
 *   StorageProvider p = StorageProviderFactory.forPath(StoragePath.of("s3://my-bucket/key"));
 *   StorageProvider p = StorageProviderFactory.forPath(StoragePath.of("dropbox:/folder/file.xlsx"));
 *   StorageProvider p = StorageProviderFactory.forPath(StoragePath.of("/local/abs/path"));
 * </pre>
 *
 * <h2>Explicit config map</h2>
 * For S3 with credentials:
 * <pre>
 *   StorageProvider p = StorageProviderFactory.fromConfig(Map.of(
 *       "type",       "S3",
 *       "region",     "us-east-1",
 *       "accessKey",  "AKI...",
 *       "secretKey",  "..."
 *   ));
 * </pre>
 * For Dropbox:
 * <pre>
 *   StorageProvider p = StorageProviderFactory.fromConfig(Map.of(
 *       "type",        "DROPBOX",
 *       "accessToken", "sl...."
 *   ));
 * </pre>
 * For local:
 * <pre>
 *   StorageProvider p = StorageProviderFactory.fromConfig(Map.of(
 *       "type", "LOCAL",
 *       "root", "/data/collibra"
 *   ));
 * </pre>
 */
public final class StorageProviderFactory {

    private static final Logger log = LoggerFactory.getLogger(StorageProviderFactory.class);

    private StorageProviderFactory() {}

    /**
     * Creates a provider automatically based on the URI scheme in {@code path}.
     */
    public static StorageProvider forPath(StoragePath path) {
        return switch (path.getProviderHint()) {
            case S3      -> S3StorageProvider.builder().build();
            case DROPBOX -> throw new IllegalArgumentException(
                    "Dropbox requires an access token — use StorageProviderFactory.fromConfig() instead");
            case LOCAL, UNSPECIFIED -> LocalStorageProvider.workingDirectory();
        };
    }

    /**
     * Creates a provider from an explicit configuration map.
     *
     * @param config key/value configuration map (see class javadoc for keys)
     * @return the configured {@link StorageProvider}
     */
    public static StorageProvider fromConfig(Map<String, String> config) {
        String type = config.getOrDefault("type", "LOCAL").toUpperCase();
        log.info("Creating StorageProvider of type '{}'", type);

        return switch (type) {
            case "S3" -> {
                S3StorageProvider.Builder b = S3StorageProvider.builder()
                        .region(config.getOrDefault("region", "us-east-1"));
                if (config.containsKey("accessKey") && config.containsKey("secretKey")) {
                    b.credentials(config.get("accessKey"), config.get("secretKey"));
                } else {
                    b.useDefaultCredentials();
                }
                if (config.containsKey("endpoint")) {
                    b.endpointOverride(config.get("endpoint"));
                }
                yield b.build();
            }

            case "DROPBOX" -> {
                String token = config.get("accessToken");
                if (token == null || token.isBlank()) {
                    throw new IllegalArgumentException("DROPBOX provider requires 'accessToken' in config");
                }
                yield DropboxStorageProvider.builder()
                        .accessToken(token)
                        .clientIdentifier(config.getOrDefault("clientIdentifier",
                                "collibra-dropbox-integration/1.0"))
                        .build();
            }

            case "LOCAL" -> {
                String root = config.getOrDefault("root", "");
                yield root.isBlank()
                        ? LocalStorageProvider.workingDirectory()
                        : LocalStorageProvider.rooted(root);
            }

            default -> throw new IllegalArgumentException("Unknown StorageProvider type: " + type);
        };
    }
}
