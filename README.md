# resol2mqtt

A standalone Python bridge that reads sensor data from Resol solar thermal system controllers and publishes it to MQTT.

## Features

- **Universal Resol Device Support**: Works with KM1, KM2, DL2, DL2Plus, DL3, VBus/LAN, and VBus/USB devices
- **Automatic Device Detection**: Automatically identifies device type and uses the appropriate protocol
- **MQTT Publishing**: Publishes sensor data to hierarchical MQTT topics
- **State Tracking**: Avoids duplicate MQTT publishes when values haven't changed
- **Flexible Deployment**: Docker, native Python, systemd, or supervisor
- **TLS/SSL Support**: Secure MQTT connections with certificate verification
- **Configurable**: JSON configuration file with comprehensive options
- **Robust Error Handling**: Connection retry logic with graceful degradation
- **MQTT Connection Resilience**: Automatic reconnection with circuit breaker pattern
- **Fail-Fast Startup**: Exits cleanly if MQTT broker is unavailable for systemd restart
- **Minimal Dependencies**: Only paho-mqtt and requests

## Supported Resol Devices

| Device Type | Protocol | Port | Notes |
|------------|----------|------|-------|
| KM2 | JSON-RPC 2.0 | 80 | Modern controllers |
| DL2Plus | JSON-RPC 2.0 | 80 | Data loggers |
| DL2 | HTTP GET | 80 | Data loggers |
| DL3 | HTTP GET | 80 | Data loggers |
| KM1 | HTTP GET | 3333 | Requires json-live-data-server |
| VBus/LAN | HTTP GET | 3333 | Requires json-live-data-server |
| VBus/USB | HTTP GET | 3333 | Requires json-live-data-server |

### Note on VBus/KM1 Devices

