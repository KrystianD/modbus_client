from modbus_client.server.mytypes import Connector
from modbus_client.server.server_config import ServerConfig


class RuntimeData:
    def __init__(self, server_config: ServerConfig, connector: Connector) -> None:
        self.server_config = server_config
        self.connector = connector
