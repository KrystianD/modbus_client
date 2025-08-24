from typing import Annotated, Optional

from pydantic import StringConstraints
from pydantic.dataclasses import dataclass


@dataclass
class EnumDefinition:
    name: Annotated[str, StringConstraints(pattern=r'^[a-zA-Z][a-zA-Z0-9_]*$')]
    value: int
    display: Optional[str] = None

    def get_display(self) -> str:
        if self.display is not None:
            return f"{self.display} ({self.name})"
        else:
            return self.name
