#!/usr/bin/env python3
"""
resol2mqtt - Bridge between Resol solar thermal controllers and MQTT

Reads sensor data from Resol devices (KM1, KM2, DL2, DL2Plus, DL3, VBus)
and publishes to MQTT with hierarchical topics.
"""

import datetime
import json
import logging
import re
import time
import traceback

import requests

import iot_daemonize
import iot_daemonize.configuration as configuration

config = None
sensor_states = {}
detected_device_type = None


def detect_resol_device():
    """Auto-detect Resol device type.

    Returns True if the device was reachable (detection succeeded),
    False if the device was unreachable (network error, timeout).
    """
    global config, detected_device_type

    logging.info("Detecting Resol device type")

    url = f"http://{config.resol_host}:{config.resol_port}/cgi-bin/get_resol_device_information"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            text = response.text
            logging.info("Device information response: {}".format(text[:200]))

            product_match = re.search(r'product\s*=\s*["\']([^"\']+)["\']', text)
            if product_match:
                product = product_match.group(1).lower()
                logging.info("Detected product: {}".format(product))

                if 'km2' in product:
                    detected_device_type = 'km2'
                elif 'dl2plus' in product or 'dl2 plus' in product:
                    detected_device_type = 'dl2plus'
                elif 'dl3' in product:
                    detected_device_type = 'dl3'
                elif 'dl2' in product:
                    detected_device_type = 'dl2'
                else:
                    logging.info("Unknown product type: {}, defaulting to vbus".format(product))
                    detected_device_type = 'vbus'

                logging.info("Device type: {}".format(detected_device_type))
                return True

        logging.info("Device detection endpoint not available, assuming vbus device")
        detected_device_type = 'vbus'
        return True

    except requests.RequestException as e:
        logging.error(traceback.format_exc())
        return False


def fetch_data_km2_dl2plus():
    """Fetch data from KM2/DL2Plus using JSON-RPC 2.0"""
    global config

    url = f"http://{config.resol_host}:{config.resol_port}/cgi-bin/resol-webservice"
    headers = {"Content-Type": "application/json"}

    login_payload = json.dumps([{
        "id": "1",
        "jsonrpc": "2.0",
        "method": "login",
        "params": {
            "username": config.resol_username,
            "password": config.resol_password
        }
    }])

    logging.info("Logging in to KM2/DL2Plus device")
    response = requests.post(url, headers=headers, data=login_payload, timeout=30)
    response.raise_for_status()

    auth_response = response.json()
    if isinstance(auth_response, list) and len(auth_response) > 0:
        auth_result = auth_response[0].get("result", {})
        auth_id = auth_result.get("authId")

        if not auth_id:
            raise Exception("Failed to get authId from login response")

        logging.info("Logged in with authId: {}".format(auth_id))
    else:
        raise Exception("Unexpected login response format")

    data_payload = json.dumps([{
        "id": "1",
        "jsonrpc": "2.0",
        "method": "dataGetCurrentData",
        "params": {
            "authId": auth_id
        }
    }])

    logging.info("Fetching current data from KM2/DL2Plus device")
    response = requests.post(url, headers=headers, data=data_payload, timeout=30)
    response.raise_for_status()

    data_response = response.json()
    if isinstance(data_response, list) and len(data_response) > 0:
        return data_response[0].get("result", {})
    else:
        raise Exception("Unexpected data response format")


def fetch_data_dlx():
    """Fetch data from DL2/DL3 using HTTP GET"""
    global config

    url = f"http://{config.resol_host}:{config.resol_port}/dlx/download/live"

    params = {}
    if config.resol_username and config.resol_password:
        params["sessionAuthUsername"] = config.resol_username
        params["sessionAuthPassword"] = config.resol_password

    if config.resol_api_key:
        params["filter"] = config.resol_api_key

    logging.info("Fetching data from DL2/DL3 device")
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


def fetch_data_vbus():
    """Fetch data from VBus/KM1 via json-live-data-server"""
    global config

    url = f"http://{config.resol_host}:{config.resol_port}/api/v1/live-data"

    logging.info("Fetching data from VBus/KM1 json-live-data-server")
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.json()


