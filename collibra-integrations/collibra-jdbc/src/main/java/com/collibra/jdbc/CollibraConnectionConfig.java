package com.collibra.jdbc;

import java.sql.SQLException;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Parsed Collibra JDBC URL and connection properties.
 *
 * <p>URL format: {@code jdbc:collibra://host[:port][/database][?key=value&...]}
 */
public final class CollibraConnectionConfig {

    // jdbc:collibra://host[:port][/db][?params]
    private static final Pattern URL_PATTERN = Pattern.compile(
            "jdbc:collibra://([^/:?]+)(?::(\\d+))?(?:/([^?]*))?(?:\\?(.*))?");

    private final String  host;
    private final int     port;
    private final String  database;
    private final String  user;
    private final String  password;
    private final boolean ssl;
    private final int     pageSize;
    private final long    timeoutMs;

    private CollibraConnectionConfig(Builder b) {
        this.host      = b.host;
        this.port      = b.port;
        this.database  = b.database;
        this.user      = b.user;
        this.password  = b.password;
        this.ssl       = b.ssl;
        this.pageSize  = b.pageSize;
        this.timeoutMs = b.timeoutMs;
    }

    /**
     * Parses a Collibra JDBC URL and merges with {@code info} properties.
     * Properties in {@code info} override URL query parameters.
     */
    public static CollibraConnectionConfig parse(String url, Properties info) throws SQLException {
        Matcher m = URL_PATTERN.matcher(url);
        if (!m.matches()) {
            throw new SQLException("Invalid Collibra JDBC URL: " + url +
                    "\nExpected: jdbc:collibra://host[:port][/database][?params]");
        }

        Builder b = new Builder();
        b.host     = m.group(1);
        b.port     = m.group(2) != null ? Integer.parseInt(m.group(2)) : 443;
        b.database = m.group(3) != null ? m.group(3) : "";

        // Parse URL query params
        String query = m.group(4);
        if (query != null) {
            for (String kv : query.split("&")) {
                String[] parts = kv.split("=", 2);
                if (parts.length == 2) {
                    applyParam(b, parts[0].trim(), parts[1].trim());
                }
            }
        }

        // Properties file / DriverManager.connect() overrides
        if (info != null) {
            for (String key : info.stringPropertyNames()) {
                applyParam(b, key, info.getProperty(key));
            }
        }

        return b.build();
    }

    private static void applyParam(Builder b, String key, String value) {
        switch (key.toLowerCase()) {
            case "user"     -> b.user     = value;
            case "password" -> b.password = value;
            case "ssl"      -> b.ssl      = Boolean.parseBoolean(value);
            case "pagesize" -> b.pageSize = Integer.parseInt(value);
            case "timeout"  -> b.timeoutMs = Long.parseLong(value);
        }
    }

    public String  getHost()      { return host; }
    public int     getPort()      { return port; }
    public String  getDatabase()  { return database; }
    public String  getUser()      { return user; }
    public String  getPassword()  { return password; }
    public boolean isSsl()        { return ssl; }
    public int     getPageSize()  { return pageSize; }
    public long    getTimeoutMs() { return timeoutMs; }

    public String getBaseUrl() {
        String scheme = ssl ? "https" : "http";
        return scheme + "://" + host + ":" + port;
    }

    private static final class Builder {
        String  host      = "";
        int     port      = 443;
        String  database  = "";
        String  user      = "";
        String  password  = "";
        boolean ssl       = true;
        int     pageSize  = 1000;
        long    timeoutMs = 30_000;

        CollibraConnectionConfig build() { return new CollibraConnectionConfig(this); }
    }
}
