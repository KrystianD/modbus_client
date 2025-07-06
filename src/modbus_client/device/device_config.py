import io
import re
from dataclasses import field
from enum import Enum
from typing import List, Optional, Union, cast, Any, Dict

import yaml
from pydantic import StrictInt, StrictFloat, validator
from pydantic.dataclasses import dataclass

from modbus_client.client.async_modbus_client import DefaultMaxReadSize
from modbus_client.client.types import RegisterValueType


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


def parse_register_def(reg_def: str) -> Optional[Dict[str, Any]]:
    reg_def_str, *options_str = reg_def.split(',')

    options = {x.split('=')[0]: (x.split('=')[1]) for x in options_str}

    address_re = r"\s*(?P<address>0x[0-9a-fA-F]+|[0-9]+)\s*"

    # name/0x002a/float32be*0.1[unit]
    m = re.match(rf"^([a-zA-Z0-9_ ]+)/{address_re}/([^*\[]+)(?:\*(?P<scale>[0-9.]+))?(?:\[(?P<unit>.+)])?$", reg_def_str)
    if m is not None:
        return dict(
                name=m.group(1).strip(),
                address=int(m.group("address"), 0),
                type=RegisterValueType(m.group(3).strip().lower()),
                scale=float(m.group("scale")) if m.group("scale") is not None else 1,
                unit=m.group("unit"),
                **options)

    # name/0x002a/float32be
    m = re.match(rf"^([a-zA-Z0-9_ ]+)/{address_re}/(.+)$", reg_def_str)
    if m is not None:
        return dict(
                name=m.group(1).strip(),
                address=int(m.group("address"), 0),
                type=RegisterValueType(m.group(3).strip().lower()),
                **options)

    # name/0x002a
    m = re.match(rf"^([a-zA-Z0-9_ ]+)/{address_re}$", reg_def_str)
    if m is not None:
        return dict(
                name=m.group(1).strip(),
                address=int(m.group("address"), 0),
                **options)

    return None


@dataclass
class DeviceHoldingRegister(IDeviceRegister):
    @staticmethod
    def parse(value: str) -> 'DeviceHoldingRegister':
        data = parse_register_def(value)
        if data is None:
            raise Exception(f"invalid definition: {value}")
        else:
            return DeviceHoldingRegister(**data)


@dataclass
class DeviceInputRegister(IDeviceRegister):
    @staticmethod
    def parse(value: str) -> 'DeviceInputRegister':
        data = parse_register_def(value)
        if data is None:
            raise Exception("invalid definition")
        else:
            return DeviceInputRegister(**data)


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

    @validator('input_registers', pre=True, allow_reuse=False)
    def _input_registers(cls, v: Any) -> List[Any]:
        return [(DeviceInputRegister.parse(x) if isinstance(x, str) else x) for x in v]

    @validator('holding_registers', pre=True, allow_reuse=False)
    def _holding_registers(cls, v: Any) -> List[Any]:
        return [(DeviceHoldingRegister.parse(x) if isinstance(x, str) else x) for x in v]


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
