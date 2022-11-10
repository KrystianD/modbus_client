import asyncio
import functools
from concurrent.futures.thread import ThreadPoolExecutor
from typing import List, cast, Any, Callable

import pymodbus.client.sync
import pymodbus.client.asynchronous.tcp
import pymodbus.register_read_message
import pymodbus.register_write_message
import pymodbus.bit_read_message

from modbus_client.exceptions import ReadErrorException, WriteErrorException
from modbus_client.async_modbus_client import AsyncModbusClient


class PyAsyncModbusClient(AsyncModbusClient):
    def __init__(self, client: pymodbus.client.sync.BaseModbusClient):
        self.client = client
        self.executor = ThreadPoolExecutor(1)

    async def _run(self, fn: Callable[..., Any], *args: List[Any], **kwargs: Any) -> Any:
        return await asyncio.get_event_loop().run_in_executor(self.executor, functools.partial(fn, *args, **kwargs))

    async def write_coil(self, unit: int, address: int, value: bool) -> None:
        await self._run(self.client.write_coil, unit=unit, address=address, value=value)

    async def read_coils(self, unit: int, address: int, count: int) -> List[bool]:
        bytes_count = (count + 7) // 8
        result = await self._run(self.client.read_coils, unit=unit, address=address, count=bytes_count)
        if isinstance(result, pymodbus.bit_read_message.ReadCoilsResponse):
            if result.byte_count != bytes_count:
                raise ReadErrorException

            # noinspection PyTypeChecker
            return cast(List[bool], result.bits[:count])

        raise ReadErrorException

    async def read_discrete_inputs(self, unit: int, address: int, count: int) -> List[int]:
        result = await self._run(self.client.read_discrete_inputs, unit=unit, address=address, count=count)
        if isinstance(result, pymodbus.bit_read_message.ReadDiscreteInputsResponse):
            if result.byte_count != count:
                raise ReadErrorException

            values = []
            for byte_i in range(count):
                value = 0
                start_bit = 8 * byte_i
                end_bit = start_bit + 8
                for i, bit in enumerate(result.bits[start_bit:end_bit]):
                    value |= bit << i
                values.append(value)
            return values

        raise ReadErrorException

    async def read_input_registers(self, unit: int, address: int, count: int) -> List[int]:
        result = await self._run(self.client.read_input_registers, unit=unit, address=address, count=count)
        if isinstance(result, pymodbus.register_read_message.ReadInputRegistersResponse):
            if len(result.registers) != count:
                raise ReadErrorException
            # noinspection PyTypeChecker
            return cast(List[int], result.registers)
        raise ReadErrorException

    async def read_holding_registers(self, unit: int, address: int, count: int) -> List[int]:
        result = await self._run(self.client.read_holding_registers, unit=unit, address=address, count=count)
        if isinstance(result, pymodbus.register_read_message.ReadHoldingRegistersResponse):
            if len(result.registers) != count:
                raise ReadErrorException
            # noinspection PyTypeChecker
            return cast(List[int], result.registers)
        raise ReadErrorException

    async def write_holding_registers(self, unit: int, address: int, values: List[int]) -> None:
        if len(values) == 1:
            result = await self._run(self.client.write_register, unit=unit, address=address, value=values[0])
            if not isinstance(result, pymodbus.register_write_message.WriteSingleRegisterResponse):
                raise WriteErrorException
        else:
            result = await self._run(self.client.write_registers, unit=unit, address=address, values=values)
            if not isinstance(result, pymodbus.register_write_message.WriteMultipleRegistersResponse):
                raise WriteErrorException

    def close(self) -> None:
        self.client.close()


class PyAsyncModbusTcpClient(PyAsyncModbusClient):
    def __init__(self, host: str, port: int, timeout: int):
        super().__init__(pymodbus.client.sync.ModbusTcpClient(host=host, port=port, timeout=timeout))


class PyAsyncModbusRtuClient(PyAsyncModbusClient):
    def __init__(self, path: str, baudrate: int = 9600, stopbits: int = 1, parity: str = "N", timeout: int = 3):
        super().__init__(pymodbus.client.sync.ModbusSerialClient(method="rtu", port=path, baudrate=baudrate, stopbits=stopbits, parity=parity, timeout=timeout))


__all__ = [
    "PyAsyncModbusTcpClient",
    "PyAsyncModbusRtuClient",
]
