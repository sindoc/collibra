package com.collibra.webhooks.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Canonical envelope for every Collibra webhook payload.
 *
 * Collibra POSTs a JSON body with this shape whenever a subscribed event
 * occurs on the platform.  Unknown fields are silently ignored so that
 * older handler code is not broken by new platform additions.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class WebhookEvent {

    /** Unique identifier for this specific delivery attempt. */
    @JsonProperty("eventId")
    private UUID eventId;

    /** Discriminator: e.g. "asset.created", "asset.updated", "domain.deleted", "workflow.state.changed" */
    @JsonProperty("eventType")
    private String eventType;

    /** ISO-8601 timestamp produced by the Collibra platform. */
    @JsonProperty("timestamp")
    private Instant timestamp;

    /** Collibra community / domain context. */
    @JsonProperty("communityId")
    private UUID communityId;

    @JsonProperty("domainId")
    private UUID domainId;

    /** Primary resource affected (asset UUID, workflow instance UUID, …). */
    @JsonProperty("resourceId")
    private UUID resourceId;

    /** Human-readable name of the affected resource at event time. */
    @JsonProperty("resourceName")
    private String resourceName;

    /** Type UUID of the affected resource (e.g. Business Term type UUID). */
    @JsonProperty("resourceTypeId")
    private UUID resourceTypeId;

    /** Originating Collibra user. */
    @JsonProperty("actorId")
    private UUID actorId;

    @JsonProperty("actorName")
    private String actorName;

    /**
     * Free-form payload specific to the eventType.
     * For "asset.updated" this contains old/new attribute values;
     * for "workflow.state.changed" it contains the workflow task details.
     */
    @JsonProperty("payload")
    private Map<String, Object> payload;

    // -----------------------------------------------------------------
    // Getters
    // -----------------------------------------------------------------

    public UUID getEventId()          { return eventId; }
    public String getEventType()       { return eventType; }
    public Instant getTimestamp()      { return timestamp; }
    public UUID getCommunityId()       { return communityId; }
    public UUID getDomainId()          { return domainId; }
    public UUID getResourceId()        { return resourceId; }
    public String getResourceName()    { return resourceName; }
    public UUID getResourceTypeId()    { return resourceTypeId; }
    public UUID getActorId()           { return actorId; }
    public String getActorName()       { return actorName; }
    public Map<String, Object> getPayload() { return payload; }

    // -----------------------------------------------------------------
    // Setters (needed for Jackson deserialization)
    // -----------------------------------------------------------------

    public void setEventId(UUID eventId)                         { this.eventId = eventId; }
    public void setEventType(String eventType)                   { this.eventType = eventType; }
    public void setTimestamp(Instant timestamp)                  { this.timestamp = timestamp; }
    public void setCommunityId(UUID communityId)                 { this.communityId = communityId; }
    public void setDomainId(UUID domainId)                       { this.domainId = domainId; }
    public void setResourceId(UUID resourceId)                   { this.resourceId = resourceId; }
    public void setResourceName(String resourceName)             { this.resourceName = resourceName; }
    public void setResourceTypeId(UUID resourceTypeId)           { this.resourceTypeId = resourceTypeId; }
    public void setActorId(UUID actorId)                         { this.actorId = actorId; }
    public void setActorName(String actorName)                   { this.actorName = actorName; }
    public void setPayload(Map<String, Object> payload)          { this.payload = payload; }

    @Override
    public String toString() {
        return "WebhookEvent{eventId=" + eventId +
               ", eventType='" + eventType + '\'' +
               ", resourceId=" + resourceId +
               ", timestamp=" + timestamp + '}';
    }
}
