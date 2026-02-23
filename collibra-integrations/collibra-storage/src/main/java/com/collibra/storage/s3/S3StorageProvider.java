package com.collibra.storage.s3;

import com.collibra.storage.StorageProvider;
import com.collibra.storage.model.StorageObject;
import com.collibra.storage.model.StoragePath;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.AwsCredentialsProvider;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.*;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.util.ArrayList;
import java.util.List;

/**
 * {@link StorageProvider} backed by AWS S3.
 *
 * <h2>Configuration</h2>
 * <pre>
 *   S3StorageProvider provider = S3StorageProvider.builder()
 *       .region("us-east-1")
 *       .build();                   // uses default credential chain
 *
 *   // OR with explicit credentials:
 *   S3StorageProvider provider = S3StorageProvider.builder()
 *       .region("eu-west-1")
 *       .credentials("ACCESS_KEY", "SECRET_KEY")
 *       .build();
 *
 *   // OR with a custom endpoint (LocalStack, MinIO, etc.):
 *   S3StorageProvider provider = S3StorageProvider.builder()
 *       .region("us-east-1")
 *       .endpointOverride("http://localhost:4566")
 *       .build();
 * </pre>
 *
 * <h2>Usage</h2>
 * <pre>
 *   List&lt;StorageObject&gt; files = provider.list(StoragePath.of("s3://my-bucket/collibra/"));
 *   byte[] content = provider.readBytes(StoragePath.of("s3://my-bucket/collibra/glossary.xlsx"));
 * </pre>
 */
public class S3StorageProvider implements StorageProvider {

    private static final Logger log = LoggerFactory.getLogger(S3StorageProvider.class);

    private final S3Client s3;

    private S3StorageProvider(Builder b) {
        software.amazon.awssdk.services.s3.S3ClientBuilder builder =
                S3Client.builder().region(Region.of(b.region));
        if (b.credentialsProvider != null) {
            builder.credentialsProvider(b.credentialsProvider);
        }
        if (b.endpointOverride != null) {
            builder.endpointOverride(URI.create(b.endpointOverride));
            builder.forcePathStyle(true); // required for MinIO / LocalStack
        }
        this.s3 = builder.build();
    }

    @Override public String getProviderType() { return "S3"; }

    @Override
    public List<StorageObject> list(StoragePath prefix) throws IOException {
        String bucket = prefix.getBucket();
        String key    = prefix.getKey();

        ListObjectsV2Request req = ListObjectsV2Request.builder()
                .bucket(bucket)
                .prefix(key)
                .build();

        List<StorageObject> results = new ArrayList<>();
        try {
            ListObjectsV2Response resp;
            do {
                resp = s3.listObjectsV2(req);
                for (S3Object obj : resp.contents()) {
                    StoragePath objPath = StoragePath.of("s3://" + bucket + "/" + obj.key());
                    results.add(StorageObject.builder(objPath)
                            .sizeBytes(obj.size())
                            .lastModified(obj.lastModified())
                            .etag(obj.eTag())
                            .build());
                }
                req = req.toBuilder().continuationToken(resp.nextContinuationToken()).build();
            } while (Boolean.TRUE.equals(resp.isTruncated()));
        } catch (S3Exception e) {
            throw new IOException("S3 list failed for " + prefix + ": " + e.getMessage(), e);
        }

        log.debug("S3 list '{}' returned {} objects", prefix, results.size());
        return results;
    }

    @Override
    public InputStream open(StoragePath path) throws IOException {
        try {
            GetObjectRequest req = GetObjectRequest.builder()
                    .bucket(path.getBucket())
                    .key(path.getKey())
                    .build();
            ResponseInputStream<GetObjectResponse> resp = s3.getObject(req);
            log.debug("Opened S3 object: {}", path);
            return resp;
        } catch (S3Exception e) {
            throw new IOException("S3 get failed for " + path + ": " + e.getMessage(), e);
        }
    }

    @Override
    public byte[] readBytes(StoragePath path) throws IOException {
        try (InputStream is = open(path)) {
            return is.readAllBytes();
        }
    }

    @Override
    public boolean exists(StoragePath path) throws IOException {
        try {
            s3.headObject(HeadObjectRequest.builder()
                    .bucket(path.getBucket()).key(path.getKey()).build());
            return true;
        } catch (NoSuchKeyException e) {
            return false;
        } catch (S3Exception e) {
            throw new IOException("S3 head failed for " + path + ": " + e.getMessage(), e);
        }
    }

    @Override
    public StorageObject stat(StoragePath path) throws IOException {
        try {
            HeadObjectResponse head = s3.headObject(HeadObjectRequest.builder()
                    .bucket(path.getBucket()).key(path.getKey()).build());
            return StorageObject.builder(path)
                    .sizeBytes(head.contentLength())
                    .lastModified(head.lastModified())
                    .contentType(head.contentType())
                    .etag(head.eTag())
                    .build();
        } catch (S3Exception e) {
            throw new IOException("S3 stat failed for " + path + ": " + e.getMessage(), e);
        }
    }

    @Override
    public void close() {
        s3.close();
        log.debug("S3StorageProvider closed");
    }

    // ------------------------------------------------------------------

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private String                  region              = "us-east-1";
        private AwsCredentialsProvider  credentialsProvider = null;
        private String                  endpointOverride    = null;

        public Builder region(String region)                              { this.region = region; return this; }
        public Builder endpointOverride(String endpoint)                  { this.endpointOverride = endpoint; return this; }
        public Builder useDefaultCredentials()                            { this.credentialsProvider = DefaultCredentialsProvider.create(); return this; }
        public Builder credentials(String accessKey, String secretKey)    {
            this.credentialsProvider = StaticCredentialsProvider.create(
                    AwsBasicCredentials.create(accessKey, secretKey));
            return this;
        }

        public S3StorageProvider build() { return new S3StorageProvider(this); }
    }
}
