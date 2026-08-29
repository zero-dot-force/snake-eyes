"""Tiny module for coverage fixture tests."""


def covered_func(x: int) -> int:
    return x + 1


def uncovered_func(x: int) -> int:
    return x * 2
