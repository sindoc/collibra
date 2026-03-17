package com.collibra.webhooks.handler;

import com.collibra.webhooks.model.WebhookEvent;

/**
 * SPI for receiving Collibra webhook events.
 *
 * <p>Implement this interface and register instances with
 * {@link com.collibra.webhooks.server.CollibraWebhookServer} to receive
 * callbacks for specific event types.
 *
 * <p>Handler implementations must be thread-safe — the server may call
 * {@link #handle(WebhookEvent)} from multiple threads concurrently.
 */
@FunctionalInterface
public interface WebhookHandler {

    /**
     * Called once for every webhook delivery whose {@code eventType} matches
     * the type(s) this handler was registered for.
     *
     * @param event the fully-deserialized webhook event
     * @throws WebhookHandlerException if the handler cannot process the event
     *         (the server will log the error but continue processing other events)
     */
    void handle(WebhookEvent event) throws WebhookHandlerException;
}
