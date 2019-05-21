#!/usr/bin/env python3.7
import datetime
import json
import jwt
import logging
import schedule
import ssl
import time
import paho.mqtt.client as mqtt

from config import Config

from epsolar_tracer.collector import (
    collect as epsolar_tracer_collect,
    sync_rtc as epsolar_tracer_sync_rtc,
)


def get_json_web_token(config: Config):
    """Generate a JSON web token (jwt) used for device authentication to Google Cloud IoT"""
    token = {
        # The time that the token was issued at
        "iat": datetime.datetime.utcnow(),
        # The time the token expires
        "exp": datetime.datetime.utcnow()
        + datetime.timedelta(minutes=config.jwt_lifetime_minutes),
        # The audience field should always be set to the GCP project id
        "aud": config.project_id,
    }
    with open(config.jwt_private_key, "r") as f:
        private_key = f.read()

    return jwt.encode(token, private_key, algorithm=config.jwt_algorithm)


def get_mqtt_client(config: Config) -> mqtt.Client:
    """Create an mqtt client instance and initiate connection"""

    # Google Cloud IoT Core expects the device ID to be in this specific format
    client_id = f"projects/{config.project_id}/locations/{config.cloud_region}/registries/{config.registry_id}/devices/{config.device_id}"

    # Set userdata to our configuration object for use in callbacks
    mqtt_client = mqtt.Client(client_id=client_id, userdata=config)
    mqtt_client.tls_set(ca_certs=config.mqtt_ca_certs, tls_version=ssl.PROTOCOL_TLSv1_2)

    mqtt_client.enable_logger()
    mqtt_client.on_connect = on_mqtt_connect

    # Connect to the Google MQTT bridge
    refresh_mqtt_client_token(config, mqtt_client)
    mqtt_client.connect_async(config.mqtt_bridge_hostname, config.mqtt_bridge_port)

    return mqtt_client


def refresh_mqtt_client_token(config: Config, mqtt_client: mqtt.Client):
    # With Google Cloud IoT Core, the username field is ignored, and the password field is used to transmit a JSON web token
    mqtt_client.username_pw_set("unused", password=get_json_web_token(config))


def on_mqtt_connect(client: mqtt.Client, config: Config, flags, rc):
    """The callback for when the client receives a CONNACK response from the server"""
    logger.debug(f"on_mqtt_connect() flags = {flags}, rc = {rc}")

    # This is the topic that the device will receive configuration updates on
    mqtt_config_topic = f"/devices/{config.device_id}/config"
    logger.debug(f"Subscribing to {mqtt_config_topic}")

    client.message_callback_add(mqtt_config_topic, on_mqtt_config_message)
    client.subscribe(mqtt_config_topic, qos=1)

    # The topic that the device will receive commands on
    mqtt_command_topic = f"/devices/{config.device_id}/commands/#"
    logger.debug(f"Subscribing to {mqtt_command_topic}")

    client.message_callback_add(mqtt_command_topic, on_mqtt_command_message)
    client.subscribe(mqtt_command_topic, qos=1)


def on_mqtt_config_message(client, config, message):
    """Handle config messages"""
    logger.debug(f"on_mqtt_config_message: {message}")


def on_mqtt_command_message(client, config, message):
    """Handle command messages"""
    logger.debug(f"on_mqtt_command_message: {message}")


def perform_and_upload_collection(collect_fn, config: Config, mqtt_client: mqtt.Client):
    collection = collect_fn()
    mqtt_client.publish(
        f"/devices/{config.device_id}/events", json.dumps(collection), qos=1
    )


def main():
    config = Config()

    mqtt_client = get_mqtt_client(config)
    mqtt_client.loop_start()

    # jwt needs to be refreshed before it expires
    # the client will be disconnected by the server after expiration and it will auto-reconnect with the new jwt
    schedule.every(config.jwt_lifetime_minutes).minutes.do(
        refresh_mqtt_client_token, config, mqtt_client
    )

    schedule.every().day.do(epsolar_tracer_sync_rtc)
    schedule.every().minute.do(
        perform_and_upload_collection, epsolar_tracer_collect, config, mqtt_client
    )

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)

    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

if __name__ == "__main__":
    main()
