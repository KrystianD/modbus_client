import re
from typing import Annotated, Optional, Any

from pydantic import StringConstraints, model_validator
from pydantic.dataclasses import dataclass


@dataclass
class FlagDefinition:
    name: Annotated[str, StringConstraints(pattern=r'^[a-zA-Z][a-zA-Z0-9_]*$')]
    bit: int
    display: Optional[str] = None

    def get_display(self) -> str:
        if self.display is not None:
            return f"{self.display} ({self.name})"
        else:
            return self.name

    @model_validator(mode='before')
    @classmethod
    def _parse(cls, v: Any) -> Any:
        if isinstance(v, str):
            d = parse_flag_def(v)
            return {
                "name": d.name,
                "bit": d.bit,
            }
        else:
            return v


def parse_flag_def(flag_def: str) -> FlagDefinition:
    m = re.match(rf"^([a-zA-Z0-9_ ]+)/\s*([0-9]+)?$", flag_def)
    if m is not None:
        return FlagDefinition(
                name=m.group(1).strip(),
                bit=int(m.group(2).strip()))
    else:
        raise ValueError(f"/{flag_def}/ is not a valid flag definition")
