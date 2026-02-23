package com.collibra.webhooks.security;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.InvalidKeyException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/**
 * Verifies Collibra webhook HMAC-SHA256 signatures.
 *
 * <p>Collibra signs every webhook delivery with the shared secret configured
 * in the webhook subscription.  The signature is delivered in the
 * {@code X-Collibra-Signature} request header as a lowercase hex string.
 *
 * <pre>
 * Expected header format:
 *   X-Collibra-Signature: sha256=&lt;hex-digest&gt;
 * </pre>
 */
public final class HmacVerifier {

    private static final String ALGORITHM  = "HmacSHA256";
    private static final String PREFIX     = "sha256=";

    private final byte[] secretBytes;

    /**
     * @param sharedSecret the secret configured in the Collibra webhook subscription
     */
    public HmacVerifier(String sharedSecret) {
        if (sharedSecret == null || sharedSecret.isBlank()) {
            throw new IllegalArgumentException("sharedSecret must not be null or blank");
        }
        this.secretBytes = sharedSecret.getBytes(StandardCharsets.UTF_8);
    }

    /**
     * Verifies the {@code X-Collibra-Signature} header value against the raw
     * request body.
     *
     * @param rawBody         the exact bytes received in the HTTP request body
     * @param signatureHeader the value of the {@code X-Collibra-Signature} header
     * @return {@code true} if the signature is valid, {@code false} otherwise
     */
    public boolean verify(byte[] rawBody, String signatureHeader) {
        if (signatureHeader == null || !signatureHeader.startsWith(PREFIX)) {
            return false;
        }
        String receivedHex = signatureHeader.substring(PREFIX.length());
        String expectedHex = computeHmac(rawBody);
        // Constant-time comparison to prevent timing attacks
        return MessageDigest.isEqual(
                expectedHex.getBytes(StandardCharsets.UTF_8),
                receivedHex.getBytes(StandardCharsets.UTF_8));
    }

    private String computeHmac(byte[] data) {
        try {
            Mac mac = Mac.getInstance(ALGORITHM);
            mac.init(new SecretKeySpec(secretBytes, ALGORITHM));
            byte[] digest = mac.doFinal(data);
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException | InvalidKeyException e) {
            throw new IllegalStateException("HMAC-SHA256 unavailable", e);
        }
    }
}
