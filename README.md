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
- F32BE (float32be) - IEEE 754 32bit float, high word first
- F32LE (float32le) - IEEE 754 32bit float, low word first

Within the word, it assumes data is stored Least Significant Bit first.

#### Example

Take an example energy meter device with 2 registers:

- 0x0001 - voltage, 1 word (2 bytes), LSB = 0.1 V
- 0x0002 - energy, 2 words (4 bytes), high word first, LSB = 1 Wh

```
===================
| Address | Value |
===================
|  0x0001 |   123 |
|  0x0002 |     1 |
|  0x0003 |    50 |
===================
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
```

#### Library usage

```python
import asyncio
from modbus_client.pymodbus_async_modbus_client import PyAsyncModbusTcpClient
from modbus_device.modbus_device import ModbusDevice

async def main():
    modbus_client = PyAsyncModbusTcpClient(host="192.168.1.10", port=4444, timeout=3)
    # modbus_client = PyAsyncModbusRtuClient(path="/dev/ttyUSB0", baudrate=9600, stopbits=1, parity='N', timeout=3)
    modbus_device = ModbusDevice.create_from_file("config.yaml")
    voltage = await modbus_device.read_register(modbus_client, unit=1, register="voltage")
    energy = await modbus_device.read_register(modbus_client, unit=1, register="energy")
    print(voltage) # 12.3
    print(energy) # 65586

asyncio.get_event_loop().run_until_complete(main())
```

#### CLI usage:

```bash
python -m cli device config.yaml <connection-params> --unit 1 read voltage
python -m cli device config.yaml <connection-params> --unit 1 read energy
```

#### Features

- Merging read requests
- System config file support (storing devices addresses/paths and their unit numbers in config file for easy querying)
