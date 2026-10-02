"""Conformance tests for the effect-disposition table (docs/effect-disposition.md).

The table is documentation, not a runtime input; these tests verify it is
complete (all ten reachable keys), internally consistent (closed-set
dispositions, no conflicting duplicate keys, non-``unclaimed`` cells name an
effect type), carries the banner, and agrees with what ``visibility.extract``
actually emits for each key.
"""

from __future__ import annotations

from pathlib import Path

from snake_eyes.analysis.effects import SideEffectType
from snake_eyes.signals import visibility
from snake_eyes.signals._types import EnclosingClassVisibility, FunctionSurface

_DOC = Path(__file__).resolve().parents[1] / "docs" / "effect-disposition.md"

_HEADERS = (
    "surface",
    "enclosing-class visibility",
    "dunder",
    "name-prefix",
    "effect-type exception",
    "disposition",
    "rationale",
)

_KEYS = [
    ("module", "none", "false", "public", "none"),
    ("module", "none", "false", "private", "none"),
    ("module", "none", "true", "n/a", "none"),
    ("method", "public", "false", "public", "none"),
    ("method", "public", "false", "private", "none"),
    ("method", "public", "true", "n/a", "none"),
    ("method", "private", "false", "n/a", "none"),
    ("method", "private", "true", "n/a", "none"),
    ("nested", "none", "n/a", "n/a", "none"),
    ("nested", "none", "n/a", "n/a", "ClosureCaptureMutation"),
]

_DISPOSITIONS = {"incidental", "contractual", "unclaimed"}


def _parse() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in _DOC.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != len(_HEADERS):
            continue
        if cells[0] == "surface":
            continue
        if all(set(c) <= {"-"} for c in cells):
            continue
        rows.append(dict(zip(_HEADERS, cells)))
    return rows


def _key(r: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        r["surface"],
        r["enclosing-class visibility"],
        r["dunder"],
        r["name-prefix"],
        r["effect-type exception"],
    )


def test_banner_present() -> None:
    text = " ".join(_DOC.read_text().split())
    assert "not a guaranteed final Gaze bucket" in text


def test_all_ten_keys_present() -> None:
    assert {_key(r) for r in _parse()} == set(_KEYS)


def test_no_conflicting_duplicate_keys() -> None:
    seen: dict[tuple[str, ...], str] = {}
    for r in _parse():
        key = _key(r)
        if key in seen:
            assert seen[key] == r["disposition"], f"conflicting disposition for {key}"
        seen[key] = r["disposition"]


def test_dispositions_in_closed_set() -> None:
    for r in _parse():
        assert r["disposition"] in _DISPOSITIONS, r


def test_non_unclaimed_cells_name_an_effect_type() -> None:
    values = {t.value for t in SideEffectType}
    for r in _parse():
        if r["disposition"] == "unclaimed":
            continue
        assert r["rationale"].strip(), r
        assert any(v in r["rationale"] for v in values), r


def test_disposition_agrees_with_extractor() -> None:
    weight_by_disposition = {
        "contractual": visibility.PUBLIC_WEIGHT,
        "incidental": visibility.PRIVATE_WEIGHT,
        "unclaimed": None,
    }
    for r in _parse():
        surface = FunctionSurface(r["surface"])
        enclosing = EnclosingClassVisibility(r["enclosing-class visibility"])
        effect = (
            "ClosureCaptureMutation"
            if r["effect-type exception"] == "ClosureCaptureMutation"
            else "ReceiverMutation"
        )
        if r["dunder"] == "true":
            func_name = "__init__"
        elif r["name-prefix"] == "private":
            func_name = "_run"
        else:
            func_name = "run"
        result = visibility.extract(func_name, False, surface, enclosing, effect)
        weight = None if result is None else result.weight
        assert weight == weight_by_disposition[r["disposition"]], (
            r,
            func_name,
            effect,
            weight,
            r["disposition"],
        )