def fetch_resol_data():
    """Fetch data from Resol device based on detected type"""
    global detected_device_type

    if detected_device_type in ('km2', 'dl2plus'):
        return fetch_data_km2_dl2plus()
    elif detected_device_type in ('dl2', 'dl3'):
        return fetch_data_dlx()
    elif detected_device_type == 'vbus':
        return fetch_data_vbus()
    else:
        raise Exception(f"Unsupported device type: {detected_device_type}")


def create_device_id(bus_dest, bus_src):
    """Generate device ID from bus addresses"""
    dest = str(bus_dest).replace(' ', '_').replace(':', '_').lower()
    src = str(bus_src).replace(' ', '_').replace(':', '_').lower()

    if dest and src and dest != 'unknown' and src != 'unknown':
        return f"{dest}_{src}"
    elif src and src != 'unknown':
        return src
    elif dest and dest != 'unknown':
        return dest
    else:
        return "unknown_device"


def format_sensor_value(value, unit):
    """Format sensor values"""
    if isinstance(value, float):
        return round(value, 2)

    if unit and 'date' in str(unit).lower():
        try:
            epoch_start = datetime.datetime(2001, 1, 1, 0, 0, 0)
            dt = epoch_start + datetime.timedelta(seconds=float(value))
            return dt.isoformat()
        except (ValueError, TypeError):
            pass

    return value


def parse_resol_response(response):
    """Parse Resol device response into normalized sensor data structure"""
    sensors = {}

    headers = response.get("headers", [])
    headersets = response.get("headersets", [])

    if not headers or not headersets:
        logging.info("No headers or headersets in response")
        return sensors

    if len(headersets) == 0:
        logging.info("No headersets available")
        return sensors

    headerset = headersets[0]
    packets = headerset.get("packets", [])

    for header_idx, header in enumerate(headers):
        if header_idx >= len(packets):
            logging.info("No packet data for header index {}".format(header_idx))
            continue

        packet = packets[header_idx]
        field_values = packet.get("field_values", [])

        bus_dest = header.get("destination_name", "unknown")
        bus_src = header.get("source_name", "unknown")
        device_id = create_device_id(bus_dest, bus_src)

        fields = header.get("fields", [])
        for field_idx, field in enumerate(fields):
            if field_idx >= len(field_values):
                logging.info("No field value for field index {}".format(field_idx))
                continue

            field_value = field_values[field_idx]
            raw_value = field_value.get("raw_value")

            if raw_value is None:
                continue

            sensor_name = field.get("name", "unknown").replace(" ", "_").lower()
            sensor_unit = field.get("unit_text", "").strip()

            formatted_value = format_sensor_value(raw_value, sensor_unit)

            header_id = header.get("id", f"header_{header_idx}")
            field_id = field.get("id", f"field_{field_idx}")
            unique_id = f"{header_id}_{field_id}"

            sensors[unique_id] = {
                "device_id": device_id,
                "name": sensor_name,
                "value": formatted_value,
                "unit": sensor_unit,
                "description": field.get("name", "")
            }

    return sensors


def publish_to_mqtt(device_id, sensor_name, value, unit=None):
    """Publish sensor data via framework MQTT client"""
    global config, sensor_states

    sensor_key = f"{device_id}/{sensor_name}"

    if sensor_key in sensor_states and sensor_states[sensor_key] == str(value):
        logging.info("Sensor {} value unchanged: {}".format(sensor_key, value))
        return

    sensor_states[sensor_key] = str(value)

    topic = f"{config.mqtt_topic}/{device_id}/{sensor_name}"

    iot_daemonize.mqtt_client.publish(topic, str(value))

    if unit and unit.strip():
        iot_daemonize.mqtt_client.publish(f"{topic}/unit", unit)


