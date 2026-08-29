"""Extra detector tests to raise coverage above 90%.

validates: gaze analyzer protocol v1.1.0
"""

from __future__ import annotations

from typing import Any

from snake_eyes.analysis.detector import analyze_source
from snake_eyes.analysis.models import FunctionRecord, function_record_to_dict


def _to_dicts(records: list[FunctionRecord]) -> list[dict[str, Any]]:
    return [function_record_to_dict(r) for r in records]


def _types(records: list[FunctionRecord]) -> set[str]:
    return {e["type"] for r in _to_dicts(records) for e in r["side_effects"]}


def _all_effects(records: list[FunctionRecord]) -> list[dict[str, Any]]:
    return [e for r in _to_dicts(records) for e in r["side_effects"]]


# ---------------------------------------------------------------------------
# Systematically hit uncovered detector paths
# ---------------------------------------------------------------------------


def test_detect_weakref_finalize() -> None:
    """FinalizerRegistration via weakref.finalize()."""
    source = "import weakref\ndef f(obj, cb):\n    weakref.finalize(obj, cb)\n"
    records = analyze_source(source, "f.py", "f")
    assert "FinalizerRegistration" in _types(records)


def test_detect_shutil_rmtree() -> None:
    """FileSystemDelete via shutil.rmtree()."""
    source = "import shutil\ndef f(p):\n    shutil.rmtree(p)\n"
    records = analyze_source(source, "f.py", "f")
    assert "FileSystemDelete" in _types(records)


def test_detect_os_unlink() -> None:
    """FileSystemDelete via os.unlink()."""
    source = "import os\ndef f(p):\n    os.unlink(p)\n"
    records = analyze_source(source, "f.py", "f")
    assert "FileSystemDelete" in _types(records)


def test_detect_os_rmdir() -> None:
    """FileSystemDelete via os.rmdir()."""
    source = "import os\ndef f(p):\n    os.rmdir(p)\n"
    records = analyze_source(source, "f.py", "f")
    assert "FileSystemDelete" in _types(records)


def test_detect_os_rename() -> None:
    """FileSystemMeta via os.rename()."""
    source = "import os\ndef f(src, dst):\n    os.rename(src, dst)\n"
    records = analyze_source(source, "f.py", "f")
    assert "FileSystemMeta" in _types(records)


def test_detect_os_mkdir() -> None:
    """FileSystemMeta via os.mkdir()."""
    source = "import os\ndef f(p):\n    os.mkdir(p)\n"
    records = analyze_source(source, "f.py", "f")
    assert "FileSystemMeta" in _types(records)


def test_detect_path_unlink() -> None:
    """FileSystemDelete via Path.unlink()."""
    source = "from pathlib import Path\ndef f(p):\n    Path(p).unlink()\n"
    records = analyze_source(source, "f.py", "f")
    assert "FileSystemDelete" in _types(records)


def test_detect_path_mkdir() -> None:
    """FileSystemMeta via Path.mkdir()."""
    source = "from pathlib import Path\ndef f(p):\n    Path(p).mkdir()\n"
    records = analyze_source(source, "f.py", "f")
    assert "FileSystemMeta" in _types(records)


def test_detect_path_rename() -> None:
    """FileSystemMeta via Path.rename()."""
    source = "from pathlib import Path\ndef f(p, dst):\n    Path(p).rename(dst)\n"
    records = analyze_source(source, "f.py", "f")
    assert "FileSystemMeta" in _types(records)


def test_detect_path_chmod() -> None:
    """FileSystemMeta via Path.chmod()."""
    source = "from pathlib import Path\ndef f(p):\n    Path(p).chmod(0o644)\n"
    records = analyze_source(source, "f.py", "f")
    assert "FileSystemMeta" in _types(records)


def test_detect_path_write_bytes() -> None:
    """FileSystemWrite via Path.write_bytes()."""
    source = "from pathlib import Path\ndef f(p):\n    Path(p).write_bytes(b'x')\n"
    records = analyze_source(source, "f.py", "f")
    assert "FileSystemWrite" in _types(records)


def test_detect_http_response_write() -> None:
    """HTTPResponseWrite detected via response.write()."""
    source = "def f(response):\n    response.write('data')\n"
    records = analyze_source(source, "f.py", "f")
    assert "HTTPResponseWrite" in _types(records)


def test_detect_exec() -> None:
    """exec() emits CallbackInvocation ambiguous."""
    source = "def f(code):\n    exec(code)\n"
    records = analyze_source(source, "f.py", "f")
    effects = _all_effects(records)
    cb = [
        e
        for e in effects
        if e["type"] == "CallbackInvocation"
        and e.get("detail", {}).get("confidence") == "ambiguous"
    ]
    assert cb


