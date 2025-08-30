from dataclasses import field
from typing import List, Optional

import yaml
from pydantic.dataclasses import dataclass


@dataclass
class RtuConfig:
    path: str
    baudrate: int


@dataclass
class TcpConfig:
    host: str
    port: int


@dataclass
class RtuOverTcpConfig:
    host: str
    port: int


@dataclass
class Device:
    name: str
    unit: int
    device: str

    rtu: Optional[RtuConfig] = None
    tcp: Optional[TcpConfig] = None
    rtu_over_tcp: Optional[RtuOverTcpConfig] = None


@dataclass
class SystemConfig:
    devices: List[Device] = field(default_factory=list)


def load_system_config(path: str) -> SystemConfig:
    return SystemConfig(**yaml.load(open(path, "rt"), Loader=yaml.SafeLoader))
