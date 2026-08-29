"""Ambiguity fixture: computed getattr call, unknown external call, pure local call."""


def pure_local() -> int:
    return 42


def uses_ambiguous(obj: object, name: str) -> None:
    # (a) computed attribute call -> CallbackInvocation ambiguous
    getattr(obj, name)()

    # (b) pure local call — NOT an effect
    pure_local()


def unknown_external_call() -> None:
    # (c) unknown external name not on pure-builtin allowlist
    some_unknown_function()  # type: ignore[name-defined]  # noqa: F821
