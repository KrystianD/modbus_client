from dataclasses import dataclass
from typing import Union, Callable, Any, Dict

from modbus_client.registers.register_value_type import RegisterValueType


@dataclass
class RegisterTypeConverter:
    format_str: str
    reverse_bytes: bool
    converter_func: Callable[[Any], Union[int, float]]


register_type_converters: Dict[RegisterValueType, RegisterTypeConverter] = {
    RegisterValueType.S16: RegisterTypeConverter("h", False, round),
    RegisterValueType.U16: RegisterTypeConverter("H", False, round),
    RegisterValueType.S32BE: RegisterTypeConverter("i", True, round),
    RegisterValueType.U32BE: RegisterTypeConverter("I", True, round),
    RegisterValueType.S32LE: RegisterTypeConverter("i", False, round),
    RegisterValueType.U32LE: RegisterTypeConverter("I", False, round),
    RegisterValueType.S64BE: RegisterTypeConverter("q", True, round),
    RegisterValueType.U64BE: RegisterTypeConverter("Q", True, round),
    RegisterValueType.S64LE: RegisterTypeConverter("q", False, round),
    RegisterValueType.U64LE: RegisterTypeConverter("Q", False, round),
    RegisterValueType.F32BE: RegisterTypeConverter("f", True, float),
    RegisterValueType.F32LE: RegisterTypeConverter("f", False, float),
}


def get_type_converter(reg_type: RegisterValueType) -> RegisterTypeConverter:
    reg_type_converter = register_type_converters.get(reg_type)
    if reg_type_converter is None:
        raise ValueError(f"Unknown register type {reg_type}")
    return reg_type_converter


__all__ = [
    "get_type_converter",
]
