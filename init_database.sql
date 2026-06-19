-- Schema and seed data for the IoT device diagnosis agent.

CREATE TABLE devices (
    device_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    gateway_id TEXT NOT NULL,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE gateways (
    gateway_id TEXT PRIMARY KEY,
    region TEXT NOT NULL
);

-- Latest sensor reading per device (telemetry store, TimescaleDB-style).
CREATE TABLE sensor_readings (
    reading_id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    status TEXT NOT NULL,            -- 'online' | 'offline' | 'error'
    temperature_c NUMERIC,
    battery_pct NUMERIC,
    recorded_at TIMESTAMPTZ NOT NULL
);

-- Latest gateway status per gateway.
CREATE TABLE gateway_status (
    status_id BIGSERIAL PRIMARY KEY,
    gateway_id TEXT NOT NULL REFERENCES gateways(gateway_id),
    status TEXT NOT NULL,            -- 'online' | 'offline' | 'error'
    uplink_ok BOOLEAN,
    recorded_at TIMESTAMPTZ NOT NULL
);

-- Durable record of every diagnosis produced by the agent.
CREATE TABLE diagnosis_log (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    overall_status TEXT,             -- 'complete' | 'degraded' | 'unknown'
    data_complete BOOLEAN,
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sensor_device_time ON sensor_readings(device_id, recorded_at DESC);
CREATE INDEX idx_gwstatus_gw_time ON gateway_status(gateway_id, recorded_at DESC);
CREATE INDEX idx_diaglog_trace ON diagnosis_log(trace_id);

-- Gateways
INSERT INTO gateways (gateway_id, region) VALUES
    ('gw-001', 'us-east'),
    ('gw-002', 'eu-west'),
    ('gw-003', 'ap-south');

-- Devices
INSERT INTO devices (device_id, model, gateway_id) VALUES
    ('dev-100', 'TempSense-X1', 'gw-001'),
    ('dev-200', 'TempSense-X1', 'gw-002'),
    ('dev-300', 'FlowMeter-Z2', 'gw-003');

-- Healthy, fresh case: dev-100 has a recent online reading and an online gateway.
INSERT INTO sensor_readings (device_id, status, temperature_c, battery_pct, recorded_at) VALUES
    ('dev-100', 'online', 22.4, 88, now() - interval '30 seconds');
INSERT INTO gateway_status (gateway_id, status, uplink_ok, recorded_at) VALUES
    ('gw-001', 'online', true, now() - interval '20 seconds');

-- Partial-failure case: dev-200 has a fresh online sensor reading,
-- but its gateway (gw-002) is reporting offline.
INSERT INTO sensor_readings (device_id, status, temperature_c, battery_pct, recorded_at) VALUES
    ('dev-200', 'online', 23.1, 75, now() - interval '40 seconds');
INSERT INTO gateway_status (gateway_id, status, uplink_ok, recorded_at) VALUES
    ('gw-002', 'offline', false, now() - interval '25 seconds');

-- Stale case: dev-300 has only an old sensor reading and an old gateway status.
INSERT INTO sensor_readings (device_id, status, temperature_c, battery_pct, recorded_at) VALUES
    ('dev-300', 'online', 19.8, 60, now() - interval '2 hours');
INSERT INTO gateway_status (gateway_id, status, uplink_ok, recorded_at) VALUES
    ('gw-003', 'online', true, now() - interval '3 hours');

