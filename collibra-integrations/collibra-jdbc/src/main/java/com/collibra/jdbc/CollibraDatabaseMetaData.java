package com.collibra.jdbc;

import java.sql.*;

/**
 * {@link DatabaseMetaData} implementation for the Collibra JDBC driver.
 *
 * <p>Reports the virtual tables exposed by the driver and the Collibra
 * REST API version.  BI tools such as DBeaver, Tableau, and Power BI
 * query this metadata to discover available tables and column types.
 */
public class CollibraDatabaseMetaData implements DatabaseMetaData {

    private final CollibraConnection connection;
    private final CollibraRestClient client;

    CollibraDatabaseMetaData(CollibraConnection connection, CollibraRestClient client) {
        this.connection = connection;
        this.client     = client;
    }

    // ------------------------------------------------------------------
    // Product info
    // ------------------------------------------------------------------

    @Override public String getDatabaseProductName()    { return "Collibra DGC"; }
    @Override public String getDatabaseProductVersion() { return "REST/2.0"; }
    @Override public String getDriverName()             { return "Collibra JDBC Driver"; }
    @Override public String getDriverVersion()          { return CollibraDriver.MAJOR_VERSION + "." + CollibraDriver.MINOR_VERSION; }
    @Override public int    getDriverMajorVersion()     { return CollibraDriver.MAJOR_VERSION; }
    @Override public int    getDriverMinorVersion()     { return CollibraDriver.MINOR_VERSION; }
    @Override public String getURL()                    { return connection.getConfig().getBaseUrl(); }
    @Override public String getUserName()               { return connection.getConfig().getUser(); }

    @Override public int    getJDBCMajorVersion()      { return 4; }
    @Override public int    getJDBCMinorVersion()      { return 3; }

    // ------------------------------------------------------------------
    // Capability flags
    // ------------------------------------------------------------------

    @Override public boolean isReadOnly()               { return true; }
    @Override public boolean supportsTransactions()     { return false; }
    @Override public boolean supportsMultipleResultSets() { return false; }
    @Override public boolean supportsGetGeneratedKeys() { return false; }
    @Override public boolean supportsBatchUpdates()     { return false; }
    @Override public boolean supportsStoredProcedures() { return false; }
    @Override public boolean supportsSubqueriesInExists() { return false; }
    @Override public boolean supportsSubqueriesInIns()  { return false; }
    @Override public boolean supportsCorrelatedSubqueries() { return false; }
    @Override public boolean supportsOrderByUnrelated() { return true; }
    @Override public boolean supportsGroupBy()          { return false; }
    @Override public boolean supportsGroupByUnrelated() { return false; }
    @Override public boolean supportsLikeEscapeClause() { return true; }
    @Override public boolean supportsUnion()            { return false; }
    @Override public boolean supportsUnionAll()         { return false; }
    @Override public boolean supportsOuterJoins()       { return false; }
    @Override public boolean supportsFullOuterJoins()   { return false; }
    @Override public boolean supportsLimitedOuterJoins() { return false; }
    @Override public boolean supportsMixedCaseIdentifiers() { return false; }
    @Override public boolean storesUpperCaseIdentifiers()   { return true; }
    @Override public boolean storesLowerCaseIdentifiers()   { return false; }
    @Override public boolean storesMixedCaseIdentifiers()   { return false; }
    @Override public boolean supportsMixedCaseQuotedIdentifiers() { return true; }
    @Override public boolean storesUpperCaseQuotedIdentifiers()   { return false; }
    @Override public boolean storesLowerCaseQuotedIdentifiers()   { return false; }
    @Override public boolean storesMixedCaseQuotedIdentifiers()   { return true; }
    @Override public boolean nullsAreSortedHigh()      { return false; }
    @Override public boolean nullsAreSortedLow()       { return true; }
    @Override public boolean nullsAreSortedAtStart()   { return false; }
    @Override public boolean nullsAreSortedAtEnd()     { return false; }
    @Override public boolean usesLocalFiles()          { return false; }
    @Override public boolean usesLocalFilePerTable()   { return false; }
    @Override public boolean allProceduresAreCallable() { return false; }
    @Override public boolean allTablesAreSelectable()  { return true; }
    @Override public boolean isCatalogAtStart()        { return true; }
    @Override public boolean supportsSchemasInTableDefinitions()  { return false; }
    @Override public boolean supportsSchemasInDataManipulation()  { return false; }
    @Override public boolean supportsSchemasInIndexDefinitions()  { return false; }
    @Override public boolean supportsSchemasInPrivilegeDefinitions() { return false; }
    @Override public boolean supportsSchemasInProcedureCalls()    { return false; }
    @Override public boolean supportsCatalogsInTableDefinitions() { return false; }
    @Override public boolean supportsCatalogsInDataManipulation() { return false; }
    @Override public boolean supportsCatalogsInIndexDefinitions() { return false; }
    @Override public boolean supportsCatalogsInPrivilegeDefinitions() { return false; }
    @Override public boolean supportsCatalogsInProcedureCalls()   { return false; }