def polling_loop(stop):
    """Main polling loop as daemon task"""
    global config, detected_device_type

    # Device detection at startup
    if config.resol_device_type == 'auto':
        resol_detect_retries = int(config.resol_detect_retries or 10)
        resol_detect_retry_delay = int(config.resol_detect_retry_delay or 10)
        for attempt in range(1, resol_detect_retries + 1):
            logging.info("Device detection attempt {}/{}".format(attempt, resol_detect_retries))
            if detect_resol_device():
                break
            if attempt < resol_detect_retries:
                logging.info("Retrying device detection in {} seconds...".format(resol_detect_retry_delay))
                time.sleep(resol_detect_retry_delay)
            else:
                logging.error("Failed to detect Resol device after all retries, defaulting to vbus")
                detected_device_type = 'vbus'
    else:
        detected_device_type = config.resol_device_type
        logging.info("Using configured device type: {}".format(detected_device_type))

    retry_count = 0
    max_retries = 5
    retry_delay = 10
    scan_interval = int(config.scan_interval or 300)

    while not stop():
        try:
            logging.info("Fetching data from Resol device")
            raw_data = fetch_resol_data()

            sensors = parse_resol_response(raw_data)
            logging.info("Parsed {} sensors".format(len(sensors)))

            for _, sensor_data in sensors.items():
                publish_to_mqtt(
                    sensor_data["device_id"],
                    sensor_data["name"],
                    sensor_data["value"],
                    sensor_data["unit"]
                )

            retry_count = 0

            logging.info("Waiting {} seconds until next scan".format(scan_interval))
            time.sleep(scan_interval)

        except requests.RequestException as e:
            retry_count += 1
            logging.error(traceback.format_exc())

            if (isinstance(e, requests.HTTPError) and e.response is not None
                    and e.response.status_code == 404
                    and config.resol_device_type == 'auto'):
                logging.info("HTTP 404 with auto-detected device type '{}'"
                             " - re-running device detection".format(detected_device_type))
                if detect_resol_device():
                    logging.info("Device re-detected as: {}".format(detected_device_type))
                    retry_count = 0
                    continue

            if retry_count >= max_retries:
                logging.error("Max retries reached. Waiting for longer period...")
                time.sleep(retry_delay * 6)
                retry_count = 0
            else:
                time.sleep(retry_delay)

        except Exception as e:
            logging.error(traceback.format_exc())
            time.sleep(retry_delay)


def main():
    global config

    config = configuration.MqttDaemonConfiguration(
        program='resol2mqtt',
        description='Bridge between Resol devices and MQTT'
    )
    config.add_config_arg('mqtt_clientid', flags='--mqtt_clientid', default='resol2mqtt',
                         help='The MQTT client ID. Default is resol2mqtt.')
    config.add_config_arg('mqtt_topic', flags='--mqtt_topic', default='resol',
                         help='The MQTT base topic. Default is resol.')
    config.add_config_arg('config', flags=['-c', '--config'], default='/etc/resol2mqtt.conf',
                         help='Configuration file. Default is /etc/resol2mqtt.conf.')
    config.add_config_arg('resol_host', flags='--resol_host',
                         help='Resol device hostname or IP.')
    config.add_config_arg('resol_port', flags='--resol_port', default=80,
                         help='Resol device port. Default is 80.')
    config.add_config_arg('resol_username', flags='--resol_username', default='admin',
                         help='Resol device username. Default is admin.')
    config.add_config_arg('resol_password', flags='--resol_password', default='admin',
                         help='Resol device password. Default is admin.')
    config.add_config_arg('resol_api_key', flags='--resol_api_key', default='',
                         help='Resol API key for DL2/DL3 filter.')
    config.add_config_arg('resol_device_type', flags='--resol_device_type', default='auto',
                         help='Device type: auto, km2, dl2plus, dl2, dl3, vbus. Default is auto.')
    config.add_config_arg('resol_detect_retries', flags='--resol_detect_retries', default=10,
                         help='Max device detection retries. Default is 10.')
    config.add_config_arg('resol_detect_retry_delay', flags='--resol_detect_retry_delay', default=10,
                         help='Delay between detection retries in seconds. Default is 10.')
    config.add_config_arg('scan_interval', flags='--scan_interval', default=300,
                         help='Scan interval in seconds. Default is 300.')

    config.parse_args()
    config.parse_config(config.config)

    iot_daemonize.init(config, mqtt=True, daemonize=True)
    iot_daemonize.daemon.add_task(polling_loop)
    iot_daemonize.run()


if __name__ == "__main__":
    main()
