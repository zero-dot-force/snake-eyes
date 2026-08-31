"""Constitution V regression: caller inference never executes analyzed code."""

from __future__ import annotations

from pathlib import Path

from snake_eyes.analysis.inference import build_caller_index, count_callers


def test_import_time_side_effect_never_fires(tmp_path: Path) -> None:
    sentinel = tmp_path / "sentinel.txt"
    code = (
        "import pathlib\n"
        f"pathlib.Path({str(sentinel)!r}).write_text('boom')\n\n"
        "def target():\n"
        "    return 1\n\n"
        "def caller():\n"
        "    return target()\n"
    )
    (tmp_path / "m.py").write_text(code)

    build_caller_index(str(tmp_path), None)
    count_callers(str(tmp_path), "m", "target")

    assert not sentinel.exists(), (
        "analyzed module was executed (import-time side effect fired)"
    )
