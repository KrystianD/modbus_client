from enum import Enum


class ModbusRegisterType(Enum):
    Coil = 1
    DiscreteInputs = 2
    InputRegister = 4
    HoldingRegister = 5


__all__ = [
    "ModbusRegisterType",
]
