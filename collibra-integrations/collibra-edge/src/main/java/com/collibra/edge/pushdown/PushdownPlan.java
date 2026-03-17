package com.collibra.edge.pushdown;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Describes what the {@link SqlPushdownOptimizer} was able to push down to
 * the edge device, and what must be evaluated locally on the edge node.
 */
public class PushdownPlan {

    /** Columns explicitly requested in the SELECT clause (empty = SELECT *). */
    private final List<String> pushedColumns;

    /** WHERE clause fragments that can be sent to the device in its native form. */
    private final List<String> pushedPredicates;

    /** WHERE clause fragments the device cannot evaluate — must be done locally. */
    private final List<String> localPredicates;

    /** ORDER BY clause the device can handle natively (may be empty). */
    private final String pushedOrderBy;

    /** LIMIT / FETCH FIRST that can be pushed to the device. */
    private final int pushedLimit;

    /** Human-readable summary for logging and query plans. */
    private final String summary;

    private PushdownPlan(Builder b) {
        this.pushedColumns    = Collections.unmodifiableList(b.pushedColumns);
        this.pushedPredicates = Collections.unmodifiableList(b.pushedPredicates);
        this.localPredicates  = Collections.unmodifiableList(b.localPredicates);
        this.pushedOrderBy    = b.pushedOrderBy;
        this.pushedLimit      = b.pushedLimit;
        this.summary          = buildSummary(b);
    }

    private static String buildSummary(Builder b) {
        return String.format("PushdownPlan[columns=%s, pushedPredicates=%s, localPredicates=%s, limit=%d]",
                b.pushedColumns.isEmpty() ? "*" : b.pushedColumns,
                b.pushedPredicates,
                b.localPredicates,
                b.pushedLimit);
    }

    public List<String> getPushedColumns()    { return pushedColumns; }
    public List<String> getPushedPredicates() { return pushedPredicates; }
    public List<String> getLocalPredicates()  { return localPredicates; }
    public String       getPushedOrderBy()    { return pushedOrderBy; }
    public int          getPushedLimit()      { return pushedLimit; }
    public String       getSummary()          { return summary; }

    public boolean hasFullPushdown() {
        return localPredicates.isEmpty();
    }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private final List<String> pushedColumns    = new ArrayList<>();
        private final List<String> pushedPredicates = new ArrayList<>();
        private final List<String> localPredicates  = new ArrayList<>();
        private String pushedOrderBy = "";
        private int    pushedLimit   = Integer.MAX_VALUE;

        public Builder pushedColumn(String col)      { pushedColumns.add(col);    return this; }
        public Builder pushedColumns(List<String> c) { pushedColumns.addAll(c);   return this; }
        public Builder pushedPredicate(String p)     { pushedPredicates.add(p);   return this; }
        public Builder localPredicate(String p)      { localPredicates.add(p);    return this; }
        public Builder pushedOrderBy(String o)       { this.pushedOrderBy = o;    return this; }
        public Builder pushedLimit(int n)            { this.pushedLimit = n;      return this; }
        public PushdownPlan build()                  { return new PushdownPlan(this); }
    }
}
