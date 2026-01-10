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

## Data Types

The bridge publishes various sensor types from Resol devices:

| Type | Unit | Example |
|------|------|---------|
| Temperature | °C | 45.2 |
| Power | W | 2500 |
| Energy | Wh | 12345 |
| Flow Rate | l/h | 12.5 |
| Pressure | bar | 1.5 |
| Humidity | %RH | 65 |
| Operating Time | s | 3600 |
| Percentage | % | 85 |
| Date/Time | ISO 8601 | 2026-01-10T12:34:56 |

### Date Handling

Resol devices use an epoch starting at 2001-01-01. The bridge automatically converts these timestamps to ISO 8601 format.

## Troubleshooting

### Device Detection Fails

If automatic device detection fails:

1. Check network connectivity to the Resol device
2. Verify the device is accessible via HTTP
3. Manually specify device type in configuration:
   ```json
   "resol_device_type": "km2"
   ```

### Connection Errors

The bridge includes retry logic:
- Retries up to 5 times with 10-second delays
- After max retries, waits 60 seconds and resets counter
- Continues indefinitely until connection is restored

Check logs for specific error messages:

```bash
# Systemd logs
sudo journalctl -u resol2mqtt -f

# Supervisor logs
sudo tail -f /var/log/resol2mqtt/main.log

# Manual run with verbose logging
python3 resol2mqtt --verbose
```

### VBus/KM1 Devices Not Working

For VBus/LAN, VBus/USB, and KM1 devices:

1. Ensure json-live-data-server is running
2. Default port is 3333, configure accordingly:
   ```json
   "resol_port": "3333"
   ```
3. Test the endpoint manually:
   ```bash
   curl http://192.168.1.100:3333/api/v1/live-data
   ```

### No Data Published

1. Check MQTT broker connection:
   ```bash
   mosquitto_sub -h localhost -t "resol/#" -v
   ```
2. Enable verbose logging to see data fetching details
3. Verify device credentials are correct
4. Check scan_interval is not too long

### Authentication Issues

For KM2/DL2Plus/DL2/DL3 devices:
- Default username is usually "admin"
- Default password is usually "admin"
- Some devices may have custom credentials

For DL2/DL3 with API key filtering:
- Set `resol_api_key` to your filter ID
- Contact device administrator for the key

## Integration Examples

### Home Assistant

Subscribe to MQTT topics in Home Assistant:

```yaml
mqtt:
  sensor:
    - name: "Solar Temperature 1"
      state_topic: "resol/vbus_controller_dfa/temperature_sensor_1"
      unit_of_measurement: "°C"
      device_class: temperature

    - name: "Solar Power"
      state_topic: "resol/vbus_controller_dfa/power"
      unit_of_measurement: "W"
      device_class: power
```

### Node-RED

Use MQTT input nodes to subscribe to `resol/#` and process the data.

### Grafana + InfluxDB

Use Telegraf MQTT consumer to store sensor data:

```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://localhost:1883"]
  topics = ["resol/#"]
  data_format = "value"
  data_type = "float"
```

## Development

### Project Structure

```
resol2mqtt/
├── resol2mqtt           # Main executable script
├── resol2mqtt.conf.example
├── requirements.txt
├── Dockerfile
├── install              # Installation script
├── run                  # Execution wrapper
├── systemd/             # Systemd integration
├── supervisor/          # Supervisor integration
└── README.md
```

### Architecture

- **Single-file application**: All logic in one Python script
- **Global state**: Module-level variables for MQTT client and configuration
- **Callback-driven**: MQTT events handled via callbacks
- **Polling loop**: Fetches data at configured intervals
- **State tracking**: Avoids duplicate MQTT publishes

## Contributing

Contributions are welcome! Please ensure:
- Code follows the existing style (similar to knx2mqtt)
- Error handling includes proper logging
- Configuration options are documented

## License

BSD-3-Clause License. See LICENSE.md for details.

## Acknowledgments

- Inspired by [knx2mqtt](https://github.com/gbeine/knx2mqtt) architecture
- Based on [hass-Deltasol-KM2](https://github.com/dm82m/hass-Deltasol-KM2) protocol implementation
- Uses [paho-mqtt](https://github.com/eclipse/paho.mqtt.python) for MQTT communication
- Resol VBus protocol information from [resol-vbus](https://github.com/danielwippermann/resol-vbus)
