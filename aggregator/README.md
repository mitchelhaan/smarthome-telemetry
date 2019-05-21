# aggregator

This aggregator is a Python script intended to be run as a Google Cloud Function. It receives messages from a Cloud Pub/Sub topic and relays them to InfluxDB.

InfluxDB example JSON schema:

```json
{
    "measurement": "test",
    "tags": {
        "type": "electric",
        "id": "1234567890"
    },
    "time": "2019-05-03T23:25:43.511Z",
    "fields": {
        "rate": 0.1,
        "usage": 12,
        "cost": 1.2
    }
}
```