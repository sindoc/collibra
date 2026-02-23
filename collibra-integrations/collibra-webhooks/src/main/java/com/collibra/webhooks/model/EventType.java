package com.collibra.webhooks.model;

/**
 * Collibra webhook event-type constants.
 *
 * These match the strings Collibra places in the {@code eventType} field of
 * every webhook payload.  Register a {@link com.collibra.webhooks.handler.WebhookHandler}
 * for one or more of these values to receive targeted callbacks.
 */
public final class EventType {

    private EventType() {}

    // ---------------------------------------------------------------
    // Asset lifecycle
    // ---------------------------------------------------------------
    public static final String ASSET_CREATED  = "asset.created";
    public static final String ASSET_UPDATED  = "asset.updated";
    public static final String ASSET_DELETED  = "asset.deleted";
    public static final String ASSET_MOVED    = "asset.moved";

    // ---------------------------------------------------------------
    // Attribute changes
    // ---------------------------------------------------------------
    public static final String ATTRIBUTE_ADDED   = "attribute.added";
    public static final String ATTRIBUTE_UPDATED = "attribute.updated";
    public static final String ATTRIBUTE_REMOVED = "attribute.removed";

    // ---------------------------------------------------------------
    // Relation changes
    // ---------------------------------------------------------------
    public static final String RELATION_ADDED   = "relation.added";
    public static final String RELATION_REMOVED = "relation.removed";

    // ---------------------------------------------------------------
    // Domain / Community lifecycle
    // ---------------------------------------------------------------
    public static final String DOMAIN_CREATED  = "domain.created";
    public static final String DOMAIN_UPDATED  = "domain.updated";
    public static final String DOMAIN_DELETED  = "domain.deleted";
    public static final String COMMUNITY_CREATED = "community.created";
    public static final String COMMUNITY_UPDATED = "community.updated";
    public static final String COMMUNITY_DELETED = "community.deleted";

    // ---------------------------------------------------------------
    // Workflow
    // ---------------------------------------------------------------
    public static final String WORKFLOW_STATE_CHANGED   = "workflow.state.changed";
    public static final String WORKFLOW_TASK_COMPLETED  = "workflow.task.completed";
    public static final String WORKFLOW_INSTANCE_ENDED  = "workflow.instance.ended";

    // ---------------------------------------------------------------
    // Data Quality
    // ---------------------------------------------------------------
    public static final String DQ_RULE_TRIGGERED = "dq.rule.triggered";
    public static final String DQ_SCORE_CHANGED  = "dq.score.changed";

    // ---------------------------------------------------------------
    // Status / Responsibility
    // ---------------------------------------------------------------
    public static final String STATUS_CHANGED      = "status.changed";
    public static final String RESPONSIBILITY_ADDED   = "responsibility.added";
    public static final String RESPONSIBILITY_REMOVED = "responsibility.removed";
}
