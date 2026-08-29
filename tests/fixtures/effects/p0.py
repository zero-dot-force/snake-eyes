"""P0 effects fixture: ReturnValue, ErrorReturn, SentinelError, ReceiverMutation, PointerArgMutation."""


# SentinelError: module-level Exception subclass
class MyError(Exception):
    pass


def returns_value() -> int:
    return 42


def raises_error() -> None:
    raise MyError("boom")


class Widget:
    def mutate_self(self) -> None:
        self.x = 1  # ReceiverMutation

    def mutate_param(self, items: list[int]) -> None:
        items.append(99)  # PointerArgMutation