VBus/LAN, VBus/USB, and KM1 devices require an external **json-live-data-server** to be running. This is a community-maintained Node.js application that provides an HTTP API for VBus data. See the [resol-vbus repository](https://github.com/danielwippermann/resol-vbus) for setup instructions.

## Requirements

- Python 3.9 or higher
- MQTT broker (e.g., Mosquitto)
- Resol device on the same network

## Installation

### Docker (Recommended)

```bash
docker build -t resol2mqtt .
docker run -d \
  --name resol2mqtt \
  -v /path/to/resol2mqtt.conf:/etc/resol2mqtt.conf \
  resol2mqtt
```

### Native Installation

```bash
# Clone or copy the repository
cd /usr/local/lib
git clone <repository-url> resol2mqtt
cd resol2mqtt

# Run the installation script
./install

# Copy and edit the configuration file
cp resol2mqtt.conf.example /etc/resol2mqtt.conf
nano /etc/resol2mqtt.conf
```

### Systemd Service

```bash
# Copy the service file
sudo cp systemd/resol2mqtt.service /etc/systemd/system/

# Enable and start the service
sudo systemctl enable resol2mqtt
sudo systemctl start resol2mqtt

# Check status
sudo systemctl status resol2mqtt
```

### Supervisor

```bash
# Copy the supervisor config
sudo cp supervisor/resol2mqtt.conf /etc/supervisor/conf.d/

# Update supervisor
sudo supervisorctl reread
sudo supervisorctl update

# Start the service
sudo supervisorctl start resol2mqtt
```

## Configuration

Configuration is done via a JSON file, typically located at `/etc/resol2mqtt.conf`. See `resol2mqtt.conf.example` for a complete template.

### MQTT Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `mqtt_host` | `localhost` | MQTT broker hostname or IP |
| `mqtt_port` | `1883` | MQTT broker port |
| `mqtt_keepalive` | `300` | MQTT keepalive interval in seconds |
| `mqtt_clientid` | `resol2mqtt` | MQTT client identifier |
| `mqtt_user` | `` | MQTT username (optional) |
| `mqtt_password` | `` | MQTT password (optional) |
| `mqtt_topic` | `resol` | MQTT base topic |
| `mqtt_tls` | `false` | Enable TLS/SSL |
| `mqtt_tls_version` | `TLSv1.2` | TLS version (TLSv1, TLSv1.1, TLSv1.2) |
| `mqtt_verify_mode` | `CERT_REQUIRED` | Certificate verification (CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED) |
| `mqtt_ssl_ca_path` | `` | Path to CA certificate file |
| `mqtt_tls_no_verify` | `false` | Disable hostname verification |
| `mqtt_connect_timeout` | `30` | Connection timeout in seconds |
| `mqtt_connect_retries` | `5` | Max connection retry attempts at startup |
| `mqtt_connect_retry_delay` | `5` | Delay between connection retries in seconds |
| `mqtt_reconnect_check_interval` | `30` | Interval to check for reconnection when circuit breaker active |

### Resol Device Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `resol_host` | *required* | Resol device hostname or IP |
| `resol_port` | `80` | Resol device port (3333 for VBus/KM1) |
| `resol_username` | `admin` | Device username |
| `resol_password` | `admin` | Device password |
| `resol_api_key` | `` | DL2/DL3 filter/API key (optional) |
| `resol_device_type` | `auto` | Device type: auto, km2, dl2plus, dl2, dl3, vbus |

### Application Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `scan_interval` | `300` | Data polling interval in seconds |
| `timestamp` | `false` | Publish timestamp with sensor data |
| `verbose` | `false` | Enable verbose logging |

### Example Configuration

```json
{
  "mqtt_host": "192.168.1.50",
  "mqtt_port": "1883",
  "mqtt_clientid": "resol2mqtt",
  "mqtt_topic": "solar",
  "resol_host": "192.168.1.100",
  "resol_port": "80",
  "resol_username": "admin",
  "resol_password": "mypassword",
  "scan_interval": "300",
  "verbose": "false"
}
```

## MQTT Topic Structure

Sensor data is published to hierarchical topics in the format:

```
{mqtt_topic}/{device_id}/{sensor_name}
```

### Examples

```
resol/vbus_controller_dfa/temperature_sensor_1 → 45.2
resol/vbus_controller_dfa/temperature_sensor_2 → 38.7
resol/vbus_controller_dfa/flow_rate → 12.5
resol/vbus_controller_dfa/operating_hours → 12345
resol/vbus_controller_dfa/power → 2500
```

### Optional Topics

If enabled in configuration:

```
resol/vbus_controller_dfa/temperature_sensor_1/unit → °C
resol/vbus_controller_dfa/temperature_sensor_1/timestamp → 1704902400.123
```

### Device ID Format

The `device_id` is automatically generated from the VBus source and destination addresses. For example:
- Source: "VBus Controller DFA"
- Destination: "Solar Module"
- Device ID: `solar_module_vbus_controller_dfa`

## MQTT Connection Resilience

resol2mqtt implements robust connection handling to ensure reliable operation:

### Startup Behavior

- **Connection Retry**: At startup, resol2mqtt attempts to connect to the MQTT broker with configurable retry logic
- **Fail-Fast**: If the MQTT broker is unavailable after all retries, the application exits cleanly
- **Systemd Integration**: When deployed with systemd, the service automatically restarts after a delay, eliminating the need for manual intervention

### Runtime Behavior

- **Automatic Reconnection**: If the MQTT connection is lost during operation, the Paho MQTT library automatically attempts to reconnect in the background
- **Circuit Breaker**: When disconnected, polling of the Resol device is paused to conserve resources and avoid collecting data that cannot be published
- **Automatic Recovery**: Once the MQTT connection is restored, the circuit breaker deactivates and normal polling resumes immediately
- **Data Loss Handling**: Data collected during disconnection is not queued or buffered - the application accepts temporary data loss for simplicity and memory efficiency

### Connection State Logging

The application provides clear logging of connection state changes:
- Initial connection attempts and success/failure
- Unexpected disconnections with reason codes
- Circuit breaker activation (polling paused)
- Reconnection success (polling resumed)
- Failed publish attempts when disconnected

This approach ensures the application is self-healing and requires minimal manual intervention, making it suitable for production IoT deployments.

## Usage

### Running Manually

```bash
# Using the run script (with venv)
./run

# Or directly with Python
python3 resol2mqtt

# With custom config file
python3 resol2mqtt --config /path/to/config.json

# With verbose logging
python3 resol2mqtt --verbose
```

### Command-Line Options

All configuration options can be specified via command-line arguments:

```bash
python3 resol2mqtt \
  --mqtt-host 192.168.1.50 \
  --mqtt-port 1883 \
  --resol-host 192.168.1.100 \
  --scan-interval 300 \
  --verbose
```

Configuration file values take precedence over command-line defaults.

## License

BSD-3-Clause License. See LICENSE.md for details.