    @Override public String getIdentifierQuoteString() { return "\""; }
    @Override public String getSQLKeywords()           { return ""; }
    @Override public String getNumericFunctions()      { return ""; }
    @Override public String getStringFunctions()       { return ""; }
    @Override public String getSystemFunctions()       { return ""; }
    @Override public String getTimeDateFunctions()     { return ""; }
    @Override public String getSearchStringEscape()    { return "\\"; }
    @Override public String getExtraNameCharacters()   { return ""; }
    @Override public String getCatalogSeparator()      { return "."; }
    @Override public String getCatalogTerm()           { return "catalog"; }
    @Override public String getSchemaTerm()            { return "schema"; }
    @Override public String getProcedureTerm()         { return "procedure"; }

    @Override public int getMaxBinaryLiteralLength()   { return 0; }
    @Override public int getMaxCharLiteralLength()     { return 0; }
    @Override public int getMaxColumnNameLength()      { return 255; }
    @Override public int getMaxColumnsInGroupBy()      { return 0; }
    @Override public int getMaxColumnsInIndex()        { return 0; }
    @Override public int getMaxColumnsInOrderBy()      { return 0; }
    @Override public int getMaxColumnsInSelect()       { return 0; }
    @Override public int getMaxColumnsInTable()        { return 0; }
    @Override public int getMaxConnections()           { return 0; }
    @Override public int getMaxCursorNameLength()      { return 0; }
    @Override public int getMaxIndexLength()           { return 0; }
    @Override public int getMaxSchemaNameLength()      { return 255; }
    @Override public int getMaxProcedureNameLength()   { return 0; }
    @Override public int getMaxCatalogNameLength()     { return 255; }
    @Override public int getMaxRowSize()               { return 0; }
    @Override public int getMaxStatementLength()       { return 0; }
    @Override public int getMaxStatements()            { return 0; }
    @Override public int getMaxTableNameLength()       { return 255; }
    @Override public int getMaxTablesInSelect()        { return 1; }
    @Override public int getMaxUserNameLength()        { return 255; }
    @Override public int getDefaultTransactionIsolation() { return Connection.TRANSACTION_NONE; }

    @Override public boolean doesMaxRowSizeIncludeBlobs() { return false; }
    @Override public boolean dataDefinitionCausesTransactionCommit() { return false; }
    @Override public boolean dataDefinitionIgnoredInTransactions()   { return false; }
    @Override public boolean supportsDataDefinitionAndDataManipulationTransactions() { return false; }
    @Override public boolean supportsDataManipulationTransactionsOnly()              { return false; }
    @Override public boolean supportsTableCorrelationNames()         { return false; }
    @Override public boolean supportsDifferentTableCorrelationNames() { return false; }
    @Override public boolean supportsExpressionsInOrderBy()          { return false; }
    @Override public boolean supportsMultipleOpenResults()           { return false; }
    @Override public boolean supportsNamedParameters()               { return false; }
    @Override public boolean supportsResultSetConcurrency(int t, int c)     { return c == ResultSet.CONCUR_READ_ONLY; }
    @Override public boolean supportsResultSetHoldability(int holdability)   { return true; }
    @Override public boolean supportsResultSetType(int type)                 { return type == ResultSet.TYPE_FORWARD_ONLY; }
    @Override public boolean supportsStatementPooling()              { return false; }
    @Override public boolean supportsPositionedDelete()              { return false; }
    @Override public boolean supportsPositionedUpdate()              { return false; }
    @Override public boolean supportsSelectForUpdate()               { return false; }
    @Override public boolean supportsOpenCursorsAcrossCommit()       { return false; }
    @Override public boolean supportsOpenCursorsAcrossRollback()     { return false; }
    @Override public boolean supportsOpenStatementsAcrossCommit()    { return false; }
    @Override public boolean supportsOpenStatementsAcrossRollback()  { return false; }
    @Override public boolean locatorsUpdateCopy()                    { return false; }
    @Override public boolean autoCommitFailureClosesAllResultSets()  { return false; }
    @Override public boolean generatedKeyAlwaysReturned()            { return false; }

    @Override public int getResultSetHoldability() { return ResultSet.HOLD_CURSORS_OVER_COMMIT; }
    @Override public RowIdLifetime getRowIdLifetime() { return RowIdLifetime.ROWID_UNSUPPORTED; }

    // ------------------------------------------------------------------
    // Virtual table catalog
    // ------------------------------------------------------------------

    private static final String[][] VIRTUAL_TABLES = {
        { "ASSETS",           "Virtual table: Collibra assets"        },
        { "DOMAINS",          "Virtual table: Collibra domains"        },
        { "COMMUNITIES",      "Virtual table: Collibra communities"    },
        { "ASSET_ATTRIBUTES", "Virtual table: asset attribute values"  },
        { "ASSET_TYPES",      "Virtual table: asset type definitions"  },
        { "RELATIONS",        "Virtual table: inter-asset relations"   },
        { "RESPONSIBILITIES", "Virtual table: role assignments"        },
    };

