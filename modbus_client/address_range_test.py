import unittest
from typing import List, Tuple

from modbus_client.address_range import AddressRange, merge_address_ranges


# tests use (start, end) tuples instead of (start, count)

class AddressRangesTest(unittest.TestCase):
    def _test_range(self, expected_output: List[Tuple[int, int]], ranges: List[Tuple[int, int]], allow_holes: bool,
                    max_read_size: int = 10) -> None:
        address_ranges = [AddressRange(x[0], x[1] - x[0] + 1) for x in ranges]

        res = merge_address_ranges(address_ranges, allow_holes=allow_holes, max_read_size=max_read_size)
        res_tuples = [(x.address, x.address + x.count - 1) for x in res]

        self.assertEqual(expected_output, res_tuples)

    def test_no_holes_single(self) -> None:
        self._test_range([(0, 1)], [(0, 1)], allow_holes=False)

    def test_no_holes_adjacent(self) -> None:
        self._test_range([(0, 2)], [(0, 1), (1, 2)], allow_holes=False)
        self._test_range([(0, 3)], [(0, 1), (1, 3)], allow_holes=False)

        self._test_range([(0, 3)], [(0, 1), (2, 3)], allow_holes=False)

    def test_no_holes_multiple_not_adjacent(self) -> None:
        self._test_range([(0, 1), (5, 6)], [(0, 1), (5, 6)], allow_holes=False)

    def test_holes_single(self) -> None:
        self._test_range([(0, 1)], [(0, 1)], allow_holes=True)

    def test_holes_adjacent(self) -> None:
        self._test_range([(0, 2)], [(0, 1), (1, 2)], allow_holes=True)
        self._test_range([(0, 3)], [(0, 1), (1, 3)], allow_holes=True)

    def test_holes_not_adjacent(self) -> None:
        self._test_range([(0, 3)], [(0, 1), (2, 3)], allow_holes=True)
        self._test_range([(0, 6)], [(0, 1), (5, 6)], allow_holes=True)

    def test_mixed_order(self) -> None:
        self._test_range([(5, 6), (10, 11)], [(10, 11), (5, 6)], allow_holes=False)

    def test_overlapping(self) -> None:
        self._test_range([(0, 10)], [(0, 1), (0, 5), (5, 9), (10, 10)], allow_holes=True)
        self._test_range([(7, 15)], [(10, 15), (7, 12)], allow_holes=True)

    def test_max_read(self) -> None:
        self._test_range([(0, 1), (15, 16)], [(0, 1), (15, 16)], allow_holes=True, max_read_size=10)
        self._test_range([(0, 9), (15, 16)], [(0, 1), (8, 9), (15, 16)], allow_holes=True, max_read_size=10)

        self._test_range([(0, 16)], [(0, 1), (15, 16)], allow_holes=True, max_read_size=100)
