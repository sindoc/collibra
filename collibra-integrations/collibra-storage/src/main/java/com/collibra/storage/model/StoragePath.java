package com.collibra.storage.model;

import java.util.Objects;

/**
 * Provider-neutral path to a storage object.
 *
 * <h2>Path conventions</h2>
 * <ul>
 *   <li><b>S3</b>: {@code bucket} + {@code key} — e.g. bucket="my-data", key="collibra/import.xlsx"</li>
 *   <li><b>Dropbox</b>: path relative to app folder — e.g. "/collibra/imports/glossary.xlsx"</li>
 *   <li><b>Local</b>: absolute or relative filesystem path</li>
 * </ul>
 *
 * Use {@link #of(String)} with a URI string for quick construction:
 * <pre>
 *   StoragePath.of("s3://my-bucket/collibra/import.xlsx")
 *   StoragePath.of("/home/user/data/glossary.csv")
 *   StoragePath.of("dropbox:/collibra/glossary.xlsx")
 * </pre>
 */
public final class StoragePath {

    public static final StoragePath ROOT = new StoragePath("", "", "");

    public enum ProviderHint { S3, DROPBOX, LOCAL, UNSPECIFIED }

    private final String       bucket;   // S3 bucket or empty
    private final String       key;      // S3 key / Dropbox path / local path
    private final String       raw;      // original URI
    private final ProviderHint hint;

    private StoragePath(String bucket, String key, String raw) {
        this.bucket = bucket;
        this.key    = key;
        this.raw    = raw;
        this.hint   = detectHint(raw);
    }

    /**
     * Parses a URI string into a {@link StoragePath}.
     *
     * Supported formats:
     * <pre>
     *   s3://bucket/key/path
     *   dropbox:/path/to/file
     *   /absolute/local/path
     *   relative/local/path
     * </pre>
     */
    public static StoragePath of(String uri) {
        Objects.requireNonNull(uri, "uri must not be null");
        if (uri.startsWith("s3://")) {
            String rest   = uri.substring(5);
            int slash     = rest.indexOf('/');
            String bucket = slash < 0 ? rest : rest.substring(0, slash);
            String key    = slash < 0 ? ""   : rest.substring(slash + 1);
            return new StoragePath(bucket, key, uri);
        } else if (uri.startsWith("dropbox:")) {
            return new StoragePath("", uri.substring(8), uri);
        } else {
            return new StoragePath("", uri, uri);
        }
    }

    public String       getBucket()      { return bucket; }
    public String       getKey()         { return key; }
    public String       getRaw()         { return raw; }
    public ProviderHint getProviderHint() { return hint; }

    /** Returns just the filename portion (last path segment). */
    public String getFileName() {
        if (key.isEmpty()) return "";
        int slash = key.lastIndexOf('/');
        return slash < 0 ? key : key.substring(slash + 1);
    }

    /** Returns the file extension (lower-case, without the dot), or empty string. */
    public String getExtension() {
        String name = getFileName();
        int dot = name.lastIndexOf('.');
        return dot < 0 ? "" : name.substring(dot + 1).toLowerCase();
    }

    /** Creates a child path by appending a segment. */
    public StoragePath child(String segment) {
        String newKey  = key.isEmpty() ? segment : key.endsWith("/") ? key + segment : key + "/" + segment;
        String newBucket = bucket;
        String newRaw  = raw.endsWith("/") ? raw + segment : raw + "/" + segment;
        return new StoragePath(newBucket, newKey, newRaw);
    }

    private static ProviderHint detectHint(String raw) {
        if (raw.startsWith("s3://"))      return ProviderHint.S3;
        if (raw.startsWith("dropbox:"))   return ProviderHint.DROPBOX;
        return ProviderHint.LOCAL;
    }

    @Override public String toString() { return raw; }

    @Override public boolean equals(Object o) {
        return o instanceof StoragePath sp && raw.equals(sp.raw);
    }
    @Override public int hashCode() { return raw.hashCode(); }
}
