package com.collibra.jdbc;

import java.io.InputStream;
import java.io.Reader;
import java.math.BigDecimal;
import java.net.URL;
import java.sql.*;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;
import java.util.Map;

/**
 * Forward-only, read-only JDBC {@link ResultSet} backed by an in-memory list
 * of row maps populated from the Collibra REST API.
 *
 * <p>Column indexing is 1-based per the JDBC spec.  Column names are
 * case-insensitive for lookup.
 */
public class CollibraResultSet implements ResultSet {

    private final List<Map<String, Object>> rows;
    private final List<String>              columns;
    private final CollibraStatement         statement;

    private int     cursor  = -1; // before first row
    private boolean closed  = false;
    private boolean wasNull = false;

    CollibraResultSet(List<Map<String, Object>> rows, CollibraStatement statement) {
        this.rows      = rows;
        this.statement = statement;
        // Derive column order from the first row (preserve insertion order)
        if (!rows.isEmpty()) {
            this.columns = new ArrayList<>(rows.getFirst().keySet());
        } else {
            this.columns = new ArrayList<>();
        }
    }

    // ------------------------------------------------------------------
    // Navigation
    // ------------------------------------------------------------------

    @Override
    public boolean next() throws SQLException {
        checkOpen();
        cursor++;
        return cursor < rows.size();
    }

    @Override public boolean isBeforeFirst() { return cursor < 0; }
    @Override public boolean isAfterLast()   { return cursor >= rows.size(); }
    @Override public boolean isFirst()        { return cursor == 0; }
    @Override public boolean isLast()         { return cursor == rows.size() - 1; }
    @Override public int     getRow()         { return cursor + 1; }

    // ------------------------------------------------------------------
    // Column accessors
    // ------------------------------------------------------------------

    @Override
    public Object getObject(int columnIndex) throws SQLException {
        return getObject(columnName(columnIndex));
    }

    @Override
    public Object getObject(String columnLabel) throws SQLException {
        checkOpen();
        checkRow();
        Object value = currentRow().get(findColumn(columnLabel));
        wasNull = (value == null);
        return value;
    }

    @Override
    public String getString(int columnIndex)     throws SQLException { return asString(getObject(columnIndex)); }
    @Override
    public String getString(String columnLabel)  throws SQLException { return asString(getObject(columnLabel)); }

    @Override
    public int getInt(int columnIndex)           throws SQLException { return asInt(getObject(columnIndex)); }
    @Override
    public int getInt(String columnLabel)        throws SQLException { return asInt(getObject(columnLabel)); }

    @Override
    public long getLong(int columnIndex)         throws SQLException { return asLong(getObject(columnIndex)); }
    @Override
    public long getLong(String columnLabel)      throws SQLException { return asLong(getObject(columnLabel)); }

    @Override
    public double getDouble(int columnIndex)     throws SQLException { return asDouble(getObject(columnIndex)); }
    @Override
    public double getDouble(String columnLabel)  throws SQLException { return asDouble(getObject(columnLabel)); }

    @Override
    public boolean getBoolean(int columnIndex)   throws SQLException { return asBoolean(getObject(columnIndex)); }
    @Override
    public boolean getBoolean(String columnLabel) throws SQLException { return asBoolean(getObject(columnLabel)); }

    @Override
    public boolean wasNull() { return wasNull; }

    // ------------------------------------------------------------------
    // Metadata
    // ------------------------------------------------------------------

    @Override
    public ResultSetMetaData getMetaData() {
        return new CollibraResultSetMetaData(columns);
    }

    @Override
    public int findColumn(String columnLabel) throws SQLException {
        for (int i = 0; i < columns.size(); i++) {
            if (columns.get(i).equalsIgnoreCase(columnLabel)) return columns.get(i);
        }
        throw new SQLException("Column not found: " + columnLabel);
    }

    // ------------------------------------------------------------------
    // Lifecycle
    // ------------------------------------------------------------------

    @Override public void close()     { closed = true; }
    @Override public boolean isClosed() { return closed; }
    @Override public Statement getStatement() { return statement; }

