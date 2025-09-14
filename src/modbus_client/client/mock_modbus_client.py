import asyncio
from typing import List, Dict

from modbus_client.client.async_modbus_client import AsyncModbusClient

delay = 0.2
write_delay = 0.5


class MockModbusClient(AsyncModbusClient):
    def __init__(self, input_registers: Dict[int, int], holding_registers: Dict[int, int], missing_as_zero: bool):
        self.input_registers = input_registers
        self.holding_registers = holding_registers
        self.missing_as_zero = missing_as_zero

    async def write_coil(self, unit: int, address: int, value: bool) -> None:
        raise NotImplementedError()

    async def read_coils(self, unit: int, address: int, count: int) -> List[bool]:
        raise NotImplementedError()

    async def read_discrete_inputs(self, unit: int, address: int, count: int) -> List[int]:
        raise NotImplementedError()

    async def read_input_registers(self, unit: int, address: int, count: int) -> List[int]:
        await asyncio.sleep(delay)
        if self.missing_as_zero:
            return [self.input_registers.get(address + i, 0) for i in range(count)]
        else:
            return [self.input_registers[address + i] for i in range(count)]

    async def read_holding_registers(self, unit: int, address: int, count: int) -> List[int]:
        await asyncio.sleep(delay)
        if self.missing_as_zero:
            return [self.holding_registers.get(address + i, 0) for i in range(count)]
        else:
            return [self.holding_registers[address + i] for i in range(count)]

    async def write_holding_register(self, unit: int, address: int, value: int) -> None:
        await asyncio.sleep(write_delay)
        self.holding_registers[address] = value

    async def write_holding_registers(self, unit: int, address: int, values: List[int]) -> None:
        await asyncio.sleep(write_delay)
        for i, value in enumerate(values):
            self.holding_registers[address + i] = value

    def close(self) -> None:
        pass


__all__ = [
    "MockModbusClient",
]
