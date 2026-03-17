package com.collibra.webhooks.handler;

/** Thrown by a {@link WebhookHandler} when event processing fails. */
public class WebhookHandlerException extends Exception {

    public WebhookHandlerException(String message) {
        super(message);
    }

    public WebhookHandlerException(String message, Throwable cause) {
        super(message, cause);
    }
}
