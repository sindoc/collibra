package io.sindoc.collibra.edge;

/**
 * Checked exception thrown by edge site operations.
 *
 * <p>All methods on {@link EdgeSite}, {@link EdgeSiteRegistry}, {@link EdgeSiteServer},
 * and {@link EdgeSiteCapability} that interact with the network or with Collibra DGC
 * declare {@code throws EdgeSiteException}.  Callers must handle or propagate it.
 *
 * <p>The {@link #getCode()} value gives machine-readable context for logging and
 * monitoring.  See the inner {@link Code} enum for all defined codes.
 *
 * @since 1.0
 */
public class EdgeSiteException extends Exception {

    /**
     * Machine-readable error codes for edge site failures.
     */
    public enum Code {

        /** DGC registration request was rejected or returned an error response. */
        REGISTRATION_FAILED,

        /** The configured registration key is invalid or expired. */
        INVALID_REGISTRATION_KEY,

        /** Network connection to the DGC instance could not be established. */
        DGC_UNREACHABLE,

        /** A capability failed to activate. */
        CAPABILITY_ACTIVATION_FAILED,

        /** A capability invocation returned an error from the remote side. */
        CAPABILITY_INVOCATION_FAILED,

        /** The embedded HTTP server could not be started on the configured port. */
        SERVER_START_FAILED,

        /** Configuration is missing a required value. */
        INVALID_CONFIGURATION,

        /** An operation was attempted on a site that is not in the required state. */
        INVALID_STATE,

        /** An unexpected error with no more specific code. */
        INTERNAL_ERROR
    }

    private static final long serialVersionUID = 1L;

    private final Code code;

    /**
     * Constructs an exception with a code and message.
     *
     * @param code    machine-readable error code
     * @param message human-readable description
     */
    public EdgeSiteException(Code code, String message) {
        super(message);
        this.code = code;
    }

    /**
     * Constructs an exception with a code, message, and cause.
     *
     * @param code    machine-readable error code
     * @param message human-readable description
     * @param cause   the underlying exception
     */
    public EdgeSiteException(Code code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }

    /**
     * Returns the machine-readable error code.
     *
     * @return the error code for this exception
     */
    public Code getCode() {
        return code;
    }

    @Override
    public String toString() {
        return "EdgeSiteException[" + code + "]: " + getMessage();
    }
}
