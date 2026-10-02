# Implementation Report — reduce-ambiguous-effect-bucket

Issue: #33 (reduce the ambiguous-effect bucket via surface-aware visibility).

## Re-measurement

Measured with the dev `gaze` binary (Go toolchain 1.26.5;
`gaze version dev (commit none, built unknown)`; no binary SHA-256 recorded —
the dev build has no pinned source commit).

Command: `gaze quality --analyzer snake-eyes --language python --format json .`

| Metric | Before (HEAD `bb7b621`) | After (this branch) |
|---|---|---|
| contractual | 421 | 447 |
| incidental | 520 | 526 |
| ambiguous | 1324 | 1326 |
| **total** | 2265 | 2299 |
| ambiguous % | 58.45% | 57.68% |

The proposal's "Why" cites `58.9%` (1286 of 2185) as the issue #33 motivation
figure, measured at an unpinned main-HEAD gaze; the "Before" row above
(`58.45%`, 1324 of 2265) is the authoritative pre-change baseline re-measured
with the pinned dev gaze binary against HEAD `bb7b621`.

Protocol version: `1.1.0` (snake-eyes `protocol.PROTOCOL_VERSION`).

### Interpretation

The ambiguous *percentage* dropped ~0.8 points (58.45% → 57.68%) and
contractual rose +26, reflecting the surface-aware visibility signal moving
some caller-visible `__init__`/public-class effects out of ambiguity. The
absolute ambiguous count is essentially flat (+2) because the total effect
count grew (2265 → 2299) and, by design, `ClosureCaptureMutation` on a
nested surface now emits `None` (no visibility signal) — which Gaze buckets
`ambiguous` rather than misreading the closure as public. This matches the
design's stated non-goal: the change improves signal accuracy and re-measures;
it does not force a specific ambiguous-count reduction.

## Constitution Alignment Verification

- **Protocol Fidelity — PASS.** No new `source` value, no wire-shape change,
  deterministic output preserved.
- **Detection Accuracy — PASS.** More precise visibility signals (dunder
  methods, nested helpers, private-class methods); escaping closures are
  never silently asserted (Principle II ambiguity-over-omission).
- **Python-Native Analysis — PASS.** Surface derived with stdlib `ast` from
  the existing `parents` walk; no reimplementation of Python semantics, no
  new dependency.
- **Testability — PASS.** Unit (per-module ≥95% via `uv run coverage report`
  post-step), conformance (`tests/test_effect_disposition.py`), integration
  (`test_classify_signals_method.py`), and regression (negative-label)
  layers all specified and green; 85% project floor unchanged.
- **Analysis Safety — PASS.** Static analysis only; analyzed code never
  executed.
