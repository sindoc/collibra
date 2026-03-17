package com.collibra.edge.device;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Represents a physical or logical edge device/data source that exposes data
 * queryable through the Collibra edge query engine.
 *
 * <p>Examples of edge devices in a Collibra integration context:
 * <ul>
 *   <li>An IoT sensor stream publishing to a local MQTT broker</li>
 *   <li>An on-premise database reachable only from the edge node</li>
 *   <li>A CSV/Parquet file available on local disk, S3, or Dropbox</li>
 *   <li>A REST micro-service endpoint at the network edge</li>
 * </ul>
 *
 * Devices register themselves with the {@link EdgeDeviceRegistry} and are
 * then queryable via the {@link com.collibra.edge.query.EdgeQueryEngine}.
 */
public class EdgeDevice {

    public enum DeviceType {
        /** JDBC-accessible relational database (MySQL, PostgreSQL, etc.) */
        JDBC_DATABASE,
        /** File on local filesystem, S3, or Dropbox */
        FILE_SOURCE,
        /** REST / HTTP API endpoint */
        REST_API,
        /** MQTT / message-broker stream */
        MQTT_STREAM,
        /** Generic custom source */
        CUSTOM
    }

    public enum ConnectionStatus { UNKNOWN, ONLINE, OFFLINE, DEGRADED }

    private final UUID         deviceId;
    private final String       deviceName;
    private final DeviceType   deviceType;
    private final String       connectionString;
    private final Map<String, String> properties;
    private volatile ConnectionStatus status;

    private EdgeDevice(Builder b) {
        this.deviceId         = b.deviceId != null ? b.deviceId : UUID.randomUUID();
        this.deviceName       = b.deviceName;
        this.deviceType       = b.deviceType;
        this.connectionString = b.connectionString;
        this.properties       = Collections.unmodifiableMap(new LinkedHashMap<>(b.properties));
        this.status           = ConnectionStatus.UNKNOWN;
    }

    public UUID              getDeviceId()         { return deviceId; }
    public String            getDeviceName()        { return deviceName; }
    public DeviceType        getDeviceType()        { return deviceType; }
    public String            getConnectionString()  { return connectionString; }
    public Map<String,String> getProperties()       { return properties; }
    public ConnectionStatus  getStatus()            { return status; }
    public void              setStatus(ConnectionStatus s) { this.status = s; }

    @Override
    public String toString() {
        return "EdgeDevice{id=" + deviceId + ", name='" + deviceName +
               "', type=" + deviceType + ", status=" + status + '}';
    }

    public static Builder builder(String deviceName, DeviceType type) {
        return new Builder(deviceName, type);
    }

    public static final class Builder {
        private UUID       deviceId;
        private final String deviceName;
        private final DeviceType deviceType;
        private String     connectionString = "";
        private final Map<String, String> properties = new LinkedHashMap<>();

        private Builder(String deviceName, DeviceType deviceType) {
            this.deviceName = deviceName;
            this.deviceType = deviceType;
        }

        public Builder deviceId(UUID id)              { this.deviceId = id; return this; }
        public Builder connectionString(String cs)    { this.connectionString = cs; return this; }
        public Builder property(String k, String v)  { this.properties.put(k, v); return this; }

        public EdgeDevice build() {
            if (deviceName == null || deviceName.isBlank()) {
                throw new IllegalArgumentException("deviceName must not be blank");
            }
            return new EdgeDevice(this);
        }
    }
}
