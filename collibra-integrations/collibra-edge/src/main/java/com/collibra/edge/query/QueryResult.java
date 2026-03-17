package com.collibra.edge.query;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * Result returned by the {@link EdgeQueryEngine} after executing a query.
 *
 * <p>Each row is a {@code Map<columnName, value>} to keep the API independent
 * of any particular JDBC or ResultSet implementation.
 */
public class QueryResult {

    private final List<String>          columns;
    private final List<Map<String, Object>> rows;
    private final long                  executionTimeMs;
    private final boolean               pushdownApplied;
    private final String                pushdownSummary;

    private QueryResult(Builder b) {
        this.columns         = Collections.unmodifiableList(new ArrayList<>(b.columns));
        this.rows            = Collections.unmodifiableList(new ArrayList<>(b.rows));
        this.executionTimeMs = b.executionTimeMs;
        this.pushdownApplied = b.pushdownApplied;
        this.pushdownSummary = b.pushdownSummary;
    }

    public List<String>              getColumns()         { return columns; }
    public List<Map<String, Object>> getRows()            { return rows; }
    public int                       getRowCount()        { return rows.size(); }
    public long                      getExecutionTimeMs() { return executionTimeMs; }
    public boolean                   isPushdownApplied()  { return pushdownApplied; }
    public String                    getPushdownSummary() { return pushdownSummary; }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private final List<String>          columns = new ArrayList<>();
        private final List<Map<String, Object>> rows = new ArrayList<>();
        private long    executionTimeMs;
        private boolean pushdownApplied;
        private String  pushdownSummary = "";

        public Builder columns(List<String> cols)          { columns.addAll(cols); return this; }
        public Builder row(Map<String, Object> row)        { rows.add(row); return this; }
        public Builder rows(List<Map<String, Object>> rs)  { rows.addAll(rs); return this; }
        public Builder executionTimeMs(long ms)            { executionTimeMs = ms; return this; }
        public Builder pushdownApplied(boolean v)          { pushdownApplied = v; return this; }
        public Builder pushdownSummary(String s)           { pushdownSummary = s; return this; }
        public QueryResult build()                         { return new QueryResult(this); }
    }
}
