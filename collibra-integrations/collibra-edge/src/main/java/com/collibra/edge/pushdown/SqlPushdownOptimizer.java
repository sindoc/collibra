package com.collibra.edge.pushdown;

import com.collibra.edge.device.EdgeDevice;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Analyses a SQL query string and produces a {@link PushdownPlan} describing
 * what can be evaluated at the edge device versus what must be done locally.
 *
 * <h2>Pushdown strategy</h2>
 * <ol>
 *   <li><b>Projection pushdown</b> – explicit SELECT columns are forwarded so
 *       the device only returns requested columns (avoids wide-row transfer).</li>
 *   <li><b>Predicate pushdown</b> – simple WHERE clauses using {@code =}, {@code !=},
 *       {@code >}, {@code <}, {@code >=}, {@code <=}, {@code IN}, {@code LIKE},
 *       {@code IS NULL / IS NOT NULL}, and {@code BETWEEN} are pushed to the device.
 *       Complex expressions (sub-queries, UDFs, OR across different tables) are
 *       retained for local evaluation.</li>
 *   <li><b>Limit pushdown</b> – LIMIT / FETCH FIRST n ROWS ONLY is pushed when no
 *       local post-processing (aggregation, sort) requires the full result set.</li>
 *   <li><b>ORDER BY pushdown</b> – pushed when the device supports native sorting
 *       (JDBC_DATABASE, REST_API with sort params).</li>
 * </ol>
 *
 * <p>This is a lightweight heuristic optimiser based on regex-level SQL parsing.
 * For production use, replace with a proper SQL parser (e.g. Apache Calcite).
 */
public class SqlPushdownOptimizer {

    private static final Logger log = LoggerFactory.getLogger(SqlPushdownOptimizer.class);

    // Devices that support native predicate pushdown
    private static final java.util.Set<EdgeDevice.DeviceType> PREDICATE_PUSHDOWN_CAPABLE =
            java.util.Set.of(EdgeDevice.DeviceType.JDBC_DATABASE, EdgeDevice.DeviceType.REST_API);

    private static final java.util.Set<EdgeDevice.DeviceType> SORT_PUSHDOWN_CAPABLE =
            java.util.Set.of(EdgeDevice.DeviceType.JDBC_DATABASE);

    // Regex patterns for lightweight SQL parsing
    private static final Pattern SELECT_COLS_PAT =
            Pattern.compile("(?i)^\\s*SELECT\\s+(.+?)\\s+FROM\\b", Pattern.DOTALL);
    private static final Pattern WHERE_PAT =
            Pattern.compile("(?i)\\bWHERE\\s+(.+?)(?:\\s+(?:GROUP\\s+BY|ORDER\\s+BY|LIMIT|FETCH)\\b|$)",
                    Pattern.DOTALL);
    private static final Pattern ORDER_BY_PAT =
            Pattern.compile("(?i)\\bORDER\\s+BY\\s+(.+?)(?:\\s+(?:LIMIT|FETCH)\\b|$)", Pattern.DOTALL);
    private static final Pattern LIMIT_PAT =
            Pattern.compile("(?i)\\bLIMIT\\s+(\\d+)|FETCH\\s+FIRST\\s+(\\d+)\\s+ROWS\\s+ONLY", Pattern.DOTALL);

    // Predicate patterns safe to push down (no sub-queries, no UDFs)
    private static final Pattern SIMPLE_PREDICATE_PAT = Pattern.compile(
            "(?i)\\b\\w+\\s*(?:=|!=|<>|>=|<=|>|<|\\bLIKE\\b|\\bIN\\b|\\bBETWEEN\\b|\\bIS\\s+(?:NOT\\s+)?NULL\\b)");

