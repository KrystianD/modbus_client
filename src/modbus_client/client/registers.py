import struct
from abc import abstractmethod
from typing import Union, List, Optional, Tuple, cast, Callable, Any

from modbus_client.client.address_range import AddressRange
from modbus_client.client.types import ModbusReadSession, RegisterType, RegisterValueType

BitsArray = List[int]


def get_type_format(reg_type: RegisterValueType) -> Tuple[str, bool, Callable[[Any], Union[int, float]]]:
    if reg_type == RegisterValueType.S16:
        return "h", False, round
    elif reg_type == RegisterValueType.U16:
        return "H", False, round
    elif reg_type == RegisterValueType.S32BE:
        return "i", True, round
    elif reg_type == RegisterValueType.U32BE:
        return "I", True, round
    elif reg_type == RegisterValueType.S32LE:
        return "i", False, round
    elif reg_type == RegisterValueType.U32LE:
        return "I", False, round
    elif reg_type == RegisterValueType.F32BE:
        return "f", True, float
    elif reg_type == RegisterValueType.F32LE:
        return "f", False, float
    else:
        raise Exception("invalid type")


def get_bits(value: int, bits: BitsArray) -> int:
    final_value = 0
    for i, bit in enumerate(reversed(bits)):
        final_value |= ((value >> bit) & 0x01) << i
    return final_value


class IRegister(AddressRange):
    def __init__(self, name: str, reg_type: RegisterType, address: int,
                 value_type: RegisterValueType, bits: Optional[BitsArray]) -> None:
        super().__init__(address, struct.calcsize(get_type_format(value_type)[0]) // 2)
        self.name = name
        self.reg_type = reg_type
        self.value_type = value_type
        self.bits = bits

    @abstractmethod
    def format(self, read_session: ModbusReadSession) -> str:
        pass

    def get_raw_from_read_session(self, read_session: ModbusReadSession) -> int:
        type_format, reverse, _ = get_type_format(self.value_type)
        count = struct.calcsize(type_format) // 2

        registers_unordered = [read_session.registers_dict[(self.reg_type, self.address + i)] for i in range(count)]
        registers_ordered = registers_unordered if not reverse else reversed(registers_unordered)
        value_bytes = struct.pack("<" + "H" * count, *registers_ordered)
        val = cast(int, struct.unpack("<" + type_format, value_bytes)[0])

        if self.bits is None:
            return val
        else:
            return get_bits(val, self.bits)

    def value_to_modbus_registers(self, value: Union[int, float]) -> List[int]:
        type_format, reverse, value_type = get_type_format(self.value_type)
        count = struct.calcsize(type_format) // 2

        raw_value = value_type(value)
        value_bytes = struct.pack("<" + type_format, raw_value)
        registers_unordered = list(struct.unpack("<" + "H" * count, value_bytes))
        registers_ordered = registers_unordered if not reverse else list(reversed(registers_unordered))

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