    // ------------------------------------------------------------------
    // Internal helpers
    // ------------------------------------------------------------------

    private Map<String, Object> currentRow() { return rows.get(cursor); }

    private String columnName(int index) throws SQLException {
        if (index < 1 || index > columns.size()) {
            throw new SQLException("Column index out of bounds: " + index);
        }
        return columns.get(index - 1);
    }

    private void checkOpen() throws SQLException {
        if (closed) throw new SQLException("ResultSet is closed");
    }

    private void checkRow() throws SQLException {
        if (cursor < 0 || cursor >= rows.size()) {
            throw new SQLException("No current row — call next() first");
        }
    }

    private static String  asString(Object o)  { return o == null ? null : o.toString(); }
    private static int     asInt(Object o)      { return o == null ? 0 : (o instanceof Number n ? n.intValue()    : Integer.parseInt(o.toString())); }
    private static long    asLong(Object o)     { return o == null ? 0L : (o instanceof Number n ? n.longValue()   : Long.parseLong(o.toString())); }
    private static double  asDouble(Object o)   { return o == null ? 0d : (o instanceof Number n ? n.doubleValue() : Double.parseDouble(o.toString())); }
    private static boolean asBoolean(Object o)  { return o != null && (o instanceof Boolean b ? b : Boolean.parseBoolean(o.toString())); }

    // ------------------------------------------------------------------
    // Unsupported / stub implementations required by the interface
    // ------------------------------------------------------------------

    @Override public void beforeFirst() throws SQLException { throw notSupported(); }
    @Override public void afterLast()   throws SQLException { throw notSupported(); }
    @Override public boolean first()    throws SQLException { throw notSupported(); }
    @Override public boolean last()     throws SQLException { throw notSupported(); }
    @Override public boolean absolute(int row)  throws SQLException { throw notSupported(); }
    @Override public boolean relative(int rows) throws SQLException { throw notSupported(); }
    @Override public boolean previous() throws SQLException { throw notSupported(); }
    @Override public void    setFetchDirection(int d) throws SQLException { /* no-op */ }
    @Override public int     getFetchDirection() { return FETCH_FORWARD; }
    @Override public void    setFetchSize(int rows) { /* no-op */ }
    @Override public int     getFetchSize()       { return 0; }
    @Override public int     getType()            { return TYPE_FORWARD_ONLY; }
    @Override public int     getConcurrency()     { return CONCUR_READ_ONLY; }
    @Override public int     getHoldability()     { return HOLD_CURSORS_OVER_COMMIT; }

    @Override public SQLWarning getWarnings()   { return null; }
    @Override public void clearWarnings()       { /* no-op */ }
    @Override public String getCursorName()     throws SQLException { throw notSupported(); }

