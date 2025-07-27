from dataclasses import dataclass
from typing import Callable

from modbus_client.client.async_modbus_client import AsyncModbusClient
from modbus_client.device.modbus_device import ModbusDevice


@dataclass
class Connector:
    modbus_device: ModbusDevice
    client_factory: Callable[[], AsyncModbusClient]
