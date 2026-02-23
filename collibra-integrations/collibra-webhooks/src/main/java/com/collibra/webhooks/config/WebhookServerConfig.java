package com.collibra.webhooks.config;

/**
 * Immutable configuration for {@link com.collibra.webhooks.server.CollibraWebhookServer}.
 *
 * Build with the nested {@link Builder}:
 * <pre>
 *   WebhookServerConfig config = WebhookServerConfig.builder()
 *       .port(8443)
 *       .path("/collibra/webhook")
 *       .sharedSecret("my-webhook-secret")
 *       .requireSignatureVerification(true)
 *       .build();
 * </pre>
 */
public final class WebhookServerConfig {

    private final int    port;
    private final String path;
    private final String sharedSecret;
    private final boolean requireSignatureVerification;
    private final int    maxThreads;

    private WebhookServerConfig(Builder b) {
        this.port                        = b.port;
        this.path                        = b.path;
        this.sharedSecret                = b.sharedSecret;
        this.requireSignatureVerification = b.requireSignatureVerification;
        this.maxThreads                  = b.maxThreads;
    }

    public int    getPort()                         { return port; }
    public String getPath()                         { return path; }
    public String getSharedSecret()                 { return sharedSecret; }
    public boolean isRequireSignatureVerification() { return requireSignatureVerification; }
    public int    getMaxThreads()                   { return maxThreads; }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private int    port    = 8080;
        private String path    = "/webhook";
        private String sharedSecret;
        private boolean requireSignatureVerification = false;
        private int    maxThreads = 10;

        public Builder port(int port)                                   { this.port = port; return this; }
        public Builder path(String path)                                 { this.path = path; return this; }
        public Builder sharedSecret(String secret)                       { this.sharedSecret = secret; return this; }
        public Builder requireSignatureVerification(boolean require)      { this.requireSignatureVerification = require; return this; }
        public Builder maxThreads(int maxThreads)                        { this.maxThreads = maxThreads; return this; }

        public WebhookServerConfig build() {
            if (requireSignatureVerification && (sharedSecret == null || sharedSecret.isBlank())) {
                throw new IllegalStateException("sharedSecret is required when requireSignatureVerification=true");
            }
            return new WebhookServerConfig(this);
        }
    }
}