    @Override public byte getByte(int i)              throws SQLException { return (byte) getInt(i); }
    @Override public short getShort(int i)            throws SQLException { return (short) getInt(i); }
    @Override public float getFloat(int i)            throws SQLException { return (float) getDouble(i); }
    @Override public BigDecimal getBigDecimal(int i, int s) throws SQLException { return BigDecimal.valueOf(getDouble(i)); }
    @Override public BigDecimal getBigDecimal(int i)  throws SQLException { return BigDecimal.valueOf(getDouble(i)); }
    @Override public BigDecimal getBigDecimal(String l) throws SQLException { return BigDecimal.valueOf(getDouble(l)); }
    @Override public byte getByte(String l)           throws SQLException { return (byte) getInt(l); }
    @Override public short getShort(String l)         throws SQLException { return (short) getInt(l); }
    @Override public float getFloat(String l)         throws SQLException { return (float) getDouble(l); }
    @Override public BigDecimal getBigDecimal(String l, int s) throws SQLException { return BigDecimal.valueOf(getDouble(l)); }
    @Override public byte[] getBytes(int i)           throws SQLException { return null; }
    @Override public byte[] getBytes(String l)        throws SQLException { return null; }
    @Override public Date getDate(int i)              throws SQLException { return null; }
    @Override public Date getDate(String l)           throws SQLException { return null; }
    @Override public Date getDate(int i, Calendar c)  throws SQLException { return null; }
    @Override public Date getDate(String l, Calendar c) throws SQLException { return null; }
    @Override public Time getTime(int i)              throws SQLException { return null; }
    @Override public Time getTime(String l)           throws SQLException { return null; }
    @Override public Time getTime(int i, Calendar c)  throws SQLException { return null; }
    @Override public Time getTime(String l, Calendar c) throws SQLException { return null; }
    @Override public Timestamp getTimestamp(int i)    throws SQLException { return null; }
    @Override public Timestamp getTimestamp(String l) throws SQLException { return null; }
    @Override public Timestamp getTimestamp(int i, Calendar c) throws SQLException { return null; }
    @Override public Timestamp getTimestamp(String l, Calendar c) throws SQLException { return null; }
    @Override public InputStream getAsciiStream(int i) throws SQLException { return null; }
    @Override public InputStream getUnicodeStream(int i) throws SQLException { return null; }
    @Override public InputStream getBinaryStream(int i)  throws SQLException { return null; }
    @Override public InputStream getAsciiStream(String l)  throws SQLException { return null; }
    @Override public InputStream getUnicodeStream(String l) throws SQLException { return null; }
    @Override public InputStream getBinaryStream(String l)  throws SQLException { return null; }
    @Override public Reader getCharacterStream(int i)  throws SQLException { return null; }
    @Override public Reader getCharacterStream(String l) throws SQLException { return null; }
    @Override public Object getObject(int i, Map<String,Class<?>> m) throws SQLException { return getObject(i); }
    @Override public Object getObject(String l, Map<String,Class<?>> m) throws SQLException { return getObject(l); }
    @Override public <T> T getObject(int i, Class<T> t) throws SQLException { return t.cast(getObject(i)); }
    @Override public <T> T getObject(String l, Class<T> t) throws SQLException { return t.cast(getObject(l)); }
    @Override public Ref getRef(int i)             throws SQLException { throw notSupported(); }
    @Override public Blob getBlob(int i)           throws SQLException { throw notSupported(); }
    @Override public Clob getClob(int i)           throws SQLException { throw notSupported(); }
    @Override public Array getArray(int i)         throws SQLException { throw notSupported(); }
    @Override public Ref getRef(String l)          throws SQLException { throw notSupported(); }
    @Override public Blob getBlob(String l)        throws SQLException { throw notSupported(); }
    @Override public Clob getClob(String l)        throws SQLException { throw notSupported(); }
    @Override public Array getArray(String l)      throws SQLException { throw notSupported(); }
    @Override public URL getURL(int i)             throws SQLException { throw notSupported(); }
    @Override public URL getURL(String l)          throws SQLException { throw notSupported(); }
    @Override public RowId getRowId(int i)         throws SQLException { throw notSupported(); }
    @Override public RowId getRowId(String l)      throws SQLException { throw notSupported(); }
    @Override public NClob getNClob(int i)         throws SQLException { throw notSupported(); }
    @Override public NClob getNClob(String l)      throws SQLException { throw notSupported(); }
    @Override public SQLXML getSQLXML(int i)       throws SQLException { throw notSupported(); }
    @Override public SQLXML getSQLXML(String l)    throws SQLException { throw notSupported(); }
    @Override public String getNString(int i)      throws SQLException { return getString(i); }
    @Override public String getNString(String l)   throws SQLException { return getString(l); }
    @Override public Reader getNCharacterStream(int i)  throws SQLException { return null; }
    @Override public Reader getNCharacterStream(String l) throws SQLException { return null; }

