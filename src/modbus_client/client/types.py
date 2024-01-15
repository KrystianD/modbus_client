from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Tuple, Union


class RegisterType(Enum):
    Coil = 1
    DiscreteInputs = 2
    InputRegister = 4
    HoldingRegister = 5


class RegisterValueType(str, Enum):
    S16 = 'int16'
    U16 = 'uint16'
    S32BE = 'int32be'
    S32LE = 'int32le'
    U32BE = 'uint32be'
    U32LE = 'uint32le'
    S64BE = 'int64be'
    S64LE = 'int64le'
    U64BE = 'uint64be'
    U64LE = 'uint64le'
    F32BE = 'float32be'
    F32LE = 'float32le'


RegisterValue = Union[int, bool]


@dataclass
class ModbusReadSession:
    registers_dict: Dict[Tuple[RegisterType, int], RegisterValue] = field(default_factory=dict)


__all__ = [
    "RegisterType",
    "ModbusReadSession",
    "RegisterValueType",
]
