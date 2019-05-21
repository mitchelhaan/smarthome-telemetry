from dataclasses import dataclass
import os


@dataclass
class Config:
    mqtt_bridge_hostname: str = "mqtt.googleapis.com"
    mqtt_bridge_port: int = 8883
    mqtt_ca_certs: str = os.path.join(
        os.path.dirname(__file__), "google_mqtt_roots.pem"
    )

    project_id: str = "<some-project-id>"
    cloud_region: str = "<some-cloud-region>"
    registry_id: str = "<some-registry-id>"
    device_id: str = "<some-device-id>"

    jwt_algorithm: str = "ES256"
    jwt_lifetime_minutes: int = 60
    jwt_private_key: str = os.path.join(os.path.dirname(__file__), f"{device_id}.pem")
