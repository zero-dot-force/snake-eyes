"""Complexity fixture for test_complexity.py.

Hand-derived McCabe integer:
  base 1 + if(1) + elif(1) + and(1) = 4
"""


def branchy(x: int, y: int) -> str:  # complexity = 4
    if x > 0 and y > 0:  # +1 for if, +1 for and
        return "both positive"
    elif x > 0:  # +1 for elif
        return "x positive"
    else:
        return "neither"


def nested_outer() -> None:
    def nested_inner() -> int:
        return 1

    nested_inner()


EXPECTED_BRANCHY_COMPLEXITY = 4
