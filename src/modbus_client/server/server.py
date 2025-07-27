import json
import os.path
from typing import Any

import uvicorn
from nicegui import app
from nicegui import ui
from starlette.responses import Response

from modbus_client.client.async_modbus_client import AsyncModbusClient
from modbus_client.client.defaults import DefaultTimeout, DefaultSilentInterval
from modbus_client.client.mock_modbus_client import MockModbusClient
from modbus_client.client.pymodbus_async_modbus_client import PyAsyncModbusTcpClient, PyAsyncModbusRtuClient, PyAsyncModbusRtuOverTcpClient
from modbus_client.device.modbus_device import ModbusDeviceFactory
from modbus_client.server.frontend_ui import register_ui
from modbus_client.server.mytypes import Connector
from modbus_client.server.runtime_data import RuntimeData
from modbus_client.server.server_config import load_server_config, ServerConfig


class PrettyJSONResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return json.dumps(content, indent=2, sort_keys=True).encode("utf-8")


def create_device_from_args(server_config: ServerConfig) -> Connector:
    modbus_device = ModbusDeviceFactory.from_file(server_config.device_file).create_device(server_config.unit)

    config = modbus_device.get_device_config()

    timeout = config.default_timeout or DefaultTimeout
    silent_interval = config.default_silent_interval or DefaultSilentInterval

    client: AsyncModbusClient
    if server_config.tcp is not None:
        client = PyAsyncModbusTcpClient(host=server_config.tcp.host, port=server_config.tcp.port,
                                        timeout=timeout,
                                        silent_interval=silent_interval)
    elif server_config.rtu is not None:
        client = PyAsyncModbusRtuClient(path=server_config.rtu.path, baudrate=server_config.rtu.baudrate,
                                        timeout=timeout,
                                        silent_interval=silent_interval)
    elif server_config.rtu_over_tcp is not None:
        client = PyAsyncModbusRtuOverTcpClient(host=server_config.rtu_over_tcp.host, port=server_config.rtu_over_tcp.port,
                                               timeout=timeout,
                                               silent_interval=silent_interval)
    elif server_config.mock is not None:
        client = MockModbusClient(input_registers={}, holding_registers={}, missing_as_zero=True)
    else:
        raise Exception("invalid mode")

    return Connector(modbus_device, lambda: client)


def run_server(args: Any) -> None:
    server_config = load_server_config(args.config)

    connector = create_device_from_args(server_config)

    runtime_data = RuntimeData(server_config, connector)

    register_ui(runtime_data)

    ui.run_with(app, mount_path=args.base_href,
                title=f"Modbus - {os.path.splitext(os.path.basename(server_config.device_file))[0]}",
                dark=args.dark_mode)

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, access_log=False)
