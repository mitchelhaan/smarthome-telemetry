# smarthome-telemetry

## Overview

- Collectors: gather data from a device and report it to the _aggregator_
- Aggregator: listens for data to be reported and writes it to the _database_
- Database: stores timestamped data for analysis and visualization

## Implementation Details

- Data format: JSON over MQTT
- Collectors: Python 3.7 using Paho MQTT
- MQTT broker: Google Cloud Pub/Sub
- Aggregator: Google Cloud Function (Python 3.7) that receives updates from the metric topic and sends the data to the database
- Database: InfluxDB
