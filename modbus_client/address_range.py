from dataclasses import dataclass
from typing import List, Optional, Sequence


@dataclass
class AddressRange:
    address: int
    count: int


def merge_address_ranges(registers: Sequence[AddressRange], allow_holes: bool, max_read_size: int) -> List[AddressRange]:
    buckets: List[AddressRange] = []
    cur_rng: Optional[AddressRange] = None

    for register in sorted(registers, key=lambda x: (x.address, -x.count)):
        rng = AddressRange(register.address, register.count)

        if cur_rng is not None and cur_rng.address + cur_rng.count > rng.address:
            continue

        if cur_rng is None:
            cur_rng = rng
        else:
            diff = (rng.address + rng.count - 1) - (cur_rng.address + cur_rng.count - 1)
            if diff > 1:
                if allow_holes:
                    if cur_rng.count + diff <= max_read_size:
                        cur_rng.count += diff
                    else:
                        buckets.append(cur_rng)
                        cur_rng = rng
                else:
                    buckets.append(cur_rng)
                    cur_rng = rng
            else:
                cur_rng.count += diff

    if cur_rng is not None:
        buckets.append(cur_rng)

    return buckets


__all__ = [
    "AddressRange",
    "merge_address_ranges",
]
