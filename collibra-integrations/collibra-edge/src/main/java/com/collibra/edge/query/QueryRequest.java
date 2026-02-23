package com.collibra.edge.query;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

/**
 * Encapsulates a SQL-like query request directed at a specific edge device.
 *
 * <p>The query is described in a vendor-neutral SQL string.  The
 * {@link com.collibra.edge.pushdown.SqlPushdownOptimizer} analyses the SQL
 * and determines which predicates and projections can be pushed down to the
 * underlying device to avoid transferring unnecessary data to the edge node.
 */
public class QueryRequest {

    private final UUID   targetDeviceId;
    private final String sql;
    private final List<Object> parameters;
    private final int    maxRows;
    private final int    fetchSize;
    private final long   timeoutMs;

    private QueryRequest(Builder b) {
        this.targetDeviceId = b.targetDeviceId;
        this.sql            = b.sql;
        this.parameters     = Collections.unmodifiableList(new ArrayList<>(b.parameters));
        this.maxRows        = b.maxRows;
        this.fetchSize      = b.fetchSize;
        this.timeoutMs      = b.timeoutMs;
    }

    public UUID         getTargetDeviceId() { return targetDeviceId; }
    public String       getSql()            { return sql; }
    public List<Object> getParameters()     { return parameters; }
    public int          getMaxRows()        { return maxRows; }
    public int          getFetchSize()      { return fetchSize; }
    public long         getTimeoutMs()      { return timeoutMs; }

    public static Builder of(UUID deviceId, String sql) {
        return new Builder(deviceId, sql);
    }

    public static final class Builder {
        private final UUID   targetDeviceId;
        private final String sql;
        private final List<Object> parameters = new ArrayList<>();
        private int  maxRows   = Integer.MAX_VALUE;
        private int  fetchSize = 1000;
        private long timeoutMs = 30_000;

        private Builder(UUID deviceId, String sql) {
            this.targetDeviceId = deviceId;
            this.sql            = sql;
        }

        public Builder parameter(Object value)  { parameters.add(value); return this; }
        public Builder maxRows(int n)            { this.maxRows   = n;  return this; }
        public Builder fetchSize(int n)          { this.fetchSize = n;  return this; }
        public Builder timeoutMs(long ms)        { this.timeoutMs = ms; return this; }
        public QueryRequest build()              { return new QueryRequest(this); }
    }
}
