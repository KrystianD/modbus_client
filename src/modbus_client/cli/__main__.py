import argparse
import asyncio
import datetime
import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Tuple, Any, Optional, List, Sequence, cast, Callable, Union, Dict

from modbus_client.cli.argument_parsers import interval_parser, mode_parser, ModeTupleType
from modbus_client.cli.system_file import load_system_config
from modbus_client.client.async_modbus_client import AsyncModbusClient
from modbus_client.client.pymodbus_async_modbus_client import PyAsyncModbusTcpClient, PyAsyncModbusRtuClient, PyAsyncModbusRtuOverTcpClient
from modbus_client.device.registers.device_register import IDeviceRegister, DeviceHoldingRegister, DeviceInputRegister, DeviceSwitch
from modbus_client.registers.read_session import ModbusReadSession
from modbus_client.registers.registers import IRegister
from modbus_client.device.device_config import DeviceConfig
from modbus_client.device.modbus_device import create_modbus_register, ModbusDevice, create_modbus_coil, ModbusDeviceFactory

script_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.join(script_dir, "../../..")

DeviceCreationResult = Tuple[ModbusDevice, AsyncModbusClient]


@dataclass
class Args:
    format: str
    cmd: str
    create_device: Callable[['Args'], Optional[DeviceCreationResult]]
    device_mode: str
    host: str
    port: int
    path: str
    mode: ModeTupleType
    unit: int
    device: str
    name: Union[str, List[str]]
    value: str
    interval: float
    timeout: float
    silent_interval: float
    verbose: bool


def create_device_from_args(args: Args) -> DeviceCreationResult:
    device_mode = args.device_mode
    modbus_device = ModbusDeviceFactory.from_file(vars(args)["device-file"]).create_device(args.unit)

    client: AsyncModbusClient
    if device_mode == "tcp":
        client = PyAsyncModbusTcpClient(host=args.host, port=args.port, timeout=args.timeout, silent_interval=args.silent_interval)
    elif device_mode == "rtu":
        client = PyAsyncModbusRtuClient(
                path=args.path, baudrate=args.mode[0], stopbits=args.mode[2], parity=args.mode[1], timeout=args.timeout,
                silent_interval=args.silent_interval)
    elif device_mode == "rtu-over-tcp":
        client = PyAsyncModbusRtuOverTcpClient(host=args.host, port=args.port, timeout=args.timeout, silent_interval=args.silent_interval)
    else:
        raise Exception("invalid mode")

    return modbus_device, client


def create_device_from_system_file(args: Args) -> DeviceCreationResult:
    device_name = vars(args)["device-name"]
    system_file = vars(args)["system-file"]
    system_config = load_system_config(system_file)

    if device_name == "list":
        for dev in system_config.devices:
            print("  ", dev.name)
        exit(0)
    else:
        devices = [x for x in system_config.devices if x.name == device_name]
        if len(devices) == 0:
            print("no matching device")
            exit(1)
        device = devices[0]
        modbus_device = ModbusDeviceFactory.from_file(device.device).create_device(device.unit)
        client = PyAsyncModbusTcpClient(host=device.host, port=device.port, timeout=3)
        return modbus_device, client


