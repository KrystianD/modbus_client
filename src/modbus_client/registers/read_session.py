from dataclasses import dataclass, field
from typing import Dict, Tuple, Union, Protocol
from typing import Sequence

from modbus_client.registers.address_range import merge_address_ranges, AddressRangeTrait
from modbus_client.client.async_modbus_client import DefaultMaxReadSize, AsyncModbusClient
from modbus_client.client.types import ModbusRegisterType

RegisterValue = Union[int, bool]


class ModbusRegisterTypeTrait(Protocol):
    def get_reg_type(self) -> ModbusRegisterType: ...


class ModbusRegisterTrait(ModbusRegisterTypeTrait, AddressRangeTrait, Protocol):
    pass


@dataclass
class ModbusReadSession:
    registers_dict: Dict[Tuple[ModbusRegisterType, int], RegisterValue] = field(default_factory=dict)

    @staticmethod
    async def read_registers(client: AsyncModbusClient,
                             unit: int,
                             registers: Sequence[ModbusRegisterTrait],
                             allow_holes: bool = False,
                             max_read_size: int = DefaultMaxReadSize) -> 'ModbusReadSession':
        coils_registers = [x for x in registers if x.get_reg_type() == ModbusRegisterType.Coil]
        discrete_inputs_registers = [x for x in registers if x.get_reg_type() == ModbusRegisterType.DiscreteInputs]
        input_registers = [x for x in registers if x.get_reg_type() == ModbusRegisterType.InputRegister]
        holding_registers = [x for x in registers if x.get_reg_type() == ModbusRegisterType.HoldingRegister]

        coils_buckets = merge_address_ranges(coils_registers, allow_holes=False, max_read_size=1)
        discrete_inputs_buckets = merge_address_ranges(discrete_inputs_registers, allow_holes=False, max_read_size=1)
        input_registers_buckets = merge_address_ranges(input_registers, allow_holes=allow_holes,
                                                       max_read_size=max_read_size)
        holding_registers_buckets = merge_address_ranges(holding_registers, allow_holes=allow_holes,
                                                         max_read_size=max_read_size)

        ses = ModbusReadSession()
        for rng in coils_buckets:
            values1 = await client.read_coils(unit=unit, address=rng.address, count=rng.count)
            for i, val1 in enumerate(values1):
                ses.registers_dict[(ModbusRegisterType.Coil, rng.address + i)] = val1

        for rng in discrete_inputs_buckets:
            values2 = await client.read_discrete_inputs(unit=unit, address=rng.address, count=rng.count)
            for i, val2 in enumerate(values2):
                ses.registers_dict[(ModbusRegisterType.DiscreteInputs, rng.address + i)] = val2

        for rng in input_registers_buckets:
            values3 = await client.read_input_registers(unit=unit, address=rng.address, count=rng.count)
            for i, val3 in enumerate(values3):
                ses.registers_dict[(ModbusRegisterType.InputRegister, rng.address + i)] = val3

        for rng in holding_registers_buckets:
            values4 = await client.read_holding_registers(unit=unit, address=rng.address, count=rng.count)
            for i, val4 in enumerate(values4):
                ses.registers_dict[(ModbusRegisterType.HoldingRegister, rng.address + i)] = val4

        return ses
