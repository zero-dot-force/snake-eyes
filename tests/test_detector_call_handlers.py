"""Per-handler tests for the decomposed call-dispatch handlers in detector.py.

Each handler in ``_EffectVisitor._CALL_HANDLERS`` and
``_EffectVisitor._METHOD_CALL_HANDLERS`` is exercised through the public
``analyze_source`` entry point, asserting the full emitted effect list
(type, description, target, detail) rather than mere membership.
"""

from __future__ import annotations

from typing import Any

import pytest

from snake_eyes.analysis.detector import analyze_source
from snake_eyes.analysis.models import FunctionRecord, function_record_to_dict


def _to_dicts(records: list[FunctionRecord]) -> list[dict[str, Any]]:
    return [function_record_to_dict(r) for r in records]


def _effects(records: list[FunctionRecord], name: str) -> list[dict[str, Any]]:
    return [
        e for r in _to_dicts(records) if r["name"] == name for e in r["side_effects"]
    ]


def _types(records: list[FunctionRecord], name: str) -> set[str]:
    return {e["type"] for e in _effects(records, name)}


@pytest.mark.parametrize(
    ("source", "name", "expected"),
    [
        # -- _handle_exit_calls
        (
            "import sys\ndef f():\n    sys.exit(0)\n",
            "f",
            {"ProcessExit", "ErrorSignal"},
        ),
        ("import os\ndef f():\n    os._exit(1)\n", "f", {"ProcessExit", "ErrorSignal"}),
        # -- _handle_print_call
        ("def f():\n    print('hi')\n", "f", {"StdoutWrite"}),
        (
            "import sys\ndef f():\n    print('x', file=sys.stderr)\n",
            "f",
            {"StderrWrite"},
        ),
        # -- _handle_dynamic_exec
        ("def f():\n    eval('1+1')\n", "f", {"CallbackInvocation"}),
        ("def f():\n    exec('x = 1')\n", "f", {"CallbackInvocation"}),
        # -- _handle_reflection_calls
        ("def f(obj):\n    setattr(obj, 'x', 1)\n", "f", {"ReflectionMutation"}),
        ("import os\ndef f():\n    setattr(os, 'x', 1)\n", "f", {"MonkeyPatch"}),
        ("def f(obj):\n    delattr(obj, 'x')\n", "f", {"ReflectionMutation"}),
        # -- _handle_metaprogramming
        ("def f():\n    type('T', (), {})\n", "f", {"MetaprogrammingMutation"}),
        (
            "import types\ndef f():\n    types.new_class('T')\n",
            "f",
            {"MetaprogrammingMutation"},
        ),
        # -- _handle_import_effects
        ("def f():\n    __import__('os')\n", "f", {"ImportSideEffect"}),
        (
            "import importlib\ndef f():\n    importlib.import_module('os')\n",
            "f",
            {"ImportSideEffect"},
        ),
        # -- _handle_finalizers
        (
            "import atexit\ndef f():\n    atexit.register(f)\n",
            "f",
            {"FinalizerRegistration"},
        ),
        (
            "import weakref\ndef f(obj):\n    weakref.finalize(obj, f)\n",
            "f",
            {"FinalizerRegistration"},
        ),
        # -- _handle_time_dependency
        ("import time\ndef f():\n    time.time()\n", "f", {"TimeDependency"}),
        ("import datetime\ndef f():\n    datetime.now()\n", "f", {"TimeDependency"}),
        (
            "from datetime import date\ndef f():\n    date.today()\n",
            "f",
            {"TimeDependency"},
        ),
        # -- _handle_logging
        ("import logging\ndef f():\n    logging.info('x')\n", "f", {"LogWrite"}),
        ("def f(logger):\n    logger.debug('x')\n", "f", {"LogWrite"}),
        # -- _handle_concurrency
        ("import asyncio\ndef f():\n    asyncio.gather(a, b)\n", "f", {"WaitGroupOp"}),
        (
            "import asyncio\ndef f():\n    asyncio.create_task(c)\n",
            "f",
            {"GoroutineSpawn"},
        ),
        ("def f(loop):\n    loop.run_in_executor(None, g)\n", "f", {"GoroutineSpawn"}),
        (
            "import multiprocessing\ndef f():\n    multiprocessing.Pool()\n",
            "f",
            {"SyncPoolOp"},
        ),
        # -- _handle_open_write
        ("def f():\n    open('f', 'w')\n", "f", {"FileSystemWrite"}),
        # -- _handle_computed_getattr_call
        ("def f(obj):\n    getattr(obj, 'run')()\n", "f", {"CallbackInvocation"}),
        # -- _handle_name_call_fallback
        ("def f():\n    unknown_fn()\n", "f", {"CallbackInvocation"}),
        # -- _handle_std_streams
        ("import sys\ndef f():\n    sys.stdout.write('x')\n", "f", {"StdoutWrite"}),
        ("import sys\ndef f():\n    sys.stderr.write('x')\n", "f", {"StderrWrite"}),
        # -- _handle_env_mutations
        (
            "import os\ndef f():\n    os.environ.update({'X': '1'})\n",
            "f",
            {"EnvVarMutation"},
        ),
        ("import os\ndef f():\n    os.putenv('X', '1')\n", "f", {"EnvVarMutation"}),
        ("def f(environ):\n    environ.update({'X': '1'})\n", "f", {"EnvVarMutation"}),
        # -- _handle_os_filesystem
        ("import os\ndef f():\n    os.remove('f')\n", "f", {"FileSystemDelete"}),
        ("import os\ndef f():\n    os.chmod('f', 0o644)\n", "f", {"FileSystemMeta"}),
        ("import os\ndef f():\n    os.write(fd, b'x')\n", "f", {"FileSystemWrite"}),
        # -- _handle_shutil_and_path
        (
            "import shutil\ndef f():\n    shutil.copy('a', 'b')\n",
            "f",
            {"FileSystemWrite"},
        ),
        (
            "import shutil\ndef f():\n    shutil.rmtree('d')\n",
            "f",
            {"FileSystemDelete"},
        ),
        (
            "from pathlib import Path\ndef f():\n    Path('f').write_text('x')\n",
            "f",
            {"FileSystemWrite", "CallbackInvocation"},
        ),
        (
            "from pathlib import Path\ndef f():\n    Path('f').unlink()\n",
            "f",
            {"FileSystemDelete", "CallbackInvocation"},
        ),
        (
            "from pathlib import Path\ndef f():\n    Path('f').mkdir()\n",
            "f",
            {"FileSystemMeta", "CallbackInvocation"},
        ),
        # -- _handle_thread_spawn
        ("def f(t):\n    t.start()\n", "f", {"GoroutineSpawn"}),
        # -- _handle_mutex_op
        ("def f(lock):\n    lock.acquire()\n", "f", {"MutexOp"}),
        # -- _handle_channel_send
        ("def f(q):\n    q.put(1)\n", "f", {"ChannelSend"}),
        # -- _handle_task_cancel
        ("def f(task):\n    task.cancel()\n", "f", {"ContextCancellation"}),
        # -- _handle_barrier_wait
        ("def f(barrier):\n    barrier.wait()\n", "f", {"WaitGroupOp"}),
        # -- _handle_db_methods
        ("def f(cursor):\n    cursor.execute('SELECT 1')\n", "f", {"DatabaseWrite"}),
        ("def f(conn):\n    conn.commit()\n", "f", {"DatabaseTransaction"}),
        # -- _handle_http_response
        ("def f(response):\n    response.write('x')\n", "f", {"HTTPResponseWrite"}),
        # -- _handle_writer_methods
        ("def f(fh):\n    fh.write('x')\n", "f", {"WriterOutput"}),
        ("def f():\n    local = []\n    local.append(1)\n", "f", {"ContainerMutation"}),
        # -- _handle_map_methods
        ("def f():\n    d = {}\n    d.setdefault('k', 1)\n", "f", {"MapMutation"}),
        ("def f(d):\n    d.setdefault('k', 1)\n", "f", {"PointerArgMutation"}),
    ],
)
def test_handler_emits_expected_effect(
    source: str, name: str, expected: set[str]
) -> None:
    records = analyze_source(source, "h.py", "h")
    assert _types(records, name) == expected


