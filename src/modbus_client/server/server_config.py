from typing import Optional, Any

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
class ServerConfig:
    device_file: str
    unit: int
    mock: Optional[Any] = None
    rtu: Optional[RtuConfig] = None
    tcp: Optional[TcpConfig] = None
    rtu_over_tcp: Optional[RtuOverTcpConfig] = None


def load_server_config(path: str) -> ServerConfig:
    return ServerConfig(**yaml.load(open(path, "rt"), Loader=yaml.SafeLoader))