def test_detect_setattr_on_module() -> None:
    """setattr on module alias → MonkeyPatch."""
    source = "import os\ndef f():\n    setattr(os, 'attr', 1)\n"
    records = analyze_source(source, "f.py", "f")
    assert "MonkeyPatch" in _types(records)


def test_detect_monkeypatch_via_assignment() -> None:
    """Attribute assignment on import alias → MonkeyPatch."""
    source = "import os\ndef f():\n    os.sep = '/'\n"
    records = analyze_source(source, "f.py", "f")
    assert "MonkeyPatch" in _types(records)


def test_detect_global_mutation_augassign() -> None:
    """GlobalMutation via augmented assignment to a global."""
    source = "_count = 0\ndef f():\n    global _count\n    _count += 1\n"
    records = analyze_source(source, "f.py", "f")
    assert "GlobalMutation" in _types(records)


def test_detect_receiver_subscript() -> None:
    """ReceiverMutation via self[key] subscript assignment."""
    source = "class C:\n    def m(self, k, v):\n        self[k] = v\n"
    records = analyze_source(source, "f.py", "f")
    assert "ReceiverMutation" in _types(records)


def test_detect_param_subscript() -> None:
    """PointerArgMutation via param[key] subscript assignment."""
    source = "def f(d):\n    d['k'] = 1\n"
    records = analyze_source(source, "f.py", "f")
    assert "PointerArgMutation" in _types(records)


def test_detect_global_subscript() -> None:
    """GlobalMutation via global_dict[key] subscript assignment."""
    source = "_data = {}\ndef f():\n    global _data\n    _data['k'] = 1\n"
    records = analyze_source(source, "f.py", "f")
    assert "GlobalMutation" in _types(records)


def test_detect_ann_assign_self() -> None:
    """ReceiverMutation via annotated assignment to self.attr."""
    source = "class C:\n    def m(self):\n        self.x: int = 1\n"
    records = analyze_source(source, "f.py", "f")
    assert "ReceiverMutation" in _types(records)


def test_detect_augassign_self() -> None:
    """ReceiverMutation via augmented assignment to self.attr."""
    source = "class C:\n    def m(self):\n        self.x += 1\n"
    records = analyze_source(source, "f.py", "f")
    assert "ReceiverMutation" in _types(records)


def test_detect_except_exception_swallow() -> None:
    """RecoverBehavior via except Exception: with no re-raise."""
    source = "def f():\n    try:\n        pass\n    except Exception:\n        pass\n"
    records = analyze_source(source, "f.py", "f")
    assert "RecoverBehavior" in _types(records)


def test_detect_types_new_class() -> None:
    """MetaprogrammingMutation via types.new_class()."""
    source = "import types\ndef f():\n    types.new_class('MyClass', ())\n"
    records = analyze_source(source, "f.py", "f")
    assert "MetaprogrammingMutation" in _types(records)


def test_detect_dunder_import() -> None:
    """ImportSideEffect via __import__()."""
    source = "def f(name):\n    __import__(name)\n"
    records = analyze_source(source, "f.py", "f")
    assert "ImportSideEffect" in _types(records)


def test_detect_asyncio_create_task_func() -> None:
    """GoroutineSpawn via asyncio.create_task() in an async function."""
    source = "import asyncio\nasync def f():\n    asyncio.create_task(None)\n"
    records = analyze_source(source, "f.py", "f")
    assert "GoroutineSpawn" in _types(records)


def test_detect_logger_log_method() -> None:
    """LogWrite via logger.info() — logger-like variable."""
    source = (
        "import logging\n"
        "def f():\n"
        "    logger = logging.getLogger(__name__)\n"
        "    logger.info('msg')\n"
    )
    records = analyze_source(source, "f.py", "f")
    assert "LogWrite" in _types(records)


def test_detect_run_in_executor() -> None:
    """GoroutineSpawn via loop.run_in_executor()."""
    source = "def f(loop, func):\n    loop.run_in_executor(None, func)\n"
    records = analyze_source(source, "f.py", "f")
    assert "GoroutineSpawn" in _types(records)


def test_detect_multiprocessing_mp_alias() -> None:
    """SyncPoolOp via mp.Pool() (mp alias)."""
    source = "import multiprocessing as mp\ndef f():\n    mp.Pool(4)\n"
    records = analyze_source(source, "f.py", "f")
    assert "SyncPoolOp" in _types(records)


def test_detect_os_putenv() -> None:
    """EnvVarMutation via os.putenv()."""
    source = "import os\ndef f():\n    os.putenv('X', '1')\n"
    records = analyze_source(source, "f.py", "f")
    assert "EnvVarMutation" in _types(records)


