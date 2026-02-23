package com.collibra.jdbc;

import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.sql.Types;
import java.util.List;

/** Lightweight {@link ResultSetMetaData} for the Collibra JDBC driver. */
public class CollibraResultSetMetaData implements ResultSetMetaData {

    private final List<String> columns;

    CollibraResultSetMetaData(List<String> columns) {
        this.columns = columns;
    }

    @Override
    public int getColumnCount() { return columns.size(); }

    @Override
    public String getColumnName(int column) throws SQLException {
        return col(column);
    }

    @Override
    public String getColumnLabel(int column) throws SQLException {
        return col(column);
    }

    @Override
    public int getColumnType(int column) throws SQLException {
        // All Collibra REST fields are treated as VARCHAR for max compatibility
        return Types.VARCHAR;
    }

    @Override
    public String getColumnTypeName(int column) { return "VARCHAR"; }

    @Override
    public String getColumnClassName(int column) { return "java.lang.String"; }

    @Override
    public int isNullable(int column) { return columnNullable; }

    @Override
    public boolean isAutoIncrement(int column) { return false; }
    @Override
    public boolean isCaseSensitive(int column) { return false; }
    @Override
    public boolean isSearchable(int column)    { return true; }
    @Override
    public boolean isCurrency(int column)      { return false; }
    @Override
    public boolean isSigned(int column)        { return false; }
    @Override
    public int    getColumnDisplaySize(int c)  { return 255; }
    @Override
    public String getSchemaName(int column)    { return ""; }
    @Override
    public int    getPrecision(int column)     { return 255; }
    @Override
    public int    getScale(int column)         { return 0; }
    @Override
    public String getTableName(int column)     { return ""; }
    @Override
    public String getCatalogName(int column)   { return ""; }
    @Override
    public boolean isReadOnly(int column)      { return true; }
    @Override
    public boolean isWritable(int column)      { return false; }
    @Override
    public boolean isDefinitelyWritable(int c) { return false; }

    @Override
    public <T> T unwrap(Class<T> iface) throws SQLException {
        if (iface.isInstance(this)) return iface.cast(this);
        throw new SQLException("Not a wrapper for " + iface);
    }
    @Override
    public boolean isWrapperFor(Class<?> iface) { return iface.isInstance(this); }

    private String col(int index) throws SQLException {
        if (index < 1 || index > columns.size())
            throw new SQLException("Column index out of range: " + index);
        return columns.get(index - 1);
    }
}
