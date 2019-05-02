import base64
from datetime import datetime
from enum import Enum
import json
import os

from influxdb import InfluxDBClient


class SslConfig(Enum):
    DISABLED = "False"
    NO_VERIFY = "NoVerify"
    ENABLED = "True"


ssl_config = SslConfig(os.environ.get("INFLUXDB_SSL", "False"))

if ssl_config is SslConfig.NO_VERIFY:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

influx_options = {
    "host": os.environ.get("INFLUXDB_HOST"),
    "port": os.environ.get("INFLUXDB_PORT", 8086),
    "ssl": ssl_config is not SslConfig.DISABLED,
    "verify_ssl": ssl_config is SslConfig.ENABLED,
    "username": os.environ.get("INFLUXDB_USERNAME"),
    "password": os.environ.get("INFLUXDB_PASSWORD"),
    "database": os.environ.get("INFLUXDB_DATABASE"),
}


def smarthome_telemetry_aggregator(event, context):
    client = InfluxDBClient(**influx_options)

    # Messages coming from PubSub will have the data base64 encoded in event['data']
    if "data" in event:
        data = json.loads(base64.b64decode(event["data"]).decode("utf-8"))
    else:
        data = event

    # InfluxDB client expects a list of data points
    if type(data) is not list:
        data = [data]

    # In the future, this could process/transform data. For now, we're just relaying it to InfluxDB.
    client.write_points(data)
