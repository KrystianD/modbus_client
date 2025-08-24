import re
from dataclasses import dataclass
from typing import List


@dataclass
class BitArray:
    bits: List[int]

    @staticmethod
    def parse(value: str) -> 'BitArray':
        m = re.match("(\d+):(\d+)", value)
        if m is None:
            raise ValueError("invalid bit array definition")

        b1 = int(m.group(1))
        b2 = int(m.group(2))

        return BitArray(bits=list(range(min(b1, b2), max(b1, b2) + 1)))
