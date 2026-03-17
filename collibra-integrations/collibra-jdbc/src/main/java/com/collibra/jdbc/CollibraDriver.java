package com.collibra.jdbc;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.Connection;
import java.sql.Driver;
import java.sql.DriverManager;
import java.sql.DriverPropertyInfo;
import java.sql.SQLException;
import java.sql.SQLFeatureNotSupportedException;
import java.util.Properties;
import java.util.logging.Level;

/**
 * Type-4 JDBC driver for Collibra.
 *
 * <h2>JDBC URL format</h2>
 * <pre>
 *   jdbc:collibra://&lt;host&gt;[:&lt;port&gt;][/&lt;database&gt;]
 *                  [?user=&lt;user&gt;&amp;password=&lt;password&gt;&amp;ssl=true]
 * </pre>
 *
 * <h2>Examples</h2>
 * <pre>
 *   jdbc:collibra://api-vlab.collibra.com
 *   jdbc:collibra://collibra.corp.example.com:443?ssl=true&amp;user=admin&amp;password=s3cret
 * </pre>
 *
 * <h2>Virtual tables</h2>
 * The driver exposes these virtual SQL tables:
 * <ul>
 *   <li>{@code ASSETS}            – all assets (id, name, type_id, domain_id, status, created, modified)</li>
 *   <li>{@code ASSET_ATTRIBUTES}  – attribute values per asset</li>
 *   <li>{@code DOMAINS}           – all domains</li>
 *   <li>{@code COMMUNITIES}       – all communities</li>
 *   <li>{@code ASSET_TYPES}       – asset type definitions</li>
 *   <li>{@code RELATIONS}         – relations between assets</li>
 *   <li>{@code RESPONSIBILITIES}  – role assignments</li>
 * </ul>
 *
 * <h2>SQL pushdown</h2>
 * WHERE predicates on indexed columns (id, name, type_id, domain_id, status)
 * are converted to Collibra REST API query parameters, dramatically reducing
 * data transfer over the wire.
 */
public class CollibraDriver implements Driver {

    private static final Logger log = LoggerFactory.getLogger(CollibraDriver.class);

    public static final String DRIVER_PREFIX = "jdbc:collibra:";
    public static final int    MAJOR_VERSION = 1;
    public static final int    MINOR_VERSION = 0;

    static {
        try {
            DriverManager.registerDriver(new CollibraDriver());
            log.info("CollibraDriver v{}.{} registered with DriverManager", MAJOR_VERSION, MINOR_VERSION);
        } catch (SQLException e) {
            throw new ExceptionInInitializerError("Failed to register CollibraDriver: " + e.getMessage());
        }
    }

    @Override
    public Connection connect(String url, Properties info) throws SQLException {
        if (!acceptsURL(url)) {
            return null; // Signal to DriverManager that this driver is not appropriate
        }
        CollibraConnectionConfig config = CollibraConnectionConfig.parse(url, info);
        log.info("Connecting to Collibra at {}://{}:{}", config.isSsl() ? "https" : "http",
                config.getHost(), config.getPort());
        return new CollibraConnection(config);
    }

    @Override
    public boolean acceptsURL(String url) throws SQLException {
        return url != null && url.startsWith(DRIVER_PREFIX);
    }

    @Override
    public DriverPropertyInfo[] getPropertyInfo(String url, Properties info) throws SQLException {
        return new DriverPropertyInfo[]{
            prop("user",     "Collibra username",  false, info.getProperty("user", "")),
            prop("password", "Collibra password",  false, ""),
            prop("ssl",      "Use HTTPS (true/false)", false, "true"),
            prop("pageSize", "REST API page size", false, "1000"),
            prop("timeout",  "Request timeout (ms)", false, "30000"),
        };
    }

    @Override
    public int getMajorVersion() { return MAJOR_VERSION; }

    @Override
    public int getMinorVersion() { return MINOR_VERSION; }

    @Override
    public boolean jdbcCompliant() {
        // Partial JDBC compliance — query-only, no DML
        return false;
    }

    @Override
    public java.util.logging.Logger getParentLogger() throws SQLFeatureNotSupportedException {
        throw new SQLFeatureNotSupportedException("getParentLogger not supported");
    }

    private static DriverPropertyInfo prop(String name, String desc, boolean required, String defaultVal) {
        DriverPropertyInfo p = new DriverPropertyInfo(name, defaultVal);
        p.description = desc;
        p.required    = required;
        return p;
    }
}
