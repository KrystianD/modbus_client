import struct
from abc import abstractmethod
from dataclasses import dataclass
from typing import Union, List, Optional, cast, Callable, Any, Dict

from modbus_client.client.address_range import AddressRange
from modbus_client.client.types import ModbusReadSession, RegisterType, RegisterValueType

BitsArray = List[int]


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


def get_type_format(reg_type: RegisterValueType) -> RegisterTypeConverter:
    reg_type_converter = register_type_converters.get(reg_type)
    if reg_type_converter is None:
        raise ValueError(f"Unknown register type {reg_type}")
    return reg_type_converter


def get_bits(value: int, bits: BitsArray) -> int:
    final_value = 0
    for i, bit in enumerate(reversed(bits)):
        final_value |= ((value >> bit) & 0x01) << i
    return final_value


class IRegister(AddressRange):
    def __init__(self, name: str, reg_type: RegisterType, address: int,
                 value_type: RegisterValueType, bits: Optional[BitsArray]) -> None:
        super().__init__(address, struct.calcsize(get_type_format(value_type).format_str) // 2)
        self.name = name
        self.reg_type = reg_type
        self.value_type = value_type
        self.bits = bits

    @abstractmethod
    def format(self, read_session: ModbusReadSession) -> str:
        pass

    @abstractmethod
    def get_value_from_read_session(self, read_session: ModbusReadSession) -> Union[int, float]:
        pass

    def get_raw_from_read_session(self, read_session: ModbusReadSession) -> int:
        reg_type_converter = get_type_format(self.value_type)
        count = struct.calcsize(reg_type_converter.format_str) // 2

        registers_unordered = [read_session.registers_dict[(self.reg_type, self.address + i)] for i in range(count)]
        registers_ordered = registers_unordered if not reg_type_converter.reverse_bytes else reversed(
            registers_unordered)
        value_bytes = struct.pack("<" + "H" * count, *registers_ordered)
        val = cast(int, struct.unpack("<" + reg_type_converter.format_str, value_bytes)[0])

        if self.bits is None:
            return val
        else:
            return get_bits(val, self.bits)

    def value_to_modbus_registers(self, value: Union[int, float]) -> List[int]:
        reg_type_converter = get_type_format(self.value_type)
        count = struct.calcsize(reg_type_converter.format_str) // 2

        raw_value = reg_type_converter.converter_func(value)
        value_bytes = struct.pack("<" + reg_type_converter.format_str, raw_value)
        registers_unordered = list(struct.unpack("<" + "H" * count, value_bytes))
        registers_ordered = registers_unordered if not reg_type_converter.reverse_bytes else list(
            reversed(registers_unordered))

        return registers_ordered


class NumericRegister(IRegister):
    def __init__(self, name: str, reg_type: RegisterType, address: int,
                 value_type: RegisterValueType = RegisterValueType.U16, *, bits: Optional[BitsArray] = None,
                 scale: Union[int, float] = 1, unit: Optional[str] = None) -> None:
        super().__init__(name=name, reg_type=reg_type, address=address, value_type=value_type, bits=bits)
        self.scale = scale
        self.unit = unit

    def get_value_from_read_session(self, read_session: ModbusReadSession) -> Union[int, float]:
        num = super().get_raw_from_read_session(read_session)
        return num * self.scale

    def value_to_modbus_registers(self, value: Union[int, float]) -> List[int]:
        return super().value_to_modbus_registers(value / self.scale)

    def format(self, read_session: ModbusReadSession) -> str:
        value = self.get_value_from_read_session(read_session)
        unit_str = "" if self.unit is None else (" " + self.unit)
        if isinstance(value, int):
            return f"{value}{unit_str}"
        elif isinstance(value, float):
            return f"{value:.3f}{unit_str}"


class Coil(IRegister):
    def __init__(self, name: str, reg_type: RegisterType, number: int) -> None:
        super().__init__(name=name, reg_type=reg_type, address=number // 8 * 8, value_type=RegisterValueType.U16,
                         bits=None)
        self.count = 8
        self.number = number

    def get_value_from_read_session(self, read_session: ModbusReadSession) -> Union[int, float]:
        return 1 if self.get_from_read_session(read_session) else 0

    def get_from_read_session(self, read_session: ModbusReadSession) -> bool:
        value = read_session.registers_dict[(self.reg_type, self.number)]
        assert isinstance(value, bool)
        return value

    def format(self, read_session: ModbusReadSession) -> str:
        value = self.get_from_read_session(read_session)
        return "ON" if value else "OFF"


__all__ = [
    "RegisterType",

    "IRegister",

    "NumericRegister",
]
