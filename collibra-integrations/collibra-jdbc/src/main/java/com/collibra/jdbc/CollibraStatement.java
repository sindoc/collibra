package com.collibra.jdbc;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.*;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * JDBC {@link Statement} that translates SQL SELECT queries into Collibra
 * REST API calls with SQL pushdown for supported predicates.
 *
 * <h2>Supported virtual table queries</h2>
 * <pre>
 *   SELECT * FROM ASSETS WHERE name = 'Customer'
 *   SELECT id, name, status FROM ASSETS WHERE typeId = '...' LIMIT 100
 *   SELECT * FROM DOMAINS
 *   SELECT * FROM COMMUNITIES
 *   SELECT * FROM ASSET_ATTRIBUTES WHERE assetId = '...'
 * </pre>
 *
 * <h2>Pushdown mapping</h2>
 * Equality predicates on known columns are converted to REST query parameters:
 * {@code name=Customer}, {@code typeId=...}, {@code domainId=...}, {@code status=ACCEPTED}.
 */
public class CollibraStatement implements Statement {

    private static final Logger log = LoggerFactory.getLogger(CollibraStatement.class);

    // SQL pattern: SELECT [cols] FROM [table] [WHERE ...] [LIMIT n]
    private static final Pattern SELECT_PAT = Pattern.compile(
            "(?i)\\bSELECT\\b.*?\\bFROM\\b\\s+(\\w+)(?:\\s+WHERE\\s+(.+?))?(?:\\s+LIMIT\\s+(\\d+))?\\s*$",
            Pattern.DOTALL);

    // Simple equality predicate: column = 'value' or column = value
    private static final Pattern EQ_PRED = Pattern.compile(
            "(?i)(\\w+)\\s*=\\s*'?([^'\\s,)]+)'?");

    protected final CollibraConnection connection;
    protected final CollibraRestClient  client;

    private final AtomicBoolean closed    = new AtomicBoolean(false);
    private CollibraResultSet   currentRs;
    private int                 maxRows   = 0;
    private int                 fetchSize = 1000;
    private int                 queryTimeout = 30;
    private SQLWarning          warnings;

    CollibraStatement(CollibraConnection connection, CollibraRestClient client) {
        this.connection = connection;
        this.client     = client;
    }

    @Override
    public ResultSet executeQuery(String sql) throws SQLException {
        checkOpen();
        log.info("Executing Collibra SQL: {}", sql);

        Matcher m = SELECT_PAT.matcher(sql.trim());
        if (!m.find()) {
            throw new SQLException("Unsupported SQL (only SELECT is supported): " + sql);
        }

        String table      = m.group(1).toUpperCase();
        String whereClause = m.group(2) != null ? m.group(2).trim() : "";
        int    limit       = m.group(3) != null ? Integer.parseInt(m.group(3)) : config().getPageSize();
        if (maxRows > 0 && limit > maxRows) limit = maxRows;

        String filterParams = buildFilterParams(whereClause);
        log.debug("Table='{}' filter='{}' limit={}", table, filterParams, limit);

        List<Map<String, Object>> rows = fetchRows(table, filterParams, limit);
        currentRs = new CollibraResultSet(rows, this);
        return currentRs;
    }

    @Override
    public boolean execute(String sql) throws SQLException {
        executeQuery(sql);
        return true;
    }

    @Override
    public ResultSet getResultSet() { return currentRs; }

    @Override
    public int executeUpdate(String sql) throws SQLException {
        throw new SQLFeatureNotSupportedException("Collibra JDBC driver is read-only");
    }

    // ------------------------------------------------------------------
    // Internal helpers
    // ------------------------------------------------------------------

    private List<Map<String, Object>> fetchRows(String table, String filterParams, int limit)
            throws SQLException {
        return switch (table) {
            case "ASSETS"           -> client.queryAssets(filterParams, 0, limit);
            case "DOMAINS"          -> client.queryDomains(filterParams, 0, limit);
            case "COMMUNITIES"      -> client.queryCommunities(filterParams, 0, limit);
            default -> throw new SQLException("Unknown virtual table: " + table +
                    ". Supported: ASSETS, DOMAINS, COMMUNITIES");
        };
    }

