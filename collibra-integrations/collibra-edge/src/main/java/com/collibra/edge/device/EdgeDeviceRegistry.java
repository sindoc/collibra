package com.collibra.edge.device;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Collection;
import java.util.Collections;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Thread-safe registry of all {@link EdgeDevice} instances known to this edge node.
 *
 * <p>The registry is the single source of truth for device discovery.  The
 * {@link com.collibra.edge.query.EdgeQueryEngine} looks up devices here before
 * routing a query.  A background health-checker (not shown) can update device
 * {@link EdgeDevice.ConnectionStatus} entries at runtime.
 */
public class EdgeDeviceRegistry {

    private static final Logger log = LoggerFactory.getLogger(EdgeDeviceRegistry.class);

    private final Map<UUID, EdgeDevice> devices = new ConcurrentHashMap<>();

    /**
     * Registers a new edge device.
     *
     * @param device the device to register
     * @throws IllegalStateException if a device with the same ID is already registered
     */
    public void register(EdgeDevice device) {
        if (devices.putIfAbsent(device.getDeviceId(), device) != null) {
            throw new IllegalStateException(
                    "Device already registered: " + device.getDeviceId());
        }
        log.info("Registered edge device: {}", device);
    }

    /**
     * Removes a device from the registry.
     *
     * @param deviceId the UUID of the device to deregister
     * @return {@code true} if the device was present and removed
     */
    public boolean deregister(UUID deviceId) {
        boolean removed = devices.remove(deviceId) != null;
        if (removed) log.info("Deregistered edge device: {}", deviceId);
        return removed;
    }

    public Optional<EdgeDevice> find(UUID deviceId) {
        return Optional.ofNullable(devices.get(deviceId));
    }

    /**
     * Finds the first device whose name matches (case-insensitive).
     */
    public Optional<EdgeDevice> findByName(String name) {
        return devices.values().stream()
                .filter(d -> d.getDeviceName().equalsIgnoreCase(name))
                .findFirst();
    }

    /** Returns all registered devices of a given type. */
    public Collection<EdgeDevice> findByType(EdgeDevice.DeviceType type) {
        return devices.values().stream()
                .filter(d -> d.getDeviceType() == type)
                .toList();
    }

    /** Returns all registered devices. */
    public Collection<EdgeDevice> all() {
        return Collections.unmodifiableCollection(devices.values());
    }

    public int size() { return devices.size(); }
}
