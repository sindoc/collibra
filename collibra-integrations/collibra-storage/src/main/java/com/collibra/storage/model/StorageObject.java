package com.collibra.storage.model;

import java.time.Instant;

/**
 * Metadata descriptor for an object in a storage provider.
 * Does not contain the object's content — use {@link com.collibra.storage.StorageProvider#open}
 * to stream content.
 */
public final class StorageObject {

    private final StoragePath path;
    private final long        sizeBytes;
    private final Instant     lastModified;
    private final String      contentType;
    private final String      etag;
    private final boolean     isDirectory;

    private StorageObject(Builder b) {
        this.path         = b.path;
        this.sizeBytes    = b.sizeBytes;
        this.lastModified = b.lastModified;
        this.contentType  = b.contentType;
        this.etag         = b.etag;
        this.isDirectory  = b.isDirectory;
    }

    public StoragePath getPath()         { return path; }
    public long        getSizeBytes()    { return sizeBytes; }
    public Instant     getLastModified() { return lastModified; }
    public String      getContentType()  { return contentType; }
    public String      getEtag()         { return etag; }
    public boolean     isDirectory()     { return isDirectory; }

    @Override
    public String toString() {
        return "StorageObject{path=" + path + ", size=" + sizeBytes + ", modified=" + lastModified + '}';
    }

    public static Builder builder(StoragePath path) { return new Builder(path); }

    public static final class Builder {
        private final StoragePath path;
        private long    sizeBytes    = -1;
        private Instant lastModified;
        private String  contentType  = "application/octet-stream";
        private String  etag         = "";
        private boolean isDirectory  = false;

        private Builder(StoragePath path) { this.path = path; }

        public Builder sizeBytes(long s)      { this.sizeBytes    = s;  return this; }
        public Builder lastModified(Instant t){ this.lastModified  = t;  return this; }
        public Builder contentType(String ct) { this.contentType   = ct; return this; }
        public Builder etag(String e)         { this.etag          = e;  return this; }
        public Builder isDirectory(boolean d) { this.isDirectory   = d;  return this; }
        public StorageObject build()          { return new StorageObject(this); }
    }
}