async def query_device(client: AsyncModbusClient, device: ModbusDevice,
                       format: str,
                       registers: Optional[List[IDeviceRegister]] = None,
                       switches: Optional[List[DeviceSwitch]] = None,
                       show_register_names: bool = False,
                       show_registers_types: bool = False,
                       interval: Optional[float] = None) -> None:
    device_config = device.get_device_config()

    if registers is None:
        registers = []
    if switches is None:
        switches = []
    holding_registers = [x for x in registers if isinstance(x, DeviceHoldingRegister)]
    input_registers = [x for x in registers if isinstance(x, DeviceInputRegister)]
    all_registers: List[Union[IDeviceRegister, DeviceSwitch]] = [*registers, *switches]
    max_name_len = max(len(x.name) for x in all_registers)

    modbus_registers_map: Dict[str, IRegister] = {}
    modbus_registers_map.update({register.name: create_modbus_register(device_config, register)
                                 for register in registers})
    modbus_registers_map.update({switch.name: create_modbus_coil(device_config, switch) for switch in switches})
    modbus_registers = list(modbus_registers_map.values())

    read_ses: ModbusReadSession

    def print_registers(registers_to_print: Sequence[Union[IDeviceRegister, DeviceSwitch]]) -> None:
        if format == "pretty":
            for register in registers_to_print:
                modbus_register = modbus_registers_map[register.name]

                if show_register_names:
                    print(f"{register.name:>{max_name_len}s} = ", end="")

                print(f"{modbus_register.format(read_ses)}")

        if format == "json":
            data: Any
            if show_register_names:
                data = {}
            else:
                data = []
            for register in registers_to_print:
                modbus_register = modbus_registers_map[register.name]
                value = modbus_register.get_value_from_read_session(read_ses)
                if show_register_names:
                    data[register.name] = value
                else:
                    data.append(value)
            sys.stdout.write(json.dumps(data) + "\n")

        if format == "raw":
            data = []
            for register in registers_to_print:
                modbus_register = modbus_registers_map[register.name]
                value = modbus_register.get_value_from_read_session(read_ses)
                data.append(value)
            sys.stdout.write(",".join([f"{x}" for x in data]) + "\n")

        sys.stdout.flush()

    read_num = 0
    while True:
        read_num += 1

        try:
            read_ses = await ModbusReadSession.read_registers(client=client, unit=device.get_unit(), registers=modbus_registers,
                                                              allow_holes=device_config.allow_holes,
                                                              max_read_size=device_config.max_read_size)
        except Exception as e:
            if interval is None:
                print(f"ERROR: {e}")
                exit(1)
            else:
                if format == "pretty":
                    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if len(registers) > 1:
                        print()
                        print(f"===============================")
                        print(f"| {f'#{read_num}':>5} - {date_str} |")
                        print(f"===============================")
                        print(f"READ ERROR {str(e)}")
                    else:
                        print(f"[{f'#{read_num}':>5} - {date_str}] READ ERROR: {str(e)}")

                await asyncio.sleep(interval)
                continue

        if interval is not None:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if format == "pretty":
                if len(registers) > 1:
                    print()
                    print(f"===============================")
                    print(f"| {f'#{read_num}':>5} - {date_str} |")
                    print(f"===============================")
                else:
                    print(f"[{f'#{read_num}':>5} - {date_str}] ", end="")

        if len(input_registers) > 0:
            if format == "pretty":
                if show_registers_types:
                    print("Input registers:")
            print_registers(input_registers)

        if format == "pretty":
            if show_registers_types and len(input_registers) > 0:
                print()

        if len(holding_registers) > 0:
            if format == "pretty":
                if show_registers_types:
                    print("Holding registers:")
            print_registers(holding_registers)

        if format == "pretty":
            if show_registers_types and len(holding_registers) > 0:
                print()

        if len(switches) > 0:
            if format == "pretty":
                if show_registers_types:
                    print("Switches:")
            print_registers(switches)

        if interval is None:
            break
        else:
            await asyncio.sleep(interval)


async def handle_list(device_config: DeviceConfig) -> None:
    print("Input registers:")
    for holding_register in device_config.registers.input_registers:
        print("  ", holding_register.name)
        if holding_register.enum is not None:
            for enum_item in holding_register.enum:
                print(f"    - {enum_item.name} = {enum_item.value}")

    print("Holding registers:")
    for input_register in device_config.registers.holding_registers:
        print("  ", input_register.name)
        if input_register.enum is not None:
            for enum_item in input_register.enum:
                print(f"    - {enum_item.name} = {enum_item.value}")

    print("Coils:")
    for switch in device_config.switches:
        print("  ", switch.name)


