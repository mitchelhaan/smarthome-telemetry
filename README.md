# smarthome-telemetry

## Overview

- Collectors: gather data from a device and report it to the _aggregator_
- Aggregator: listens for data to be reported and writes it to the _database_
- Database: stores timestamped data for analysis and visualization

## Implementation Details

- Data format: JSON over MQTT - structure TBD
- Collectors: can be written in any language that can upload data points in JSON format via MQTT (Python 3.7)
- Aggregator: Google Cloud Function that subscribes to the metric topic and sends the data to the database (Python 3.7)
- Database: InfluxDB
