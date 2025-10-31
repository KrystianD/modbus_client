import struct
from abc import abstractmethod
from dataclasses import dataclass
from typing import Union, List, Optional, cast, Set, Iterator

from modbus_client.device.registers.enum_definition import EnumDefinition
from modbus_client.device.registers.flag_definition import FlagDefinition
from modbus_client.registers.address_range import AddressRangeTrait
from modbus_client.client.types import ModbusRegisterType
from modbus_client.registers.type_converters import get_type_converter
from modbus_client.registers.register_value_type import RegisterValueType
from modbus_client.registers.read_session import ModbusReadSession

BitsArray = List[int]


def get_bits(value: int, bits: BitsArray) -> int:
    final_value = 0
    for i, bit in enumerate(bits):
        final_value |= ((value >> bit) & 0x01) << i
    return final_value


def put_bits(bits: BitsArray, value: int, existing_value: int) -> int:
    final_value = existing_value

    for i, bit in enumerate(bits):
        final_value &= ~(1 << bit)
        final_value |= ((value >> i) & 0x01) << bit

    return final_value


@dataclass
class EnumValue:
    enum_name: Optional[str]
    enum_value: int
    enum_display: Optional[str]

    def format(self) -> str:
        if self.enum_name is None:
            return f"<unknown> ({self.enum_value})"
        else:
            return f"{self.enum_name} ({self.enum_value})"


@dataclass(frozen=True)
class FlagValue:
    flag_name: Optional[str]
    flag_bit: int
    flag_display: Optional[str]

    def format(self) -> str:
        if self.flag_name is None:
            return f"(bit{self.flag_bit})"
        else:
            return f"{self.flag_name} (bit{self.flag_bit})"


@dataclass(frozen=True)
class FlagsCollection:
    flags: Set[FlagValue]

    def __iter__(self) -> Iterator[FlagValue]:
        return iter(self.flags)

    def __contains__(self, item: int | FlagValue | FlagDefinition) -> bool:
        bits = {x.flag_bit for x in self.flags}

        if isinstance(item, int):
            return item in bits
        elif isinstance(item, FlagValue):
            return item.flag_bit in bits
        elif isinstance(item, FlagDefinition):
            return item.bit in bits
        else:
            raise ValueError(f"Unsupported item type {type(item)}")


class IRegister(AddressRangeTrait):
    def __init__(self, name: str, reg_type: ModbusRegisterType, address: int,
                 value_type: RegisterValueType, bits: Optional[BitsArray]) -> None:
        self.address = address
        self.count = struct.calcsize(get_type_converter(value_type).format_str) // 2
        self.name = name
        self.reg_type = reg_type
        self.value_type = value_type
        self.bits = bits

        if self.bits is not None:
            if self.value_type not in (RegisterValueType.U16,):
                raise ValueError("Bitfields only support uint16 type")

    def get_address(self) -> int:
        return self.address

    def get_count(self) -> int:
        return self.count

    def get_reg_type(self) -> ModbusRegisterType:
        return self.reg_type

    def requires_existing_reading(self) -> bool:
        return self.bits is not None

    @abstractmethod
    def format(self, read_session: ModbusReadSession) -> str:
        pass

    @abstractmethod
    def get_value_from_read_session(self, read_session: ModbusReadSession) -> Union[int, float, EnumValue, FlagsCollection, str]:
        pass

    def get_raw_from_read_session(self, read_session: ModbusReadSession) -> int:
        val = self._get_base_value_from_read_session(read_session)

        if self.bits is None:
            return val
        else:
            return get_bits(val, self.bits)

    def value_to_modbus_registers(self, value: Union[int, float, str], existing_read_session: ModbusReadSession | None) -> List[int]:
        reg_type_converter = get_type_converter(self.value_type)
        count = struct.calcsize(reg_type_converter.format_str) // 2

        if self.bits:
            assert existing_read_session is not None
            assert isinstance(value, int)
            existing_value = self._get_base_value_from_read_session(existing_read_session)
            value = put_bits(self.bits, value, existing_value)

        raw_value = reg_type_converter.converter_func(value)
        value_bytes = struct.pack("<" + reg_type_converter.format_str, raw_value)

        registers_unordered = list(struct.unpack("<" + "H" * count, value_bytes))
        registers_ordered = registers_unordered if not reg_type_converter.reverse_bytes else list(
                reversed(registers_unordered))

        return registers_ordered

    def _get_base_value_from_read_session(self, read_session: ModbusReadSession) -> int:
        reg_type_converter = get_type_converter(self.value_type)
        count = struct.calcsize(reg_type_converter.format_str) // 2

        registers_unordered = [read_session.registers_dict[(self.reg_type, self.address + i)] for i in range(count)]
        registers_ordered = registers_unordered if not reg_type_converter.reverse_bytes else reversed(
                registers_unordered)
        value_bytes = struct.pack("<" + "H" * count, *registers_ordered)
        val = cast(int, struct.unpack("<" + reg_type_converter.format_str, value_bytes)[0])

        return val