async def handle_read(client: AsyncModbusClient, device: ModbusDevice, names: List[str],
                      format: str) -> None:
    registers: List[IDeviceRegister] = []
    switches: List[DeviceSwitch] = []
    for name in names:
        register = device.get_device_config().find_register(name)
        if register is not None:
            registers.append(register)
        else:
            switch = device.get_device_config().find_switch(name)
            if switch is not None:
                switches.append(switch)
            else:
                print(f"Register or switch [{name}] not found")

    await query_device(client, device, registers=registers, switches=switches, show_registers_types=False, format=format,
                       show_register_names=len(names) > 1)


async def handle_watch(client: AsyncModbusClient, device: ModbusDevice, names: List[str], format: str,
                       interval: float) -> None:
    registers: List[IDeviceRegister] = []
    switches: List[DeviceSwitch] = []
    for name in names:
        register = device.get_device_config().find_register(name)
        if register is not None:
            registers.append(register)
        else:
            switch = device.get_device_config().find_switch(name)
            if switch is not None:
                switches.append(switch)
            else:
                print(f"Register or switch [{name}] not found")

    await query_device(client, device, registers=registers, switches=switches, show_registers_types=False, format=format,
                       interval=interval, show_register_names=len(names) > 1)


async def handle_write(client: AsyncModbusClient, device: ModbusDevice,
                       name: str, value: Union[int, float, str]) -> None:
    register = device.get_device_config().find_register(name)
    if register is None:
        print("Register not found")
        exit(1)

    await device.write_register(client, register, value)


async def handle_enable(client: AsyncModbusClient, device: ModbusDevice,
                        name: str) -> None:
    switch = device.get_device_config().find_switch(name)
    if switch is None:
        print("Switch not found")
        exit(1)

    await device.switch_set(client, switch, True)


async def handle_disable(client: AsyncModbusClient, device: ModbusDevice,
                         name: str) -> None:
    switch = device.get_device_config().find_switch(name)
    if switch is None:
        print("Switch not found")
        exit(1)

    await device.switch_set(client, switch, False)


async def handle_toggle(client: AsyncModbusClient, device: ModbusDevice,
                        name: str) -> None:
    switch = device.get_device_config().find_switch(name)
    if switch is None:
        print("Switch not found")
        exit(1)

    await device.switch_toggle(client, switch)


