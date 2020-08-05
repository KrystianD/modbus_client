import io

import yaml
from dataclasses import field
from enum import Enum
from typing import List, Optional, Union, cast

from pydantic import StrictInt, StrictFloat
from pydantic.dataclasses import dataclass

from modbus_client.types import RegisterValueType


class ValueRegisterTypeEnum(str, Enum):
    InputRegister = 'input-register'
    HoldingRegister = 'holding-register'


@dataclass
class IDeviceRegister:
    name: str
    address: int
    scale: Union[StrictInt, StrictFloat] = cast(StrictInt, 1)
    type: RegisterValueType = RegisterValueType.U16
    unit: Optional[str] = None


@dataclass
class DeviceHoldingRegister(IDeviceRegister):
    pass


@dataclass
class DeviceInputRegister(IDeviceRegister):
    pass


class SwitchRegisterTypeEnum(str, Enum):
    Coil = 'coil'


@dataclass
class DeviceSwitch:
    name: str
    type: SwitchRegisterTypeEnum
    number: int


@dataclass
class DeviceRegisters:
    input_registers: List[DeviceInputRegister] = field(default_factory=list)
    holding_registers: List[DeviceHoldingRegister] = field(default_factory=list)


@dataclass
class DeviceConfig:
    zero_mode: bool
    registers: DeviceRegisters
    switches: List[DeviceSwitch] = field(default_factory=list)

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
    return DeviceConfig(**yaml.load(io.StringIO(config), Loader=yaml.SafeLoader))  # type: ignore


def load_device_config(path: str) -> DeviceConfig:
    return DeviceConfig(**yaml.load(open(path, "rt"), Loader=yaml.SafeLoader))  # type: ignore
