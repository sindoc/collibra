package com.collibra.edge.query;

import com.collibra.edge.device.EdgeDevice;
import com.collibra.edge.device.EdgeDeviceRegistry;
import com.collibra.edge.pushdown.PushdownPlan;
import com.collibra.edge.pushdown.SqlPushdownOptimizer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Edge-level SQL query engine.
 *
 * <p>Routes a {@link QueryRequest} to the correct {@link EdgeDevice}, applies
 * SQL pushdown optimisation via {@link SqlPushdownOptimizer}, executes the
 * (possibly rewritten) SQL, and returns a {@link QueryResult}.
 *
 * <h2>Supported device types</h2>
 * <ul>
 *   <li>{@code JDBC_DATABASE} – executed via standard JDBC using the device's
 *       {@code connectionString} as the JDBC URL.  Username/password are read
 *       from device properties {@code db.user} and {@code db.password}.</li>
 *   <li>{@code FILE_SOURCE} – delegates to the storage abstraction layer
 *       (S3 / Dropbox / local) and applies in-memory filtering for pushdown
 *       predicates the storage layer cannot evaluate natively.</li>
 *   <li>Other types – placeholder; extend {@link #executeOnDevice} for custom logic.</li>
 * </ul>
 */
public class EdgeQueryEngine {

    private static final Logger log = LoggerFactory.getLogger(EdgeQueryEngine.class);

    private final EdgeDeviceRegistry    registry;
    private final SqlPushdownOptimizer  optimizer;

    public EdgeQueryEngine(EdgeDeviceRegistry registry) {
        this.registry  = registry;
        this.optimizer = new SqlPushdownOptimizer();
    }

    /**
     * Executes {@code request} against its target edge device.
     *
     * @param request the query request
     * @return the query result including pushdown metadata
     * @throws EdgeQueryException if the device is not found or execution fails
     */
    public QueryResult execute(QueryRequest request) throws EdgeQueryException {
        UUID deviceId = request.getTargetDeviceId();
        EdgeDevice device = registry.find(deviceId)
                .orElseThrow(() -> new EdgeQueryException("No edge device registered with id: " + deviceId));

        if (device.getStatus() == EdgeDevice.ConnectionStatus.OFFLINE) {
            throw new EdgeQueryException("Edge device '" + device.getDeviceName() + "' is OFFLINE");
        }

        log.info("Executing query on device '{}' ({}): {}",
                device.getDeviceName(), device.getDeviceType(), request.getSql());

        // Analyse and plan pushdown
        PushdownPlan plan = optimizer.analyse(request.getSql(), device);
        String deviceSql  = optimizer.rewriteForDevice(request.getSql(), plan);

        long start = System.currentTimeMillis();
        QueryResult result = executeOnDevice(device, deviceSql, request, plan);
        long elapsed = System.currentTimeMillis() - start;

        log.info("Query on '{}' returned {} rows in {}ms (pushdown={})",
                device.getDeviceName(), result.getRowCount(), elapsed, plan.getSummary());
        return result;
    }

    // ------------------------------------------------------------------
    // Device-specific execution
    // ------------------------------------------------------------------

    private QueryResult executeOnDevice(EdgeDevice device,
                                        String deviceSql,
                                        QueryRequest request,
                                        PushdownPlan plan) throws EdgeQueryException {
        return switch (device.getDeviceType()) {
            case JDBC_DATABASE -> executeJdbc(device, deviceSql, request, plan);
            case FILE_SOURCE   -> executeFileSource(device, deviceSql, request, plan);
            default            -> throw new EdgeQueryException(
                    "Device type " + device.getDeviceType() + " is not yet supported by EdgeQueryEngine");
        };
    }

    // ------ JDBC execution ------

    private QueryResult executeJdbc(EdgeDevice device,
                                    String sql,
                                    QueryRequest request,
                                    PushdownPlan plan) throws EdgeQueryException {
        String url  = device.getConnectionString();
        String user = device.getProperties().getOrDefault("db.user", "");
        String pass = device.getProperties().getOrDefault("db.password", "");

        try (Connection conn = DriverManager.getConnection(url, user, pass);
             PreparedStatement ps = conn.prepareStatement(sql)) {

            ps.setQueryTimeout((int) (request.getTimeoutMs() / 1000));
            ps.setFetchSize(request.getFetchSize());
            if (request.getMaxRows() < Integer.MAX_VALUE) {
                ps.setMaxRows(request.getMaxRows());
            }

            // Bind parameters
            List<Object> params = request.getParameters();
            for (int i = 0; i < params.size(); i++) {
                ps.setObject(i + 1, params.get(i));
            }

            long start = System.currentTimeMillis();
            try (ResultSet rs = ps.executeQuery()) {
                return toQueryResult(rs, plan, System.currentTimeMillis() - start);
            }

        } catch (Exception e) {
            throw new EdgeQueryException("JDBC execution failed on device '" +
                    device.getDeviceName() + "': " + e.getMessage(), e);
        }
    }

    private QueryResult toQueryResult(ResultSet rs, PushdownPlan plan, long execMs)
            throws java.sql.SQLException {
        ResultSetMetaData meta = rs.getMetaData();
        int colCount = meta.getColumnCount();

        List<String> columns = new ArrayList<>();
        for (int i = 1; i <= colCount; i++) {
            columns.add(meta.getColumnLabel(i));
        }

        QueryResult.Builder builder = QueryResult.builder()
                .columns(columns)
                .executionTimeMs(execMs)
                .pushdownApplied(!plan.getPushedPredicates().isEmpty())
                .pushdownSummary(plan.getSummary());

        while (rs.next()) {
            Map<String, Object> row = new LinkedHashMap<>();
            for (int i = 1; i <= colCount; i++) {
                row.put(columns.get(i - 1), rs.getObject(i));
            }
            builder.row(row);
        }
        return builder.build();
    }

    // ------ File source execution ------

    private QueryResult executeFileSource(EdgeDevice device,
                                          String sql,
                                          QueryRequest request,
                                          PushdownPlan plan) throws EdgeQueryException {
        // File-source queries are handled by loading the file via the storage layer
        // and applying in-memory row filtering for any local predicates.
        // This stub returns an empty result — wire up CollibraStorageProvider for full impl.
        log.warn("FILE_SOURCE execution stub invoked for device '{}'. " +
                 "Wire up the collibra-storage module for real file access.", device.getDeviceName());
        return QueryResult.builder()
                .columns(plan.getPushedColumns().isEmpty() ? List.of() : plan.getPushedColumns())
                .executionTimeMs(0)
                .pushdownApplied(false)
                .pushdownSummary("FILE_SOURCE stub — no data returned")
                .build();
    }
}
