import re
import argparse
from typing import Tuple, Any

ModeTupleType = Tuple[int, str, int]


def mode_parser(arg_value: Any) -> ModeTupleType:
    m = re.match(r"(\d+)([neo])([12])", arg_value, re.IGNORECASE)
    if m:
        return int(m.group(1)), m.group(2).upper(), int(m.group(3))
    else:
        raise argparse.ArgumentTypeError


def interval_parser(arg_value: Any) -> float:
    try:
        return float(arg_value)
    except ValueError:
        m = re.match(r"(\d+)(ms|s)", arg_value, re.IGNORECASE)
        if m:
            return float(m.group(1)) * (1 if m.group(2) == "s" else 0.001)
        else:
            raise argparse.ArgumentTypeError


__all__ = [
    "ModeTupleType",
    "mode_parser",
    "interval_parser",
]
