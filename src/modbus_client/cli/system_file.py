from dataclasses import field
from typing import List

import yaml
from pydantic.dataclasses import dataclass


@dataclass
class Device:
    name: str
    host: str
    port: int
    unit: int
    device: str


@dataclass
class SystemConfig:
    devices: List[Device] = field(default_factory=list)


def load_system_config(path: str) -> SystemConfig:
    return SystemConfig(**yaml.load(open(path, "rt"), Loader=yaml.SafeLoader))
