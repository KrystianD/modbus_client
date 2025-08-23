from abc import abstractmethod
from typing import List

DefaultMaxReadSize = 100


class AsyncModbusClient:
    @abstractmethod
    async def write_coil(self, unit: int, address: int, value: bool) -> None:
        pass

    @abstractmethod
    async def read_coils(self, unit: int, address: int, count: int) -> List[bool]:
        pass

    @abstractmethod
    async def read_discrete_inputs(self, unit: int, address: int, count: int) -> List[int]:
        pass

    @abstractmethod
    async def read_input_registers(self, unit: int, address: int, count: int) -> List[int]:
        pass

    @abstractmethod
    async def read_holding_registers(self, unit: int, address: int, count: int) -> List[int]:
        pass

    @abstractmethod
    async def write_holding_register(self, unit: int, address: int, value: int) -> None:
        pass

    @abstractmethod
    async def write_holding_registers(self, unit: int, address: int, values: List[int]) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


__all__ = [
    "DefaultMaxReadSize",
    "AsyncModbusClient",
]