class NumericRegister(IRegister):
    def __init__(self, name: str, reg_type: ModbusRegisterType, address: int,
                 value_type: RegisterValueType = RegisterValueType.U16, *, bits: Optional[BitsArray] = None,
                 scale: Union[int, float] = 1, unit: Optional[str] = None) -> None:
        super().__init__(name=name, reg_type=reg_type, address=address, value_type=value_type, bits=bits)
        self.scale = scale
        self.unit = unit

    def get_value_from_read_session(self, read_session: ModbusReadSession) -> Union[int, float]:
        num = super().get_raw_from_read_session(read_session)
        return num * self.scale

    def value_to_modbus_registers(self, value: Union[int, float, str], existing_read_session: ModbusReadSession | None) -> List[int]:
        assert isinstance(value, (int, float)), "value must be int or float"
        return super().value_to_modbus_registers((value / self.scale) if self.scale != 1 else value,
                                                 existing_read_session=existing_read_session)

    def format(self, read_session: ModbusReadSession) -> str:
        value = self.get_value_from_read_session(read_session)
        unit_str = "" if self.unit is None else (" " + self.unit)
        if isinstance(value, int):
            return f"{value}{unit_str}"
        elif isinstance(value, float):
            return f"{value:.3f}{unit_str}"


class EnumRegister(IRegister):
    def __init__(self, name: str, reg_type: ModbusRegisterType, address: int,
                 value_type: RegisterValueType = RegisterValueType.U16, *, bits: Optional[BitsArray] = None,
                 enum: List[EnumDefinition]) -> None:
        super().__init__(name=name, reg_type=reg_type, address=address, value_type=value_type, bits=bits)

        self.enum_by_value = {x.value: x for x in enum}
        self.enum_by_name = {x.name: x for x in enum}

    def get_value_from_read_session(self, read_session: ModbusReadSession) -> EnumValue:
        value = super().get_raw_from_read_session(read_session)

        enum_def = self.enum_by_value.get(value)
        if enum_def is None:
            return EnumValue(enum_name=None, enum_value=value, enum_display=None)
        else:
            return EnumValue(enum_name=enum_def.name, enum_value=value, enum_display=enum_def.display)

    def value_to_modbus_registers(self, value: Union[int, float, str], existing_read_session: ModbusReadSession | None) -> List[int]:
        assert isinstance(value, (int, str)), "value must be int or string"

        if isinstance(value, str):
            enum_def = self.enum_by_name.get(value)
            if enum_def is None:
                raise ValueError(f"Enum {value} not found")
            else:
                return super().value_to_modbus_registers(enum_def.value, existing_read_session=existing_read_session)
        elif isinstance(value, int):
            return super().value_to_modbus_registers(value, existing_read_session=existing_read_session)
        else:
            raise ValueError(f"Unknown value type {type(value)}")

    def format(self, read_session: ModbusReadSession) -> str:
        enum_value = self.get_value_from_read_session(read_session)

        return enum_value.format()


