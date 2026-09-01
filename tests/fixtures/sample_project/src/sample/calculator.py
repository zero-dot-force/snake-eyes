"""Sample calculator module for snake-eyes test fixtures."""


def add(a: int, b: int) -> int:
    """Return the sum of a and b."""
    return a + b


def divide(a: int, b: int) -> float:
    """Return a divided by b; raises ZeroDivisionError when b is zero."""
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b


class Counter:
    """A simple counter that tracks a running total."""

    def __init__(self) -> None:
        self.value: int = 0

    def inc(self) -> None:
        """Increment the counter by one."""
        self.value += 1