    @Override
    public ResultSet getTables(String catalog, String schemaPattern,
                               String tableNamePattern, String[] types) throws SQLException {
        // Build an in-memory result set of our virtual tables
        var rows = new java.util.ArrayList<java.util.Map<String, Object>>();
        for (String[] t : VIRTUAL_TABLES) {
            if (tableNamePattern == null || tableNamePattern.equals("%") || t[0].equals(tableNamePattern)) {
                var row = new java.util.LinkedHashMap<String, Object>();
                row.put("TABLE_CAT",   null);
                row.put("TABLE_SCHEM", null);
                row.put("TABLE_NAME",  t[0]);
                row.put("TABLE_TYPE",  "TABLE");
                row.put("REMARKS",     t[1]);
                rows.add(row);
            }
        }
        return new CollibraResultSet(rows, null);
    }

    @Override
    public ResultSet getSchemas() throws SQLException {
        return new CollibraResultSet(java.util.List.of(), null);
    }

    @Override
    public ResultSet getSchemas(String catalog, String schemaPattern) throws SQLException {
        return new CollibraResultSet(java.util.List.of(), null);
    }

    @Override
    public ResultSet getCatalogs() throws SQLException {
        return new CollibraResultSet(java.util.List.of(), null);
    }

    @Override
    public ResultSet getTableTypes() throws SQLException {
        var row = new java.util.LinkedHashMap<String, Object>();
        row.put("TABLE_TYPE", "TABLE");
        return new CollibraResultSet(java.util.List.of(row), null);
    }

    @Override
    public ResultSet getColumns(String catalog, String schemaPattern, String tableNamePattern, String columnNamePattern)
            throws SQLException {
        return new CollibraResultSet(java.util.List.of(), null);
    }

    // ------------------------------------------------------------------
    // Unsupported metadata queries return empty ResultSets
    // ------------------------------------------------------------------

    @Override public ResultSet getProcedures(String c, String s, String p) throws SQLException { return empty(); }
    @Override public ResultSet getProcedureColumns(String c, String s, String p, String col) throws SQLException { return empty(); }
    @Override public ResultSet getColumnPrivileges(String c, String s, String t, String col) throws SQLException { return empty(); }
    @Override public ResultSet getTablePrivileges(String c, String s, String t) throws SQLException { return empty(); }
    @Override public ResultSet getBestRowIdentifier(String c, String s, String t, int scope, boolean nullable) throws SQLException { return empty(); }
    @Override public ResultSet getVersionColumns(String c, String s, String t) throws SQLException { return empty(); }
    @Override public ResultSet getPrimaryKeys(String c, String s, String t) throws SQLException { return empty(); }
    @Override public ResultSet getImportedKeys(String c, String s, String t) throws SQLException { return empty(); }
    @Override public ResultSet getExportedKeys(String c, String s, String t) throws SQLException { return empty(); }
    @Override public ResultSet getCrossReference(String pc, String ps, String pt, String fc, String fs, String ft) throws SQLException { return empty(); }
    @Override public ResultSet getTypeInfo() throws SQLException { return empty(); }
    @Override public ResultSet getIndexInfo(String c, String s, String t, boolean unique, boolean approximate) throws SQLException { return empty(); }
    @Override public ResultSet getUDTs(String c, String s, String t, int[] types) throws SQLException { return empty(); }
    @Override public ResultSet getSuperTypes(String c, String s, String t) throws SQLException { return empty(); }
    @Override public ResultSet getSuperTables(String c, String s, String t) throws SQLException { return empty(); }
    @Override public ResultSet getAttributes(String c, String s, String t, String a) throws SQLException { return empty(); }
    @Override public ResultSet getClientInfoProperties() throws SQLException { return empty(); }
    @Override public ResultSet getFunctions(String c, String s, String fn) throws SQLException { return empty(); }
    @Override public ResultSet getFunctionColumns(String c, String s, String fn, String col) throws SQLException { return empty(); }
    @Override public ResultSet getPseudoColumns(String c, String s, String t, String col) throws SQLException { return empty(); }

    @Override public Connection getConnection() { return connection; }

    @Override public boolean ownUpdatesAreVisible(int type)   { return false; }
    @Override public boolean ownDeletesAreVisible(int type)   { return false; }
    @Override public boolean ownInsertsAreVisible(int type)   { return false; }
    @Override public boolean othersUpdatesAreVisible(int type) { return false; }
    @Override public boolean othersDeletesAreVisible(int type) { return false; }
    @Override public boolean othersInsertsAreVisible(int type) { return false; }
    @Override public boolean updatesAreDetected(int type)     { return false; }
    @Override public boolean deletesAreDetected(int type)     { return false; }
    @Override public boolean insertsAreDetected(int type)     { return false; }

    @Override public <T> T unwrap(Class<T> iface) throws SQLException {
        if (iface.isInstance(this)) return iface.cast(this);
        throw new SQLException("Not a wrapper for " + iface);
    }
    @Override public boolean isWrapperFor(Class<?> iface) { return iface.isInstance(this); }

    private static ResultSet empty() { return new CollibraResultSet(java.util.List.of(), null); }
}
