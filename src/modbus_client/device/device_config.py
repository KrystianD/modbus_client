import io
from dataclasses import field
from typing import List, Optional

import yaml
from pydantic.dataclasses import dataclass

from modbus_client.client.async_modbus_client import DefaultMaxReadSize
from modbus_client.device.registers.device_register import DeviceRegisters, DeviceSwitch, IDeviceRegister


@dataclass
class DeviceConfig:
    zero_mode: bool
    registers: DeviceRegisters
    switches: List[DeviceSwitch] = field(default_factory=list)
    force_multiple_write: bool = False
    allow_holes: bool = False
    max_read_size: int = DefaultMaxReadSize

    def find_register(self, name: str) -> Optional[IDeviceRegister]:
        for reg in self.get_all_registers():
            if reg.name == name:
                return reg
        return None

    def find_switch(self, name: str) -> Optional[DeviceSwitch]:
        for switch in self.switches:
            if switch.name == name:
                return switch
        return None

    def get_all_registers(self) -> List[IDeviceRegister]:
        return [*self.registers.holding_registers, *self.registers.input_registers]


def load_device_config_from_yaml(config: str) -> DeviceConfig:
    return DeviceConfig(**yaml.load(io.StringIO(config), Loader=yaml.SafeLoader))


def load_device_config(path: str) -> DeviceConfig:
    return DeviceConfig(**yaml.load(open(path, "rt"), Loader=yaml.SafeLoader))