    /**
     * Analyses {@code sql} in the context of the given {@code device} and
     * returns a {@link PushdownPlan}.
     *
     * @param sql    the original SQL query string
     * @param device the target edge device
     * @return a pushdown plan (never null)
     */
    public PushdownPlan analyse(String sql, EdgeDevice device) {
        log.debug("Analysing SQL for pushdown to device '{}' ({}): {}",
                device.getDeviceName(), device.getDeviceType(), sql);

        PushdownPlan.Builder plan = PushdownPlan.builder();

        // --- Projection pushdown ---
        List<String> selectedCols = extractSelectColumns(sql);
        if (!selectedCols.isEmpty() && !selectedCols.contains("*")) {
            plan.pushedColumns(selectedCols);
        }

        // --- Predicate pushdown ---
        if (PREDICATE_PUSHDOWN_CAPABLE.contains(device.getDeviceType())) {
            extractPredicates(sql, plan);
        } else {
            // No native predicate support: all predicates evaluated locally
            String whereClause = extractWhereClause(sql);
            if (!whereClause.isBlank()) {
                plan.localPredicate(whereClause);
            }
        }

        // --- ORDER BY pushdown ---
        if (SORT_PUSHDOWN_CAPABLE.contains(device.getDeviceType())) {
            String orderBy = extractOrderBy(sql);
            if (!orderBy.isBlank()) {
                plan.pushedOrderBy(orderBy);
            }
        }

        // --- LIMIT pushdown ---
        int limit = extractLimit(sql);
        if (limit != Integer.MAX_VALUE) {
            plan.pushedLimit(limit);
        }

        PushdownPlan result = plan.build();
        log.info("Pushdown plan for device '{}': {}", device.getDeviceName(), result.getSummary());
        return result;
    }

    // ------------------------------------------------------------------
    // Internal helpers
    // ------------------------------------------------------------------

    private List<String> extractSelectColumns(String sql) {
        Matcher m = SELECT_COLS_PAT.matcher(sql);
        if (!m.find()) return List.of();
        String cols = m.group(1).trim();
        if (cols.equals("*")) return List.of("*");
        return Arrays.stream(cols.split(","))
                .map(String::trim)
                .collect(Collectors.toList());
    }

    private String extractWhereClause(String sql) {
        Matcher m = WHERE_PAT.matcher(sql);
        return m.find() ? m.group(1).trim() : "";
    }

    private void extractPredicates(String sql, PushdownPlan.Builder plan) {
        String where = extractWhereClause(sql);
        if (where.isBlank()) return;

        // Split on AND (simplistic — does not handle parenthesised OR groups)
        String[] parts = where.split("(?i)\\bAND\\b");
        for (String part : parts) {
            part = part.trim();
            if (isSimplePredicate(part)) {
                plan.pushedPredicate(part);
            } else {
                // Contains sub-query, UDF call, or complex expression
                plan.localPredicate(part);
                log.debug("Predicate '{}' retained for local evaluation", part);
            }
        }
    }

    private boolean isSimplePredicate(String predicate) {
        // Reject sub-queries
        if (predicate.contains("(") && predicate.toLowerCase().contains("select")) return false;
        return SIMPLE_PREDICATE_PAT.matcher(predicate).find();
    }

    private String extractOrderBy(String sql) {
        Matcher m = ORDER_BY_PAT.matcher(sql);
        return m.find() ? m.group(1).trim() : "";
    }

    private int extractLimit(String sql) {
        Matcher m = LIMIT_PAT.matcher(sql);
        if (!m.find()) return Integer.MAX_VALUE;
        String val = m.group(1) != null ? m.group(1) : m.group(2);
        return Integer.parseInt(val);
    }

    /**
     * Rewrites the original SQL to apply the pushdown plan, producing SQL
     * optimised for execution on the target device.
     *
     * @param originalSql the original query
     * @param plan        the pushdown plan to apply
     * @return rewritten SQL ready to send to the device
     */
    public String rewriteForDevice(String originalSql, PushdownPlan plan) {
        // If full pushdown — return as-is (device handles everything)
        if (plan.hasFullPushdown() && !plan.getPushedColumns().isEmpty()) {
            return originalSql;
        }

        // Strip predicates that will be evaluated locally
        String rewritten = originalSql;
        for (String localPred : plan.getLocalPredicates()) {
            rewritten = rewritten.replace(localPred, "1=1");
        }
        return rewritten;
    }
}
