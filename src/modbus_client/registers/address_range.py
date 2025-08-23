from dataclasses import dataclass
from typing import List, Optional, Sequence, Protocol


class AddressRangeTrait(Protocol):
    def get_address(self) -> int: ...

    def get_count(self) -> int: ...


@dataclass
class AddressRange(AddressRangeTrait):
    address: int
    count: int

    def get_address(self) -> int:
        return self.address

    def get_count(self) -> int:
        return self.count

    @property
    def first_address(self) -> int:
        return self.address

    @property
    def last_address(self) -> int:
        return self.address + self.count - 1


def merge_address_ranges(registers: Sequence[AddressRangeTrait], allow_holes: bool, max_read_size: int) \
        -> List[AddressRange]:
    buckets: List[AddressRange] = []
    cur_rng: Optional[AddressRange] = None

    for register in sorted(registers, key=lambda x: (x.get_address(), -x.get_count())):
        rng = AddressRange(register.get_address(), register.get_count())

        if cur_rng is not None and rng.first_address >= cur_rng.first_address and rng.last_address <= cur_rng.last_address:
            continue

        if cur_rng is None:
            cur_rng = rng
        else:
            diff = rng.first_address - cur_rng.last_address
            to_add = rng.last_address - cur_rng.last_address
            if (diff <= 1 or allow_holes) and cur_rng.count + to_add <= max_read_size:
                cur_rng.count += to_add
            else:
                buckets.append(cur_rng)
                cur_rng = rng

    if cur_rng is not None:
        buckets.append(cur_rng)

    return buckets


__all__ = [
    "AddressRange",
    "merge_address_ranges",
]
