import asyncio
import functools
import logging
from concurrent.futures.thread import ThreadPoolExecutor
from typing import List, cast, Any, Callable, Optional

import pymodbus.bit_read_message
import pymodbus.client
import pymodbus.register_read_message
import pymodbus.register_write_message
from pymodbus.framer.rtu_framer import ModbusRtuFramer

from modbus_client.client.async_modbus_client import AsyncModbusClient
from modbus_client.client.exceptions import ReadErrorException, WriteErrorException


class PyAsyncModbusClient(AsyncModbusClient):
    def __init__(self, client: pymodbus.client.base.ModbusBaseClient):
        self.client = client
        self.executor = ThreadPoolExecutor(1)

    async def _run(self, fn: Callable[..., Any], *args: List[Any], **kwargs: Any) -> Any:
        return await asyncio.get_event_loop().run_in_executor(self.executor, functools.partial(fn, *args, **kwargs))

    async def write_coil(self, unit: int, address: int, value: bool) -> None:
        await self._run(self.client.write_coil, slave=unit, address=address, value=value)

    async def read_coils(self, unit: int, address: int, count: int) -> List[bool]:
        bytes_count = (count + 7) // 8
        result = await self._run(self.client.read_coils, slave=unit, address=address, count=bytes_count)
        if isinstance(result, pymodbus.bit_read_message.ReadCoilsResponse):
            if result.byte_count != bytes_count:
                raise ReadErrorException("invalid count")

            # noinspection PyTypeChecker
            return cast(List[bool], result.bits[:count])
        else:
            raise ReadErrorException(str(result))

    async def read_discrete_inputs(self, unit: int, address: int, count: int) -> List[int]:
        result = await self._run(self.client.read_discrete_inputs, slave=unit, address=address, count=count)
        if isinstance(result, pymodbus.bit_read_message.ReadDiscreteInputsResponse):
            if result.byte_count != count:
                raise ReadErrorException("invalid count")

            values = []
            for byte_i in range(count):
                value = 0
                start_bit = 8 * byte_i
                end_bit = start_bit + 8
                for i, bit in enumerate(result.bits[start_bit:end_bit]):
                    value |= bit << i
                values.append(value)
            return values
        else:
            raise ReadErrorException(str(result))

    async def read_input_registers(self, unit: int, address: int, count: int) -> List[int]:
        logging.debug(f"read {address} count: {count}")
        result = await self._run(self.client.read_input_registers, slave=unit, address=address, count=count)
        if isinstance(result, pymodbus.register_read_message.ReadInputRegistersResponse):
            if len(result.registers) != count:
                raise ReadErrorException("invalid count")
            # noinspection PyTypeChecker
            return cast(List[int], result.registers)
        else:
            raise ReadErrorException(str(result))

    async def read_holding_registers(self, unit: int, address: int, count: int) -> List[int]:
        result = await self._run(self.client.read_holding_registers, slave=unit, address=address, count=count)
        if isinstance(result, pymodbus.register_read_message.ReadHoldingRegistersResponse):
            if len(result.registers) != count:
                raise ReadErrorException("invalid count")
            # noinspection PyTypeChecker
            return cast(List[int], result.registers)
        else:
            raise ReadErrorException(str(result))

    async def write_holding_register(self, unit: int, address: int, value: int) -> None:
        result = await self._run(self.client.write_register, slave=unit, address=address, value=value)
        if not isinstance(result, pymodbus.register_write_message.WriteSingleRegisterResponse):
            raise WriteErrorException(str(result))

    async def write_holding_registers(self, unit: int, address: int, values: List[int]) -> None:
        result = await self._run(self.client.write_registers, slave=unit, address=address, values=values)
        if not isinstance(result, pymodbus.register_write_message.WriteMultipleRegistersResponse):
            raise WriteErrorException(str(result))

    def close(self) -> None:
        self.client.close()


class PyAsyncModbusTcpClient(PyAsyncModbusClient):
    def __init__(self, host: str, port: int, timeout: float, silent_interval: Optional[float] = None):
        cl = pymodbus.client.tcp.ModbusTcpClient(host=host, port=port, timeout=timeout)

        if silent_interval is not None:
            cl.silent_interval = silent_interval

        super().__init__(cl)


class PyAsyncModbusRtuClient(PyAsyncModbusClient):
    def __init__(self, path: str, baudrate: int = 9600, stopbits: int = 1, parity: str = "N", timeout: float = 3,
                 silent_interval: Optional[float] = None):
        cl = pymodbus.client.serial.ModbusSerialClient(method="rtu", port=path,
                                                       baudrate=baudrate, stopbits=stopbits, parity=parity,
                                                       timeout=timeout)
        if silent_interval is not None:
            cl.silent_interval = silent_interval

        super().__init__(cl)


class PyAsyncModbusRtuOverTcpClient(PyAsyncModbusClient):
    def __init__(self, host: str, port: int, timeout: float, silent_interval: Optional[float] = None):
        cl = pymodbus.client.tcp.ModbusTcpClient(host=host, port=port, timeout=timeout, framer=ModbusRtuFramer)  # type: ignore

        if silent_interval is not None:
            cl.silent_interval = silent_interval

        super().__init__(cl)


__all__ = [
    "PyAsyncModbusTcpClient",
    "PyAsyncModbusRtuClient",
    "PyAsyncModbusRtuOverTcpClient",
]