def test_detect_date_today() -> None:
    """TimeDependency via date.today()."""
    source = "from datetime import date\ndef f():\n    date.today()\n"
    records = analyze_source(source, "f.py", "f")
    assert "TimeDependency" in _types(records)


def test_detect_time_sleep() -> None:
    """TimeDependency via time.sleep()."""
    source = "import time\ndef f():\n    time.sleep(1)\n"
    records = analyze_source(source, "f.py", "f")
    assert "TimeDependency" in _types(records)


def test_detect_yield_from_async() -> None:
    """AsyncGeneratorYield via yield from in async def."""
    source = "async def f():\n    yield from range(3)\n"
    records = analyze_source(source, "f.py", "f")
    assert "AsyncGeneratorYield" in _types(records)


def test_detect_async_contextmanager_decorator() -> None:
    """ResourceManagement via @asynccontextmanager."""
    source = (
        "from contextlib import asynccontextmanager\n"
        "@asynccontextmanager\n"
        "async def f():\n"
        "    yield\n"
    )
    records = analyze_source(source, "f.py", "f")
    assert "ResourceManagement" in _types(records)


def test_detect_asyncio_gather_creates_waitgroup() -> None:
    """WaitGroupOp via asyncio.gather() in sync function."""
    source = "import asyncio\ndef f():\n    asyncio.gather()\n"
    records = analyze_source(source, "f.py", "f")
    assert "WaitGroupOp" in _types(records)


def test_detect_shutil_copy2() -> None:
    """FileSystemWrite via shutil.copy2()."""
    source = "import shutil\ndef f(src, dst):\n    shutil.copy2(src, dst)\n"
    records = analyze_source(source, "f.py", "f")
    assert "FileSystemWrite" in _types(records)


def test_detect_map_mutation_popitem() -> None:
    """MapMutation via dict.popitem() on a local (only in MAP_MUTATING_METHODS)."""
    source = "def f():\n    d = {'k': 1}\n    d.popitem()\n"
    records = analyze_source(source, "f.py", "f")
    assert "MapMutation" in _types(records)


def test_detect_map_mutation_param_update() -> None:
    """PointerArgMutation via param dict.update()."""
    source = "def f(d):\n    d.update({'k': 1})\n"
    records = analyze_source(source, "f.py", "f")
    assert "PointerArgMutation" in _types(records)


def test_detect_no_effect_for_assert() -> None:
    """Assert statement produces no effect."""
    source = "def f(x):\n    assert x > 0\n"
    records = analyze_source(source, "f.py", "f")
    effects = _all_effects(records)
    assert all(e["type"] != "AssertEffect" for e in effects)


def test_detect_import_from_inside_function() -> None:
    """ImportSideEffect via 'from x import y' inside a function."""
    source = "def f():\n    from os.path import join\n"
    records = analyze_source(source, "f.py", "f")
    assert "ImportSideEffect" in _types(records)


def test_detect_sentinel_error_base_exception() -> None:
    """SentinelError for BaseException subclass at module level."""
    source = "class FatalError(BaseException):\n    pass\n\ndef f():\n    pass\n"
    records = analyze_source(source, "f.py", "f")
    assert "SentinelError" in _types(records)


def test_detect_nested_function_effects() -> None:
    """Nested functions are analyzed separately."""
    source = "def outer():\n    def inner():\n        return 1\n    return inner\n"
    records = analyze_source(source, "f.py", "f")
    names = [r.name for r in records]
    assert "outer" in names
    assert "inner" in names


def test_detect_class_with_descriptor_and_resource() -> None:
    """Class with both descriptor and resource methods."""
    source = (
        "class Both:\n"
        "    def __get__(self, obj, objtype=None):\n"
        "        return self\n"
        "    def __enter__(self):\n"
        "        return self\n"
        "    def __exit__(self, *args):\n"
        "        pass\n"
    )
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "DescriptorEffect" in types
    assert "ResourceManagement" in types


def test_detect_environ_update_direct() -> None:
    """EnvVarMutation via environ.update() (environ imported directly)."""
    source = "from os import environ\ndef f():\n    environ.update({'X': '1'})\n"
    records = analyze_source(source, "f.py", "f")
    assert "EnvVarMutation" in _types(records)


def test_detect_aenter_aexit_resource_mgmt() -> None:
    """ResourceManagement via __aenter__/__aexit__ in a class."""
    source = (
        "class AsyncCtx:\n"
        "    async def __aenter__(self):\n"
        "        return self\n"
        "    async def __aexit__(self, *args):\n"
        "        pass\n"
    )
    records = analyze_source(source, "f.py", "f")
    assert "ResourceManagement" in _types(records)
