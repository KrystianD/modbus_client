import re
from dataclasses import field
from enum import Enum
from typing import List, Optional, Union, cast, Any, Dict, Annotated

from pydantic import StrictInt, StrictFloat, field_validator, model_validator, StringConstraints, BaseModel
from pydantic.dataclasses import dataclass

from modbus_client.device.registers.enum_definition import EnumDefinition
from modbus_client.device.registers.flag_definition import FlagDefinition
from modbus_client.registers.bitarray import BitArray
from modbus_client.device.registers.register_type import RegisterType


class ValueRegisterTypeEnum(str, Enum):
    InputRegister = 'input-register'
    HoldingRegister = 'holding-register'


class IDeviceRegister(BaseModel):
    name: Annotated[str, StringConstraints(pattern=r'^[a-zA-Z][a-zA-Z0-9_]*$')]
    address: int
    readonly: bool = False
    scale: Union[StrictInt, StrictFloat] = cast(StrictInt, 1)
    type: RegisterType = RegisterType.U16
    unit: Optional[str] = None
    bits: Optional[BitArray] = None
    enum: Optional[List[EnumDefinition]] = None
    flags: Optional[List[FlagDefinition]] = None
    bit: int = 0

    @field_validator('bits', mode='before')
    @classmethod
    def parse_bits(cls, bits_str: Any) -> BitArray:
        return BitArray.parse(bits_str)

    @model_validator(mode='after')
    def check(self) -> 'IDeviceRegister':
        if self.type == RegisterType.ENUM and self.enum is None:
            raise ValueError("register of type /enum/ requires /enum/ object with the definition")
        if self.type == RegisterType.BOOL and self.bit is None:
            raise ValueError("register of type /bool/ requires /bit/ definition")
        if self.type == RegisterType.FLAGS:
            if self.flags is None:
                raise ValueError("register of type /flags/ requires /flags/ object with the definition")
            if not self.readonly:
                raise ValueError("register of type /flags/ need to be readonly")
        return self


def parse_options_str(options_strs: List[str]) -> Dict[str, Any]:
    options: Dict[str, Any] = {}

    for option_str in options_strs:
        parts = option_str.split('=', 1)
        if len(parts) == 1:
            options[parts[0]] = True
        elif len(parts) == 2:
            options[parts[0]] = parts[1]
        else:
            raise ValueError("invalid options")

    return options


def parse_register_def(reg_def: str) -> Optional[Dict[str, Any]]:
    reg_def_str, *options_strs = reg_def.split(',')

    options = parse_options_str(options_strs)

    address_re = r"\s*(?P<address>0x[0-9a-fA-F]+|[0-9]+)\s*"

    # name/0x002a/float32be*0.1[unit]
    m = re.match(rf"^([a-zA-Z0-9_ ]+)/{address_re}/([^*\[]+)(?:\*(?P<scale>[0-9.]+))?(?:\[(?P<unit>.+)])?$", reg_def_str)
    if m is not None:
        return dict(
                name=m.group(1).strip(),
                address=int(m.group("address"), 0),
                type=RegisterType(m.group(3).strip().lower()),
                scale=float(m.group("scale")) if m.group("scale") is not None else 1,
                unit=m.group("unit"),
                **options)

    # name/0x002a/float32be
    m = re.match(rf"^([a-zA-Z0-9_ ]+)/{address_re}/(.+)$", reg_def_str)
    if m is not None:
        return dict(
                name=m.group(1).strip(),
                address=int(m.group("address"), 0),
                type=RegisterType(m.group(3).strip().lower()),
                **options)

    # name/0x002a
    m = re.match(rf"^([a-zA-Z0-9_ ]+)/{address_re}$", reg_def_str)
    if m is not None:
        return dict(
                name=m.group(1).strip(),
                address=int(m.group("address"), 0),
                **options)

    return None


class DeviceHoldingRegister(IDeviceRegister):
    @staticmethod
    def parse(value: str) -> 'DeviceHoldingRegister':
        data = parse_register_def(value)
        if data is None:
            raise Exception(f"invalid definition: {value}")
        else:
            return DeviceHoldingRegister(**data)


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

    @field_validator('input_registers', mode='before')
    @classmethod
    def _input_registers(cls, v: Any) -> List[Any]:
        return [(DeviceInputRegister.parse(x) if isinstance(x, str) else x) for x in v]

    @field_validator('holding_registers', mode='before')
    @classmethod
    def _holding_registers(cls, v: Any) -> List[Any]:
        return [(DeviceHoldingRegister.parse(x) if isinstance(x, str) else x) for x in v]
