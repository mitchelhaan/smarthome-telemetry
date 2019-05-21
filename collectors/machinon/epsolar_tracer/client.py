from collections import defaultdict
import datetime
import logging
from typing import Dict, Callable

from pymodbus.register_read_message import (
    ReadInputRegistersResponse,
    ReadHoldingRegistersResponse,
)
from pymodbus.mei_message import ReadDeviceInformationRequest
from pymodbus.client.sync import BaseModbusClient, ModbusSerialClient as ModbusClient

from .registers import Register, RegisterType, RegisterValue, SettingParameter


def unsupported_register_type(*args, **kwargs):
    raise Exception("Unsupported register type for operation")


class EpsolarTracerClient:
    def __init__(self, modbus_client: BaseModbusClient = None, unit: int = 1):
        self.logger = logging.getLogger(__name__)
        self.unit = unit
        self.modbus_client = modbus_client or ModbusClient(
            method="rtu", port="/dev/serial485", baudrate=115200
        )

        client = self.modbus_client

        self._read_helpers: Dict[Callable] = defaultdict(unsupported_register_type)
        self._read_helpers[RegisterType.COIL] = client.read_coils
        self._read_helpers[RegisterType.DISCRETE] = client.read_discrete_inputs
        self._read_helpers[RegisterType.INPUT] = client.read_input_registers
        self._read_helpers[RegisterType.HOLDING] = client.read_holding_registers

        self._write_helpers: Dict[Callable] = defaultdict(unsupported_register_type)
        self._write_helpers[RegisterType.COIL] = client.write_coils
        self._write_helpers[RegisterType.HOLDING] = client.write_registers

    def read_register(self, register: Register) -> RegisterValue:
        helper = self._read_helpers[register.type]
        value = helper(register.address, register.size, unit=self.unit)
        return register.decode(value)

    def write_register(self, register: Register, value):
        self.logger.debug(f"write_register value: {value}")
        values = register.encode(value)
        self.logger.debug(f"write_register encoded values: {values}")
        helper = self._write_helpers[register.type]
        helper(register.address, values, unit=self.unit)

    def read_device_info(self):
        response = self.modbus_client.execute(
            ReadDeviceInformationRequest(unit=self.unit)
        )

        return {
            "manufacturer": response.information[0].decode("utf-8"),
            "model": response.information[1].decode("utf-8"),
            "version": response.information[2].decode("utf-8"),
        }

    def sync_rtc(self):
        self.logger.info("Syncing RTC")
        device_time = self.read_register(SettingParameter.Clock).value
        now = datetime.datetime.now()
        self.write_register(SettingParameter.Clock, now)
        self.logger.info(f"Device time was: {device_time.isoformat()}")
        self.logger.info(f"System time now: {now.isoformat()}")
