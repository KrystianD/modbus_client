import argparse
import asyncio
import datetime
import os
from dataclasses import dataclass
from typing import Tuple, Any, Optional, List, Sequence, cast, Callable, Union, Dict

from cli.argument_parsers import interval_parser, mode_parser, ModeTupleType
from cli.system_file import load_system_config
from modbus_client.async_modbus_client import AsyncModbusClient
from modbus_client.pymodbus_async_modbus_client import PyAsyncModbusTcpClient, PyAsyncModbusRtuClient
from modbus_client.registers import IRegister
from modbus_client.types import ModbusReadSession
from modbus_device.device_config import DeviceHoldingRegister, DeviceSwitch, DeviceConfig, DeviceInputRegister, \
    IDeviceRegister
from modbus_device.modbus_device import create_modbus_register, ModbusDevice, create_modbus_coil

script_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.join(script_dir, "..")

DeviceCreationResult = Tuple[ModbusDevice, int, AsyncModbusClient]


@dataclass
class Args:
    cmd: str
    create_device: Callable[['Args'], Optional[DeviceCreationResult]]
    device_mode: str
    host: str
    port: int
    path: str
    mode: ModeTupleType
    unit: int
    device: str
    name: str
    value: str
    interval: float


def create_device_from_args(args: Args) -> DeviceCreationResult:
    device_mode = args.device_mode
    modbus_device = ModbusDevice.create_from_file(vars(args)["device-file"])

    client: AsyncModbusClient
    if device_mode == "tcp":
        client = PyAsyncModbusTcpClient(host=args.host, port=args.port, timeout=3)
    elif device_mode == "rtu":
        client = PyAsyncModbusRtuClient(
            path=args.path, baudrate=args.mode[0], stopbits=args.mode[2], parity=args.mode[1], timeout=3)
    else:
        raise Exception("invalid mode")

    return modbus_device, args.unit, client


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
        modbus_device = ModbusDevice.create_from_file(device.device)
        client = PyAsyncModbusTcpClient(host=device.host, port=device.port, timeout=3)
        return modbus_device, device.unit, client


async def query_device(device_config: DeviceConfig, client: AsyncModbusClient, unit: int,
                       registers: List[IDeviceRegister] = [],
                       switches: List[DeviceSwitch] = [],
                       show_register_names: bool = False,
                       show_registers_types: bool = False,
                       interval: Optional[float] = None) -> None:
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
        for register in registers_to_print:
            modbus_register = modbus_registers_map[register.name]

            if show_register_names:
                print(f"{register.name:>{max_name_len}s} = ", end="")

            print(f"{modbus_register.format(read_ses)}")

    read_num = 0
    while True:
        read_ses = await client.read_registers(unit=unit, registers=modbus_registers)

        if interval is not None:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if len(registers) > 1:
                print()
                print(f"===============================")
                print(f"| {f'#{read_num}':>5} - {date_str} |")
                print(f"===============================")
            else:
                print(f"[{f'#{read_num}':>5} - {date_str}] ", end="")

        if len(input_registers) > 0:
            if show_registers_types:
                print("Input registers:")
            print_registers(input_registers)

        if show_registers_types and len(input_registers) > 0:
            print()

        if len(holding_registers) > 0:
            if show_registers_types:
                print("Holding registers:")
            print_registers(holding_registers)

        if show_registers_types and len(holding_registers) > 0:
            print()

        if len(switches) > 0:
            if show_registers_types:
                print("Switches:")
            print_registers(switches)

        if interval is None:
            break
        else:
            await asyncio.sleep(interval)
            read_num += 1


async def handle_list(device_config: DeviceConfig) -> None:
    print("Input registers:")
    for holding_register in device_config.registers.input_registers:
        print("  ", holding_register.name)

    print("Holding registers:")
    for input_register in device_config.registers.holding_registers:
        print("  ", input_register.name)

    print("Coils:")
    for switch in device_config.switches:
        print("  ", switch.name)