def test_exit_calls_emit_full_shape() -> None:
    records = analyze_source("import sys\ndef f():\n    sys.exit(0)\n", "h.py", "h")
    assert _effects(records, "f") == [
        {
            "type": "ErrorSignal",
            "description": "Exception signal via sys.exit",
            "location": "h.py:3:4",
        },
        {
            "type": "ProcessExit",
            "description": "Process exit via sys.exit",
            "location": "h.py:3:4",
        },
    ]


def test_print_emits_stdout_write() -> None:
    records = analyze_source("def f():\n    print('hi')\n", "h.py", "h")
    assert _effects(records, "f") == [
        {
            "type": "StdoutWrite",
            "description": "Writes to stdout via print",
            "location": "h.py:2:4",
        },
    ]


def test_channel_send_target() -> None:
    records = analyze_source("def f(q):\n    q.put(1)\n", "h.py", "h")
    assert _effects(records, "f") == [
        {
            "type": "ChannelSend",
            "description": "Channel send via .put()",
            "location": "h.py:2:4",
            "target": "q",
        },
    ]


def test_ambiguous_call_detail() -> None:
    records = analyze_source("def f():\n    unknown_fn()\n", "h.py", "h")
    assert _effects(records, "f") == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'unknown_fn'",
            "location": "h.py:2:4",
            "detail": {"confidence": "ambiguous"},
        },
    ]


def test_write_mode_open_co_emits_filesystem_write() -> None:
    source = "def f(p):\n    fh = open(p, 'w')\n    fh.write('data')\n"
    records = analyze_source(source, "h.py", "h")
    types = _types(records, "f")
    assert "StreamOutput" in types
    assert "FileSystemWrite" in types
    assert "WriterOutput" not in types


def test_read_mode_open_no_filesystem_write() -> None:
    source = "def f(p):\n    fh = open(p, 'r')\n    fh.write('x')\n"
    records = analyze_source(source, "h.py", "h")
    types = _types(records, "f")
    assert "StreamOutput" in types
    assert "FileSystemWrite" not in types


def test_container_mutation_precedence() -> None:
    receiver = analyze_source(
        "class C:\n    def m(self):\n        self.items.append(1)\n", "h.py", "h"
    )
    assert _types(receiver, "m") == {"ReceiverMutation"}

    param = analyze_source("def f(items):\n    items.append(1)\n", "h.py", "h")
    assert _types(param, "f") == {"PointerArgMutation"}

    local = analyze_source("def f():\n    x = []\n    x.append(1)\n", "h.py", "h")
    assert _types(local, "f") == {"ContainerMutation"}
