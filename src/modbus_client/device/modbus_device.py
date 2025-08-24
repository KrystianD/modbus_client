from typing import Union, List, Dict

from modbus_client.client.async_modbus_client import AsyncModbusClient
from modbus_client.device.registers.device_register import DeviceInputRegister, DeviceHoldingRegister, SwitchRegisterTypeEnum, \
    IDeviceRegister, DeviceSwitch
from modbus_client.device.registers.enum_definition import EnumDefinition
from modbus_client.device.registers.register_type import RegisterType
from modbus_client.registers.read_session import ModbusReadSession
from modbus_client.registers.register_value_type import RegisterValueType
from modbus_client.registers.registers import NumericRegister, Coil, IRegister, EnumValue, EnumRegister
from modbus_client.client.types import ModbusRegisterType
from modbus_client.device.device_config import DeviceConfig, load_device_config, load_device_config_from_yaml
from modbus_client.device.device_config_finder import find_device_file


def create_modbus_register(device: DeviceConfig, register: IDeviceRegister) -> Union[NumericRegister, EnumRegister]:
    zero_offset = 0 if device.zero_mode else 1
    address = register.address - zero_offset

    if isinstance(register, DeviceInputRegister):
        reg_type = ModbusRegisterType.InputRegister
    elif isinstance(register, DeviceHoldingRegister):
        reg_type = ModbusRegisterType.HoldingRegister
    else:
        raise Exception("invalid type")

    if register.type == RegisterType.ENUM:
        assert register.enum is not None
        return EnumRegister(name=register.name, reg_type=reg_type, value_type=RegisterValueType.U16,
                            address=address, enum=register.enum,
                            bits=register.bits.bits if register.bits is not None else None)
    else:
        return NumericRegister(name=register.name, reg_type=reg_type, value_type=RegisterValueType(register.type),
                               address=address, scale=register.scale, unit=register.unit,
                               bits=register.bits.bits if register.bits is not None else None)


def create_modbus_coil(device: DeviceConfig, register: DeviceSwitch) -> Coil:
    zero_offset = 0 if device.zero_mode else 1
    number = register.number - zero_offset

    if register.type == SwitchRegisterTypeEnum.Coil:
        reg_type = ModbusRegisterType.Coil
    else:
        raise Exception("invalid type")

    return Coil(name=register.name, reg_type=reg_type, number=number)


class ModbusDeviceFactory:
    def __init__(self, device_config: DeviceConfig):
        self._device_config = device_config

    def create_device(self, unit: int) -> 'ModbusDevice':
        return ModbusDevice(self._device_config, unit)

    @staticmethod
    def from_file(path: str) -> 'ModbusDeviceFactory':
        device = load_device_config(find_device_file(path))
        return ModbusDeviceFactory(device)

    @staticmethod
    def from_config(config: str) -> 'ModbusDeviceFactory':
        device = load_device_config_from_yaml(config)
        return ModbusDeviceFactory(device)


class ModbusDevice:
    def __init__(self, device_config: DeviceConfig, unit: int):
        self._device_config = device_config
        self._unit = unit

    def get_device_config(self) -> DeviceConfig:
        return self._device_config

    def get_unit(self) -> int:
        return self._unit

    def get_register(self, name: str) -> IDeviceRegister:
        reg = self._device_config.find_register(name)
        assert reg is not None
        return reg

    def get_switch(self, name: str) -> DeviceSwitch:
        switch = self._device_config.find_switch(name)
        assert switch is not None
        return switch

    def create_modbus_register(self, register: Union[str, IDeviceRegister]) -> IRegister:
        if isinstance(register, IDeviceRegister):
            return create_modbus_register(self._device_config, register)
        elif isinstance(register, str):
            return create_modbus_register(self._device_config, self.get_register(register))
        else:
            raise Exception("Invalid register type")

    def create_modbus_switch(self, switch: Union[str, DeviceSwitch]) -> Coil:
        if isinstance(switch, DeviceSwitch):
            return create_modbus_coil(self._device_config, switch)
        elif isinstance(switch, str):
            return create_modbus_coil(self._device_config, self.get_switch(switch))
        else:
            raise Exception("Invalid switch type")

    async def read_register(self, client: AsyncModbusClient, register: Union[str, IDeviceRegister]) \
            -> Union[int, float, EnumValue]:
        modbus_register = self.create_modbus_register(register)

        read_session = await ModbusReadSession.read_registers(client=client,
                                                              unit=self._unit,
                                                              registers=[modbus_register],
                                                              allow_holes=self._device_config.allow_holes,
                                                              max_read_size=self._device_config.max_read_size)

        return modbus_register.get_value_from_read_session(read_session)

    async def read_registers(self, client: AsyncModbusClient, registers: List[Union[str, IDeviceRegister]]) \
            -> Dict[str, Union[int, float, EnumValue]]:
        modbus_registers = [self.create_modbus_register(x) for x in registers]

        read_session = await ModbusReadSession.read_registers(client=client,
                                                              unit=self._unit,
                                                              registers=modbus_registers,
                                                              allow_holes=self._device_config.allow_holes,
                                                              max_read_size=self._device_config.max_read_size)

        return {x.name: x.get_value_from_read_session(read_session) for x in modbus_registers}

    async def write_register(self, client: AsyncModbusClient, register: Union[str, IDeviceRegister],
                             value: Union[float, int, str, EnumDefinition]) -> None:
        if isinstance(value, EnumDefinition):
            value = value.value

        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                value = str(value)

        modbus_register = self.create_modbus_register(register)

        ses = ModbusReadSession()
        if modbus_register.requires_existing_reading():
            ses = await ModbusReadSession.read_registers(client=client, unit=self._unit, registers=[modbus_register])

        modbus_values = modbus_register.value_to_modbus_registers(value, ses)

        if self._device_config.force_multiple_write or len(modbus_values) > 1:
            await client.write_holding_registers(unit=self._unit, address=modbus_register.address, values=modbus_values)
        else:
            await client.write_holding_register(unit=self._unit, address=modbus_register.address, value=modbus_values[0])

    async def read_switch(self, client: AsyncModbusClient, switch: Union[str, DeviceSwitch]) -> bool:
        modbus_register = self.create_modbus_switch(switch)

        read_session = await ModbusReadSession.read_registers(client=client, unit=self._unit, registers=[modbus_register])

        return modbus_register.get_from_read_session(read_session)

    async def switch_set(self, client: AsyncModbusClient, switch: Union[str, DeviceSwitch],
                         value: bool) -> None:
        modbus_register = self.create_modbus_switch(switch)

        await client.write_coil(unit=self._unit, address=modbus_register.number, value=value)

    async def switch_toggle(self, client: AsyncModbusClient, switch: Union[str, DeviceSwitch]) -> None:
        current_value = await self.read_switch(client, switch)
        await self.switch_set(client, switch, not current_value)
