import asyncio
import functools
import logging
from asyncio import CancelledError
from concurrent.futures.thread import ThreadPoolExecutor
from typing import List, cast, Any, Callable, Optional, TypeVar

import pymodbus.bit_read_message
import pymodbus.client
import pymodbus.register_read_message
import pymodbus.register_write_message
import pymodbus.pdu
import pymodbus.exceptions
from pymodbus.framer.rtu_framer import ModbusRtuFramer

from modbus_client.client.async_modbus_client import AsyncModbusClient
from modbus_client.client.exceptions import ModbusException

T = TypeVar('T')

DefaultTimeout = 3
DefaultRetryCount = 1


class PyAsyncModbusClient(AsyncModbusClient):
    def __init__(self, client: pymodbus.client.base.ModbusBaseClient, retry_count: int = DefaultRetryCount):
        self.client = client
        self.executor = ThreadPoolExecutor(1)
        self._retry_count = max(1, retry_count)

    async def _run_single(self, fn: Callable[..., T], *args: List[Any], **kwargs: Any) -> T:
        try:
            resp = await asyncio.get_event_loop().run_in_executor(self.executor, functools.partial(fn, *args, **kwargs))
            if isinstance(resp, pymodbus.exceptions.ModbusException):
                raise ModbusException(f"Modbus error: {resp.string}")
            elif isinstance(resp, pymodbus.pdu.ExceptionResponse):
                raise ModbusException(f"Modbus error response: {resp.exception_code}")
            else:
                return resp
        except Exception as e:
            raise ModbusException(f"Unknown error: {e}")

    async def _run_with_retry(self, fn: Callable[..., T], *args: List[Any], **kwargs: Any) -> T:
        for i in range(self._retry_count):
            try:
                return await self._run_single(fn, *args, **kwargs)
            except (KeyboardInterrupt, CancelledError):
                raise
            except Exception as e:
                if i + 1 == self._retry_count:
                    raise
                logging.debug(f"Error, retry {i + 1} of {self._retry_count}, error: {e}")

        raise ModbusException("Unreachable")

    async def write_coil(self, unit: int, address: int, value: bool) -> None:
        await self._run_with_retry(self.client.write_coil, slave=unit, address=address, value=value)

    async def read_coils(self, unit: int, address: int, count: int) -> List[bool]:
        logging.debug(f"read coils, unit: {unit}, at: {address} count: {count}")
        bytes_count = (count + 7) // 8
        result = await self._run_with_retry(self.client.read_coils, slave=unit, address=address, count=bytes_count)
        if result.byte_count != bytes_count:
            raise ModbusException("Invalid bytes count")

        # noinspection PyTypeChecker
        return cast(List[bool], result.bits[:count])

    async def read_discrete_inputs(self, unit: int, address: int, count: int) -> List[int]:
        logging.debug(f"read discrete, unit: {unit}, at: {address} count: {count}")
        result = await self._run_with_retry(self.client.read_discrete_inputs, slave=unit, address=address, count=count)
        if result.byte_count != count:
            raise ModbusException("Invalid bytes count")

        values = []
        for byte_i in range(count):
            value = 0
            start_bit = 8 * byte_i
            end_bit = start_bit + 8
            for i, bit in enumerate(result.bits[start_bit:end_bit]):
                value |= bit << i
            values.append(value)
        return values

    async def read_input_registers(self, unit: int, address: int, count: int) -> List[int]:
        logging.debug(f"read input, unit: {unit}, at: {address} count: {count}")
        result = await self._run_with_retry(self.client.read_input_registers, slave=unit, address=address, count=count)
        if len(result.registers) != count:
            raise ModbusException("Invalid bytes count")
        # noinspection PyTypeChecker
        return cast(List[int], result.registers)

    async def read_holding_registers(self, unit: int, address: int, count: int) -> List[int]:
        logging.debug(f"read holding, unit: {unit}, at: {address} count: {count}")
        result = await self._run_with_retry(self.client.read_holding_registers, slave=unit, address=address, count=count)
        if len(result.registers) != count:
            raise ModbusException("Invalid bytes count")
        # noinspection PyTypeChecker
        return cast(List[int], result.registers)

    async def write_holding_register(self, unit: int, address: int, value: int) -> None:
        logging.debug(f"write holding, unit: {unit}, at: {address} value: {value}")
        await self._run_with_retry(self.client.write_register, slave=unit, address=address, value=value)

    async def write_holding_registers(self, unit: int, address: int, values: List[int]) -> None:
        s = ", ".join(f"0x{value:04x}" for value in values)
        logging.debug(f"write holding, unit: {unit}, at: {address} values: {s}")
        await self._run_with_retry(self.client.write_registers, slave=unit, address=address, values=values)

    def close(self) -> None:
        self.client.close()


class PyAsyncModbusTcpClient(PyAsyncModbusClient):
    def __init__(self,
                 host: str,
                 port: int,
                 *,
                 timeout: float = DefaultTimeout,
                 silent_interval: Optional[float] = None,
                 retry_count: int = DefaultRetryCount,
                 ):
        cl = pymodbus.client.tcp.ModbusTcpClient(host=host, port=port, timeout=timeout)

        if silent_interval is not None:
            cl.silent_interval = silent_interval

        super().__init__(cl, retry_count=retry_count)


class PyAsyncModbusRtuClient(PyAsyncModbusClient):
    def __init__(self,
                 path: str,
                 *,
                 baudrate: int = 9600,
                 stopbits: int = 1,
                 parity: str = "N",
                 timeout: float = DefaultTimeout,
                 silent_interval: Optional[float] = None,
                 retry_count: int = DefaultRetryCount,
                 ):
        cl = pymodbus.client.serial.ModbusSerialClient(method="rtu", port=path,
                                                       baudrate=baudrate, stopbits=stopbits, parity=parity,
                                                       timeout=timeout)
        if silent_interval is not None:
            cl.silent_interval = silent_interval

        super().__init__(cl, retry_count=retry_count)


class PyAsyncModbusRtuOverTcpClient(PyAsyncModbusClient):
    def __init__(self,
                 host: str,
                 port: int,
                 *,
                 timeout: float = DefaultTimeout,
                 silent_interval: Optional[float] = None,
                 retry_count: int = DefaultRetryCount,
                 ):
        cl = pymodbus.client.tcp.ModbusTcpClient(host=host, port=port, timeout=timeout, framer=ModbusRtuFramer)  # type: ignore

        if silent_interval is not None:
            cl.silent_interval = silent_interval

        super().__init__(cl, retry_count=retry_count)


__all__ = [
    "PyAsyncModbusClient",
    "PyAsyncModbusTcpClient",
    "PyAsyncModbusRtuClient",
    "PyAsyncModbusRtuOverTcpClient",
]