    // Mutation methods — not supported (read-only)
    @Override public boolean rowUpdated()  { return false; }
    @Override public boolean rowInserted() { return false; }
    @Override public boolean rowDeleted()  { return false; }
    @Override public void updateNull(int i)               throws SQLException { throw notSupported(); }
    @Override public void updateBoolean(int i, boolean v) throws SQLException { throw notSupported(); }
    @Override public void updateByte(int i, byte v)       throws SQLException { throw notSupported(); }
    @Override public void updateShort(int i, short v)     throws SQLException { throw notSupported(); }
    @Override public void updateInt(int i, int v)         throws SQLException { throw notSupported(); }
    @Override public void updateLong(int i, long v)       throws SQLException { throw notSupported(); }
    @Override public void updateFloat(int i, float v)     throws SQLException { throw notSupported(); }
    @Override public void updateDouble(int i, double v)   throws SQLException { throw notSupported(); }
    @Override public void updateBigDecimal(int i, BigDecimal v)  throws SQLException { throw notSupported(); }
    @Override public void updateString(int i, String v)          throws SQLException { throw notSupported(); }
    @Override public void updateBytes(int i, byte[] v)           throws SQLException { throw notSupported(); }
    @Override public void updateDate(int i, Date v)              throws SQLException { throw notSupported(); }
    @Override public void updateTime(int i, Time v)              throws SQLException { throw notSupported(); }
    @Override public void updateTimestamp(int i, Timestamp v)    throws SQLException { throw notSupported(); }
    @Override public void updateAsciiStream(int i, InputStream in, int l) throws SQLException { throw notSupported(); }
    @Override public void updateBinaryStream(int i, InputStream in, int l) throws SQLException { throw notSupported(); }
    @Override public void updateCharacterStream(int i, Reader r, int l) throws SQLException { throw notSupported(); }
    @Override public void updateObject(int i, Object v, int s)   throws SQLException { throw notSupported(); }
    @Override public void updateObject(int i, Object v)          throws SQLException { throw notSupported(); }
    @Override public void updateNull(String l)                   throws SQLException { throw notSupported(); }
    @Override public void updateBoolean(String l, boolean v)     throws SQLException { throw notSupported(); }
    @Override public void updateByte(String l, byte v)           throws SQLException { throw notSupported(); }
    @Override public void updateShort(String l, short v)         throws SQLException { throw notSupported(); }
    @Override public void updateInt(String l, int v)             throws SQLException { throw notSupported(); }
    @Override public void updateLong(String l, long v)           throws SQLException { throw notSupported(); }
    @Override public void updateFloat(String l, float v)         throws SQLException { throw notSupported(); }
    @Override public void updateDouble(String l, double v)       throws SQLException { throw notSupported(); }
    @Override public void updateBigDecimal(String l, BigDecimal v) throws SQLException { throw notSupported(); }
    @Override public void updateString(String l, String v)       throws SQLException { throw notSupported(); }
    @Override public void updateBytes(String l, byte[] v)        throws SQLException { throw notSupported(); }
    @Override public void updateDate(String l, Date v)           throws SQLException { throw notSupported(); }
    @Override public void updateTime(String l, Time v)           throws SQLException { throw notSupported(); }
    @Override public void updateTimestamp(String l, Timestamp v) throws SQLException { throw notSupported(); }
    @Override public void updateAsciiStream(String l, InputStream in, int length) throws SQLException { throw notSupported(); }
    @Override public void updateBinaryStream(String l, InputStream in, int length) throws SQLException { throw notSupported(); }
    @Override public void updateCharacterStream(String l, Reader r, int length) throws SQLException { throw notSupported(); }
    @Override public void updateObject(String l, Object v, int s) throws SQLException { throw notSupported(); }
    @Override public void updateObject(String l, Object v)        throws SQLException { throw notSupported(); }
    @Override public void insertRow()    throws SQLException { throw notSupported(); }
    @Override public void updateRow()    throws SQLException { throw notSupported(); }
    @Override public void deleteRow()    throws SQLException { throw notSupported(); }
    @Override public void refreshRow()   throws SQLException { throw notSupported(); }
    @Override public void cancelRowUpdates() throws SQLException { throw notSupported(); }
    @Override public void moveToInsertRow() throws SQLException { throw notSupported(); }
    @Override public void moveToCurrentRow() throws SQLException { throw notSupported(); }
    @Override public void updateRef(int i, Ref v)          throws SQLException { throw notSupported(); }
    @Override public void updateBlob(int i, Blob v)        throws SQLException { throw notSupported(); }
    @Override public void updateClob(int i, Clob v)        throws SQLException { throw notSupported(); }
    @Override public void updateArray(int i, Array v)      throws SQLException { throw notSupported(); }
    @Override public void updateRef(String l, Ref v)       throws SQLException { throw notSupported(); }
    @Override public void updateBlob(String l, Blob v)     throws SQLException { throw notSupported(); }
    @Override public void updateClob(String l, Clob v)     throws SQLException { throw notSupported(); }
    @Override public void updateArray(String l, Array v)   throws SQLException { throw notSupported(); }
    @Override public void updateRowId(int i, RowId v)      throws SQLException { throw notSupported(); }
    @Override public void updateRowId(String l, RowId v)   throws SQLException { throw notSupported(); }
    @Override public void updateNString(int i, String v)   throws SQLException { throw notSupported(); }
    @Override public void updateNString(String l, String v) throws SQLException { throw notSupported(); }
    @Override public void updateNClob(int i, NClob v)      throws SQLException { throw notSupported(); }
    @Override public void updateNClob(String l, NClob v)   throws SQLException { throw notSupported(); }
    @Override public void updateNCharacterStream(int i, Reader r, long l)   throws SQLException { throw notSupported(); }
    @Override public void updateNCharacterStream(String l, Reader r, long length) throws SQLException { throw notSupported(); }
    @Override public void updateAsciiStream(int i, InputStream in, long l)  throws SQLException { throw notSupported(); }
    @Override public void updateBinaryStream(int i, InputStream in, long l)  throws SQLException { throw notSupported(); }
    @Override public void updateCharacterStream(int i, Reader r, long l)    throws SQLException { throw notSupported(); }
    @Override public void updateAsciiStream(String l, InputStream in, long length)   throws SQLException { throw notSupported(); }
    @Override public void updateBinaryStream(String l, InputStream in, long length)  throws SQLException { throw notSupported(); }
    @Override public void updateCharacterStream(String l, Reader r, long length)     throws SQLException { throw notSupported(); }
    @Override public void updateBlob(int i, InputStream in, long l)  throws SQLException { throw notSupported(); }
    @Override public void updateBlob(String l, InputStream in, long length) throws SQLException { throw notSupported(); }
    @Override public void updateClob(int i, Reader r, long l)        throws SQLException { throw notSupported(); }
    @Override public void updateClob(String l, Reader r, long length) throws SQLException { throw notSupported(); }
    @Override public void updateNClob(int i, Reader r, long l)        throws SQLException { throw notSupported(); }
    @Override public void updateNClob(String l, Reader r, long length) throws SQLException { throw notSupported(); }
    @Override public void updateSQLXML(int i, SQLXML v)    throws SQLException { throw notSupported(); }
    @Override public void updateSQLXML(String l, SQLXML v) throws SQLException { throw notSupported(); }
    @Override public void updateAsciiStream(int i, InputStream in)    throws SQLException { throw notSupported(); }
    @Override public void updateBinaryStream(int i, InputStream in)   throws SQLException { throw notSupported(); }
    @Override public void updateCharacterStream(int i, Reader r)      throws SQLException { throw notSupported(); }
    @Override public void updateAsciiStream(String l, InputStream in)  throws SQLException { throw notSupported(); }
    @Override public void updateBinaryStream(String l, InputStream in) throws SQLException { throw notSupported(); }
    @Override public void updateCharacterStream(String l, Reader r)    throws SQLException { throw notSupported(); }
    @Override public void updateNCharacterStream(int i, Reader r)     throws SQLException { throw notSupported(); }
    @Override public void updateNCharacterStream(String l, Reader r)  throws SQLException { throw notSupported(); }

    @Override public <T> T unwrap(Class<T> i) throws SQLException {
        if (i.isInstance(this)) return i.cast(this);
        throw new SQLException("Not a wrapper for " + i);
    }
    @Override public boolean isWrapperFor(Class<?> i) { return i.isInstance(this); }

    private static SQLFeatureNotSupportedException notSupported() {
        return new SQLFeatureNotSupportedException("Operation not supported — ResultSet is forward-only read-only");
    }
}
