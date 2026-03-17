package com.collibra.jdbc;

import java.io.InputStream;
import java.io.Reader;
import java.math.BigDecimal;
import java.net.URL;
import java.sql.*;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;

/**
 * Minimal {@link PreparedStatement} implementation for the Collibra JDBC driver.
 *
 * <p>Supports positional parameter binding ({@code ?}) for SELECT queries.
 * Parameters are substituted into the SQL string before passing to
 * {@link CollibraStatement#executeQuery(String)}.
 */
public class CollibrapreparedStatement extends CollibraStatement implements PreparedStatement {

    private final String       template;
    private final List<Object> params = new ArrayList<>();

    CollibrapreparedStatement(CollibraConnection connection,
                              CollibraRestClient  client,
                              String              sql) {
        super(connection, client);
        this.template = sql;
    }

    @Override
    public ResultSet executeQuery() throws SQLException {
        return executeQuery(bindParameters());
    }

    @Override
    public int executeUpdate() throws SQLException {
        throw new SQLFeatureNotSupportedException("Collibra JDBC driver is read-only");
    }

    @Override
    public boolean execute() throws SQLException {
        return execute(bindParameters());
    }

    // ------------------------------------------------------------------
    // Parameter setters
    // ------------------------------------------------------------------

    private void ensureCapacity(int index) {
        while (params.size() < index) params.add(null);
    }

    @Override public void setNull(int i, int t)                    { ensureCapacity(i); params.set(i-1, null); }
    @Override public void setBoolean(int i, boolean v)             { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setByte(int i, byte v)                   { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setShort(int i, short v)                 { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setInt(int i, int v)                     { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setLong(int i, long v)                   { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setFloat(int i, float v)                 { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setDouble(int i, double v)               { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setBigDecimal(int i, BigDecimal v)       { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setString(int i, String v)               { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setDate(int i, Date v)                   { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setTime(int i, Time v)                   { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setTimestamp(int i, Timestamp v)         { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setObject(int i, Object v)               { ensureCapacity(i); params.set(i-1, v); }
    @Override public void setObject(int i, Object v, int t)        { setObject(i, v); }
    @Override public void setObject(int i, Object v, int t, int s) { setObject(i, v); }
    @Override public void setNull(int i, int t, String tn)         { setNull(i, t); }
    @Override public void clearParameters()                        { params.clear(); }

    @Override public void addBatch()                               throws SQLException { throw notSupported(); }
    @Override public ResultSetMetaData getMetaData()               throws SQLException { throw notSupported(); }
    @Override public ParameterMetaData  getParameterMetaData()     throws SQLException { throw notSupported(); }

    @Override public void setBytes(int i, byte[] v)                throws SQLException { throw notSupported(); }
    @Override public void setAsciiStream(int i, InputStream in, int l) throws SQLException { throw notSupported(); }
    @Override public void setUnicodeStream(int i, InputStream in, int l) throws SQLException { throw notSupported(); }
    @Override public void setBinaryStream(int i, InputStream in, int l)  throws SQLException { throw notSupported(); }
    @Override public void setCharacterStream(int i, Reader r, int l)     throws SQLException { throw notSupported(); }
    @Override public void setRef(int i, Ref v)                     throws SQLException { throw notSupported(); }
    @Override public void setBlob(int i, Blob v)                   throws SQLException { throw notSupported(); }
    @Override public void setClob(int i, Clob v)                   throws SQLException { throw notSupported(); }
    @Override public void setArray(int i, Array v)                 throws SQLException { throw notSupported(); }
    @Override public void setDate(int i, Date v, Calendar cal)     throws SQLException { throw notSupported(); }
    @Override public void setTime(int i, Time v, Calendar cal)     throws SQLException { throw notSupported(); }
    @Override public void setTimestamp(int i, Timestamp v, Calendar cal) throws SQLException { throw notSupported(); }
    @Override public void setURL(int i, URL v)                     throws SQLException { throw notSupported(); }
    @Override public void setRowId(int i, RowId v)                 throws SQLException { throw notSupported(); }
    @Override public void setNString(int i, String v)              throws SQLException { throw notSupported(); }
    @Override public void setNCharacterStream(int i, Reader v, long l)   throws SQLException { throw notSupported(); }
    @Override public void setNClob(int i, NClob v)                 throws SQLException { throw notSupported(); }
    @Override public void setClob(int i, Reader r, long l)         throws SQLException { throw notSupported(); }
    @Override public void setBlob(int i, InputStream in, long l)   throws SQLException { throw notSupported(); }
    @Override public void setNClob(int i, Reader r, long l)        throws SQLException { throw notSupported(); }
    @Override public void setSQLXML(int i, SQLXML v)               throws SQLException { throw notSupported(); }
    @Override public void setAsciiStream(int i, InputStream in, long l) throws SQLException { throw notSupported(); }
    @Override public void setBinaryStream(int i, InputStream in, long l) throws SQLException { throw notSupported(); }
    @Override public void setCharacterStream(int i, Reader r, long l)   throws SQLException { throw notSupported(); }
    @Override public void setAsciiStream(int i, InputStream in)    throws SQLException { throw notSupported(); }
    @Override public void setBinaryStream(int i, InputStream in)   throws SQLException { throw notSupported(); }
    @Override public void setCharacterStream(int i, Reader r)      throws SQLException { throw notSupported(); }
    @Override public void setNCharacterStream(int i, Reader r)     throws SQLException { throw notSupported(); }
    @Override public void setClob(int i, Reader r)                 throws SQLException { throw notSupported(); }
    @Override public void setBlob(int i, InputStream in)           throws SQLException { throw notSupported(); }
    @Override public void setNClob(int i, Reader r)                throws SQLException { throw notSupported(); }

    // ------------------------------------------------------------------

    private String bindParameters() throws SQLException {
        String sql = template;
        for (Object p : params) {
            String value = p == null ? "NULL" : ("'" + p.toString().replace("'", "''") + "'");
            sql = sql.replaceFirst("\\?", value);
        }
        return sql;
    }

    private static SQLFeatureNotSupportedException notSupported() {
        return new SQLFeatureNotSupportedException("Not supported by Collibra JDBC driver");
    }
}
