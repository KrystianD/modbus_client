Modbus client for Python
-----

Device oriented Modbus client. As opposed to bare modbus clients, it focuses on data meaning and data types. Uses pymodbus under the hood.

Supported data types:

- S16 (int16) - 16bit signed integer
- U16 (uint16) - 16bit unsigned integer
- S32BE (int32be) - 32bit signed integer, high word first
- S32LE (int32le) - 32bit signed integer, low word first
- U32BE (uint32be) - 32bit unsigned integer, high word first
- U32LE (uint32le) - 32bit unsigned integer, low word first
- S64BE (int64be) - 64bit signed integer, high word first
- S64LE (int64le) - 64bit signed integer, low word first
- U64BE (uint64be) - 64bit unsigned integer, high word first
- U64LE (uint64le) - 64bit unsigned integer, low word first
- F32BE (float32be) - IEEE 754 32bit float, high word first
- F32LE (float32le) - IEEE 754 32bit float, low word first
- ENUM (enum) - list of named numeric values
- BOOL (bool) - single bit value
- FLAGS (flags) - bit flags
- STRING (string) - null-terminated ASCII string spanning over multiple Modbus registers (words)

Within the word, it assumes data is stored Least Significant Bit first.

Supports multiple values within a single register. For example, 16-bit register at 0x0010 may contain:

- one bool on bit 15,
- one 2-bit enum with 8 possible value (on bits 12, 11),
- one 3-bit integer (on bits 10, 9, 8),
- one 8-bit integer (on bits 7, 6, 5, 4, 3, 2, 1, 0).

#### Installation

```shell
pip install git+https://github.com/KrystianD/modbus_client
```

#### Example

Take a made up example of an energy meter device with 3 registers:

- 0x0001 - voltage, 1 word (2 bytes), LSB = 0.1 V
- 0x0002 - energy, 2 words (4 bytes), high word first, LSB = 1 Wh
- 0x0010 - configuration

```
==========================
| Type | Address | Value |
==========================
| IR   |  0x0001 |   123 |
| IR   |  0x0002 |     1 |
| IR   |  0x0003 |    50 |
| HR   |  0x0010 |  4146 |
==========================
```

`config.yaml` file content

```yaml
zero_mode: True # if true, "address: 1" means second register, otherwise, "address: 1" means first register

registers:
  input_registers:
    - name: voltage
      address: 0x0001
      type: uint16
      scale: 0.1
      unit: V
    
    - name: energy
      address: 0x0002
      type: uint32be
      unit: Wh
    
    # or in short form:
    # - voltage/0x0001/uint16*0.1[V]
    # - energy/0x0002/uint32be[Wh] 
  
  holding_registers:
    - pulse_enabled   / 0x0010 / bool,bit=15
    
    - name: parity
      address: 0x0010
      type: enum
      bits: "12:11"
      enum:
        - { name: none, value: 0 }
        - { name: odd, value: 1 }
        - { name: even, value: 2 }
    
    - baudrate        / 0x0010 / uint16,bits=10:8
    
    - slave_id        / 0x0010 / uint16,bits=7:0
```

#### Library usage

```python
import asyncio

from modbus_client.client.pymodbus_async_modbus_client import PyAsyncModbusTcpClient
from modbus_client.device.modbus_device import ModbusDeviceFactory


async def main():
    modbus_client = PyAsyncModbusTcpClient(host="192.168.1.10", port=4444, timeout=3)
    # modbus_client = PyAsyncModbusRtuClient(path="/dev/ttyUSB0", baudrate=9600, stopbits=1, parity='N', timeout=3)
    modbus_device_factory = ModbusDeviceFactory.from_file("config.yaml")
    modbus_device = modbus_device_factory.create_device(unit=1)
    voltage = await modbus_device.read_register(modbus_client, register="voltage")
    energy = await modbus_device.read_register(modbus_client, register="energy")
    print(voltage)  # 12.3
    print(energy)  # 65586

    await modbus_device.write_register(modbus_client, "pulse_enabled", True)
    await modbus_device.write_register(modbus_client, "parity", "even")
    await modbus_device.write_register(modbus_client, "baudrate", 3)
    # 0x0010 now has value of 37682


asyncio.run(main())
```

#### CLI usage:

```bash
python -m cli device config.yaml <connection-params> --unit 1 read voltage
python -m cli device config.yaml <connection-params> --unit 1 read energy
```

#### Features

- Merging read requests
- System config file support (storing devices addresses/paths and their unit numbers in config file for easy querying)
