package com.collibra.webhooks.handler;

import com.collibra.webhooks.model.WebhookEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * No-op reference implementation that logs every event at INFO level.
 * Useful as a catch-all fallback handler or during integration testing.
 */
public class LoggingWebhookHandler implements WebhookHandler {

    private static final Logger log = LoggerFactory.getLogger(LoggingWebhookHandler.class);

    @Override
    public void handle(WebhookEvent event) {
        log.info("Collibra webhook received: type={} resourceId={} resourceName='{}' actor={} ts={}",
                event.getEventType(),
                event.getResourceId(),
                event.getResourceName(),
                event.getActorName(),
                event.getTimestamp());
    }
}