class BoolRegister(IRegister):
    def __init__(self, name: str, reg_type: ModbusRegisterType, address: int, bit: int) -> None:
        super().__init__(name=name, reg_type=reg_type, address=address, value_type=RegisterValueType.U16, bits=[bit])

    def requires_existing_reading(self) -> bool:
        return True

    def get_value_from_read_session(self, read_session: ModbusReadSession) -> bool:
        value = super().get_raw_from_read_session(read_session)

        return value != 0

    def value_to_modbus_registers(self, value: Union[int, float, str], existing_read_session: ModbusReadSession | None) -> List[int]:
        assert isinstance(value, (int, bool)), "value must be an int or boolean"

        return super().value_to_modbus_registers(1 if value else 0, existing_read_session=existing_read_session)

    def format(self, read_session: ModbusReadSession) -> str:
        value = self.get_value_from_read_session(read_session)

        return "true" if value else "false"


class FlagsRegister(IRegister):
    def __init__(self, name: str, reg_type: ModbusRegisterType, address: int, *, bits: Optional[BitsArray] = None,
                 flags: List[FlagDefinition]) -> None:
        super().__init__(name=name, reg_type=reg_type, address=address, value_type=RegisterValueType.U16, bits=bits)

        self.bit_to_flag = {x.bit: x for x in flags}

        if self.value_type not in (RegisterValueType.U16,):
            raise ValueError("Flags only supports uint16 type")

    def requires_existing_reading(self) -> bool:
        return True

    def get_value_from_read_session(self, read_session: ModbusReadSession) -> FlagsCollection:
        value = super().get_raw_from_read_session(read_session)

        flags: Set[FlagValue] = set()
        bit = 0
        while value > 0:
            if value & 1 == 1:
                f = self.bit_to_flag.get(bit)
                if f is not None:
                    flags.add(FlagValue(flag_name=f.name, flag_bit=f.bit, flag_display=f.display))
                else:
                    flags.add(FlagValue(flag_name=None, flag_bit=bit, flag_display=None))

            value >>= 1
            bit += 1

        return FlagsCollection(flags)

    def value_to_modbus_registers(self, value: Union[int, float, str], existing_read_session: ModbusReadSession | None) -> List[int]:
        raise Exception("writing to flags register is not supported")

    def format(self, read_session: ModbusReadSession) -> str:
        value = self.get_value_from_read_session(read_session)

        return ",".join(x.format() for x in sorted(value, key=lambda x: x.flag_bit, reverse=True))


class StringRegister(IRegister):
    def __init__(self, name: str, reg_type: ModbusRegisterType, address: int, *, words: int) -> None:
        super().__init__(name=name, reg_type=reg_type, address=address, value_type=RegisterValueType.U16, bits=[])

        self.words = words

        if self.value_type not in (RegisterValueType.U16,):
            raise ValueError("Flags only supports uint16 type")

    def get_count(self) -> int:
        return self.words

    def requires_existing_reading(self) -> bool:
        return True

    def get_value_from_read_session(self, read_session: ModbusReadSession) -> str:
        values = [read_session.registers_dict[(self.reg_type, self.address + i)] for i in range(self.get_count())]

        string_bytes = struct.pack(f">{len(values)}H", *values)
        first_null = string_bytes.find(0x00)
        if first_null != -1:
            string_bytes = string_bytes[:first_null]

        return string_bytes.decode('ascii')

    def value_to_modbus_registers(self, value: Union[int, float, str], existing_read_session: ModbusReadSession | None) -> List[int]:
        raise Exception("writing to flags register is not supported")

    def format(self, read_session: ModbusReadSession) -> str:
        value = self.get_value_from_read_session(read_session)

        return value


class Coil(IRegister):
    def __init__(self, name: str, reg_type: ModbusRegisterType, number: int) -> None:
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
    "ModbusRegisterType",

    "IRegister",

    "NumericRegister",
]
