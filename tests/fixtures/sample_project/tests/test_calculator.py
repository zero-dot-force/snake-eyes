"""Fixture test file for snake-eyes test-mapping pipeline tests.

Not executed by the host pytest run (excluded via collect_ignore_glob).
Analyzed as static input by test_test_mapping_method.py.
"""

from __future__ import annotations

import unittest

from sample.calculator import Counter, add, divide


def test_add(a: int = 1, b: int = 2) -> None:
    """Name-strategy pair: test_add <-> add (confidence 90)."""
    result = add(a, b)
    assert result == a + b


def test_Add(a: int = 2, b: int = 3) -> None:
    """Case-only name match: test_Add <-> add (confidence 70)."""
    result = add(a, b)
    assert result == a + b


def test_it_divides(a: int = 10, b: int = 2) -> None:
    """Direct-call strategy: calls divide() but name doesn't match (confidence 80)."""
    result = divide(a, b)
    assert result == 5.0


def test_divide_error() -> None:
    """Error-check assertion using pytest.raises."""
    import pytest

    with pytest.raises(ZeroDivisionError):
        divide(1, 0)


def test_multi_assertion() -> None:
    """Multi-assertion test spanning lines 2 and 10 of the function body.

    Line 2 (within body): first assert
    Line 10 (within body): second assert — triggers numeric sort check.
    """
    # assertion on an early line of this function body
    assert add(1, 2) == 3
    # pad to push the next assertion further down
    _ = add(0, 0)
    _ = add(0, 0)
    _ = add(0, 0)
    _ = add(0, 0)
    _ = add(0, 0)
    _ = add(0, 0)
    _ = add(0, 0)
    # assertion on a later line (line 10+ of the body)
    assert add(3, 4) == 7


class TestCounter(unittest.TestCase):
    """unittest.TestCase subclass — test_inc pairs to Counter.inc."""

    def test_inc(self) -> None:
        c = Counter()
        c.inc()
        self.assertEqual(c.value, 1)
