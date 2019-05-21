#!/usr/bin/env python3.7
import datetime
from enum import Enum
import logging

from .registers import *
from .client import EpsolarTracerClient


class ChargingMode(Enum):
    Off = 0
    Float = 1
    MPPT = 2
    Equalization = 3

    def parse(charging_equipment_status):
        return ChargingMode((int(charging_equipment_status) & 0x000C) >> 2)


def _collect_values(client):
    return {
        "pv_voltage": float(client.read_register(RealtimeData.PvArrayInputVoltage)),
        "pv_current": float(client.read_register(RealtimeData.PvArrayInputCurrent)),
        "pv_power": float(client.read_register(RealtimeData.PvArrayInputPower)),
        "battery_voltage": float(client.read_register(RealtimeData.BatteryVoltage)),
        "battery_temperature": float(
            client.read_register(RealtimeData.BatteryTemperature)
        ),
        "generated_today": float(
            client.read_register(StatisticalParameter.GeneratedEnergyToday)
        ),
        "generated_total": float(
            client.read_register(StatisticalParameter.TotalGeneratedEnergy)
        ),
        "charging_mode": ChargingMode.parse(
            client.read_register(RealtimeStatus.ChargingEquipmentStatus)
        ).name,
    }


def sync_rtc():
    EpsolarTracerClient().sync_rtc()


def collect():
    logger = logging.getLogger("epsolar_tracer_collect")
    client = EpsolarTracerClient()
    device_info = client.read_device_info()

    results = _collect_values(client)

    return {
        "measurement": "solar_controller",
        "time": datetime.datetime.utcnow().isoformat("T") + "Z",
        "tags": {"type": "epsolar_tracer", "model": device_info["model"]},
        "fields": results,
    }


if __name__ == "__main__":
    logging.basicConfig()
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    sync_rtc()
    print(collect())