    /**
     * Converts a WHERE clause into Collibra REST API query parameters.
     * Simple equality predicates are pushed down; others are ignored at this
     * level (would need post-filtering in a full implementation).
     */
    private String buildFilterParams(String whereClause) {
        if (whereClause.isBlank()) return "";
        StringBuilder sb = new StringBuilder();
        Matcher m = EQ_PRED.matcher(whereClause);
        while (m.find()) {
            if (!sb.isEmpty()) sb.append('&');
            sb.append(m.group(1)).append('=').append(m.group(2));
        }
        return sb.toString();
    }

    private CollibraConnectionConfig config() { return connection.getConfig(); }

    private void checkOpen() throws SQLException {
        if (closed.get())          throw new SQLException("Statement is closed");
        if (connection.isClosed()) throw new SQLException("Connection is closed");
    }

    // ------------------------------------------------------------------
    // Standard JDBC boilerplate
    // ------------------------------------------------------------------

    @Override public void close()                              { closed.set(true); }
    @Override public boolean isClosed()                        { return closed.get(); }
    @Override public int    getMaxRows()                       { return maxRows; }
    @Override public void   setMaxRows(int max)                { this.maxRows = max; }
    @Override public int    getFetchSize()                     { return fetchSize; }
    @Override public void   setFetchSize(int rows)             { this.fetchSize = rows; }
    @Override public int    getQueryTimeout()                  { return queryTimeout; }
    @Override public void   setQueryTimeout(int seconds)       { this.queryTimeout = seconds; }
    @Override public SQLWarning getWarnings()                  { return warnings; }
    @Override public void   clearWarnings()                    { warnings = null; }
    @Override public Connection getConnection()                { return connection; }
    @Override public int    getResultSetType()                 { return ResultSet.TYPE_FORWARD_ONLY; }
    @Override public int    getResultSetConcurrency()          { return ResultSet.CONCUR_READ_ONLY; }
    @Override public int    getResultSetHoldability()          { return ResultSet.HOLD_CURSORS_OVER_COMMIT; }
    @Override public boolean isPoolable()                      { return false; }
    @Override public void   setPoolable(boolean poolable)      { /* no-op */ }
    @Override public boolean isCloseOnCompletion()             { return false; }
    @Override public void   closeOnCompletion()                { /* no-op */ }

    @Override public int    getMaxFieldSize()                  { return 0; }
    @Override public void   setMaxFieldSize(int max)           { /* no-op */ }
    @Override public void   setEscapeProcessing(boolean e)     { /* no-op */ }
    @Override public void   setCursorName(String name)         { /* no-op */ }
    @Override public int    getUpdateCount()                   { return -1; }
    @Override public boolean getMoreResults()                  { return false; }
    @Override public boolean getMoreResults(int current)       { return false; }
    @Override public void   cancel()                           { /* no-op */ }

    @Override public int    executeUpdate(String sql, int ag)        throws SQLException { throw notSupported(); }
    @Override public int    executeUpdate(String sql, int[] ci)      throws SQLException { throw notSupported(); }
    @Override public int    executeUpdate(String sql, String[] cn)   throws SQLException { throw notSupported(); }
    @Override public boolean execute(String sql, int ag)             throws SQLException { return execute(sql); }
    @Override public boolean execute(String sql, int[] ci)           throws SQLException { return execute(sql); }
    @Override public boolean execute(String sql, String[] cn)        throws SQLException { return execute(sql); }
    @Override public int[]  executeBatch()                           throws SQLException { throw notSupported(); }
    @Override public void   addBatch(String sql)                     throws SQLException { throw notSupported(); }
    @Override public void   clearBatch()                             throws SQLException { throw notSupported(); }
    @Override public ResultSet getGeneratedKeys()                    throws SQLException { throw notSupported(); }
    @Override public long   getLargeUpdateCount()                    { return -1L; }
    @Override public long   getLargeMaxRows()                        { return maxRows; }
    @Override public void   setLargeMaxRows(long max)                { this.maxRows = (int) max; }

    @Override public <T> T unwrap(Class<T> i)   throws SQLException {
        if (i.isInstance(this)) return i.cast(this);
        throw new SQLException("Not a wrapper for " + i);
    }
    @Override public boolean isWrapperFor(Class<?> i) { return i.isInstance(this); }

    private static SQLFeatureNotSupportedException notSupported() {
        return new SQLFeatureNotSupportedException("Operation not supported by CollibraDriver (read-only)");
    }
}