async def handle_read(device_config: DeviceConfig, client: AsyncModbusClient, unit: int, name: str) -> None:
    register = device_config.find_register(name)
    if register is not None:
        await query_device(device_config, client, unit, registers=[register], show_registers_types=False)
        return

    switch = device_config.find_switch(name)
    if switch is not None:
        await query_device(device_config, client, unit, switches=[switch], show_registers_types=False)
        return

    print(f"Register or switch [{name}] not found")


async def handle_watch(device_config: DeviceConfig, client: AsyncModbusClient, unit: int, name: str,
                       interval: float) -> None:
    register = device_config.find_register(name)
    if register is not None:
        await query_device(device_config, client, unit, registers=[register], show_registers_types=False,
                           interval=interval)
        return

    switch = device_config.find_switch(name)
    if switch is not None:
        await query_device(device_config, client, unit, switches=[switch], show_registers_types=False,
                           interval=interval)
        return

    print(f"Register or switch [{name}] not found")


async def handle_write(device_config: DeviceConfig, client: AsyncModbusClient, modbus_device: ModbusDevice, unit: int,
                       name: str, value: float) -> None:
    register = device_config.find_register(name)
    if register is None:
        print("Register not found")
        exit(1)

    await modbus_device.write_register(client, unit, register, value)


async def handle_enable(device_config: DeviceConfig, client: AsyncModbusClient, modbus_device: ModbusDevice, unit: int,
                        name: str) -> None:
    switch = device_config.find_switch(name)
    if switch is None:
        print("Switch not found")
        exit(1)

    await modbus_device.switch_set(client, unit, switch, True)


async def handle_disable(device_config: DeviceConfig, client: AsyncModbusClient, modbus_device: ModbusDevice, unit: int,
                         name: str) -> None:
    switch = device_config.find_switch(name)
    if switch is None:
        print("Switch not found")
        exit(1)

    await modbus_device.switch_set(client, unit, switch, False)


async def handle_toggle(device_config: DeviceConfig, client: AsyncModbusClient, modbus_device: ModbusDevice, unit: int,
                        name: str) -> None:
    switch = device_config.find_switch(name)
    if switch is None:
        print("Switch not found")
        exit(1)

    await modbus_device.switch_toggle(client, unit, switch)


async def main() -> None:
    argparser = argparse.ArgumentParser()

    argparser.add_argument("--format", type=str, choices=("raw", "pretty", "json"), default="pretty")

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
        read_parser.add_argument("name")

        watch_parser = subparsers.add_parser('watch')
        watch_parser.set_defaults(cmd="watch")
        watch_parser.add_argument("name")
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
    add_commands_parser(system_p)

    args = cast(Args, argparser.parse_args())

    if "create_device" not in cast(Any, args):
        argparser.print_help()
        exit(1)

    res = args.create_device(args)
    if res is None:
        system_p.print_help()
        exit(1)

    modbus_device: ModbusDevice
    modbus_device, unit, client = res

    device_config = modbus_device.get_config()

    if "cmd" not in cast(Any, args):
        print("Specify command")
        exit(1)

    if args.cmd == "list":
        await handle_list(device_config)

    if args.cmd == "read":
        await handle_read(device_config, client, unit, args.name)

    if args.cmd == "watch":
        await handle_watch(device_config, client, unit, args.name, args.interval)

    if args.cmd == "read-all":
        await query_device(device_config, client, unit,
                           registers=device_config.get_all_registers(),
                           switches=device_config.switches,
                           show_register_names=True,
                           show_registers_types=True)

    if args.cmd == "watch-all":
        await query_device(device_config, client, unit,
                           registers=device_config.get_all_registers(),
                           switches=device_config.switches,
                           show_register_names=True,
                           show_registers_types=True,
                           interval=args.interval)

    if args.cmd == "write":
        await handle_write(device_config, client, modbus_device, unit, args.name, float(args.value))

    if args.cmd == "enable":
        await handle_enable(device_config, client, modbus_device, unit, args.name)

    if args.cmd == "disable":
        await handle_disable(device_config, client, modbus_device, unit, args.name)

    if args.cmd == "toggle":
        await handle_toggle(device_config, client, modbus_device, unit, args.name)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
