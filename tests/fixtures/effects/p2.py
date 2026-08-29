"""P2 effects fixture: FileSystemWrite (open 'w'), ReflectionMutation (setattr), ResourceManagement,
DescriptorEffect, ImportSideEffect, MonkeyPatch, MetaprogrammingMutation."""

import importlib

import other_module  # noqa: F401 (used below for MonkeyPatch)


def open_write(path: str) -> None:
    open(path, "w")  # FileSystemWrite


def use_setattr(obj: object) -> None:
    setattr(obj, "attr", 1)  # ReflectionMutation


class ManagedResource:
    def __enter__(self) -> "ManagedResource":  # ResourceManagement
        return self

    def __exit__(self, *args: object) -> None:  # ResourceManagement
        pass


class Descriptor:
    def __get__(self, obj: object, objtype: object = None) -> int:  # DescriptorEffect
        return 0


def dynamic_import(name: str) -> None:
    importlib.import_module(name)  # ImportSideEffect


def monkeypatch_module() -> None:
    other_module.foo = 1  # MonkeyPatch


def make_class() -> type:
    return type("T", (), {})  # MetaprogrammingMutation