async def main() -> None:
    argparser = argparse.ArgumentParser()

    argparser.add_argument("--format", type=str, choices=("raw", "pretty", "json"), default="pretty")
    argparser.add_argument("--timeout", type=float, default=3)
    argparser.add_argument("--silent-interval", type=float)
    argparser.add_argument("-v", "--verbose", action='store_true')

    mode_subparser = argparser.add_subparsers(title='standalone device', description='valid subcommands')
    dev_p = mode_subparser.add_parser("device")
    dev_p.set_defaults(create_device=lambda x: create_device_from_args(x))
    dev_p.add_argument("device-file", type=str)

    dev_sp = dev_p.add_subparsers(title="MODBUS mode")

    dev_tcp_p = dev_sp.add_parser("tcp")
    dev_tcp_p.set_defaults(device_mode="tcp")
    dev_tcp_p.set_defaults(create_device=lambda x: create_device_from_args(x))
    dev_tcp_p.add_argument("--host", type=str, required=True)
    dev_tcp_p.add_argument("--port", type=int, required=True)
    dev_tcp_p.add_argument("--unit", type=int, required=True)

    dev_rtu_p = dev_sp.add_parser("rtu")
    dev_rtu_p.set_defaults(device_mode="rtu")
    dev_rtu_p.set_defaults(create_device=lambda x: create_device_from_args(x))
    dev_rtu_p.add_argument("--path", type=str, required=True)
    dev_rtu_p.add_argument("--mode", type=mode_parser, default="9600n1", help="default 9600n1")
    dev_rtu_p.add_argument("--unit", type=int, required=True)

    dev_rtu_over_tcp_p = dev_sp.add_parser("rtu-over-tcp")
    dev_rtu_over_tcp_p.set_defaults(device_mode="rtu-over-tcp")
    dev_rtu_over_tcp_p.set_defaults(create_device=lambda x: create_device_from_args(x))
    dev_rtu_over_tcp_p.add_argument("--host", type=str, required=True)
    dev_rtu_over_tcp_p.add_argument("--port", type=int, required=True)
    dev_rtu_over_tcp_p.add_argument("--unit", type=int, required=True)

    system_p = mode_subparser.add_parser("system")
    system_p.set_defaults(create_device=lambda x: create_device_from_system_file(x))
    system_p.add_argument("system-file", type=str)
    system_p.add_argument("device-name", type=str)

    def add_commands_parser(sp: argparse.ArgumentParser) -> None:
        subparsers = sp.add_subparsers(title='subcommands', description='valid subcommands', help='additional help')

        list_parser = subparsers.add_parser('list')
        list_parser.set_defaults(cmd="list")

        read_parser = subparsers.add_parser('read')
        read_parser.set_defaults(cmd="read")
        read_parser.add_argument("name", nargs="+")

        watch_parser = subparsers.add_parser('watch')
        watch_parser.set_defaults(cmd="watch")
        watch_parser.add_argument("name", nargs="+")
        watch_parser.add_argument("--interval", type=interval_parser, default="1s")

        write_parser = subparsers.add_parser('write')
        write_parser.set_defaults(cmd="write")
        write_parser.add_argument("name")
        write_parser.add_argument("value")

        read_all_parser = subparsers.add_parser('read-all')
        read_all_parser.set_defaults(cmd="read-all")

        watch_all_parser = subparsers.add_parser('watch-all')
        watch_all_parser.set_defaults(cmd="watch-all")
        watch_all_parser.add_argument("--interval", type=interval_parser, default="1s")

        switch_parser = subparsers.add_parser('enable')
        switch_parser.set_defaults(cmd="enable")
        switch_parser.add_argument("name")

        switch_parser = subparsers.add_parser('disable')
        switch_parser.set_defaults(cmd="disable")
        switch_parser.add_argument("name")

        switch_parser = subparsers.add_parser('toggle')
        switch_parser.set_defaults(cmd="toggle")
        switch_parser.add_argument("name")

    add_commands_parser(dev_tcp_p)
    add_commands_parser(dev_rtu_p)
    add_commands_parser(dev_rtu_over_tcp_p)
    add_commands_parser(system_p)

    args = cast(Args, argparser.parse_args())

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="[%(asctime)s] [%(name)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")

    if "create_device" not in cast(Any, args):
        argparser.print_help()
        exit(1)

    res = args.create_device(args)
    if res is None:
        system_p.print_help()
        exit(1)

    modbus_device: ModbusDevice
    modbus_device, client = res

    device_config = modbus_device.get_device_config()

    if "cmd" not in cast(Any, args):
        print("Specify command")
        exit(1)

    if args.cmd == "list":
        await handle_list(device_config)

    if args.cmd == "read":
        await handle_read(client, modbus_device, cast(List[str], args.name), args.format)

    if args.cmd == "watch":
        await handle_watch(client, modbus_device, cast(List[str], args.name), args.format, args.interval)

    if args.cmd == "read-all":
        await query_device(client, modbus_device,
                           registers=device_config.get_all_registers(),
                           switches=device_config.switches,
                           show_register_names=True,
                           show_registers_types=True,
                           format=args.format)

    if args.cmd == "watch-all":
        await query_device(client, modbus_device,
                           registers=device_config.get_all_registers(),
                           switches=device_config.switches,
                           show_register_names=True,
                           show_registers_types=True,
                           interval=args.interval,
                           format=args.format)

    if args.cmd == "write":
        await handle_write(client, modbus_device, cast(str, args.name), args.value)

    if args.cmd == "enable":
        await handle_enable(client, modbus_device, cast(str, args.name))

    if args.cmd == "disable":
        await handle_disable(client, modbus_device, cast(str, args.name))

    if args.cmd == "toggle":
        await handle_toggle(client, modbus_device, cast(str, args.name))


def main_cli() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())


if __name__ == "__main__":
    main_cli()
