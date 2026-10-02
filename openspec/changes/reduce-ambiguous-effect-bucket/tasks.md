<!--
  [P] marks tasks eligible for parallel execution.
  Add [P] when a task: (a) touches different files from
  other [P] tasks in the group, (b) has no dependency
  on prior tasks in the group, (c) can safely execute
  without ordering constraints.
  Do NOT add [P] when tasks modify the same file —
  parallel workers will cause merge conflicts.
  Tasks without [P] run sequentially first, then [P]
  tasks run in parallel.
-->

## 1. Function surface model

- [x] 1.1 Add `FunctionSurface` (`module`, `method`, `nested`) and `EnclosingClassVisibility` (`none`, `public`, `private`) enums to `src/snake_eyes/signals/_types.py`
- [x] 1.2 Extend `_FileContext` with `surface_by_line: dict[int, FunctionSurface]` and `enclosing_class_visibility_by_line: dict[int, EnclosingClassVisibility]`
- [x] 1.3 Extend `_collect_file_context` to populate both maps from the existing `parents` walk: a function is `method` when its direct enclosing scope is a class body, `nested` when its direct enclosing scope is a function body, else `module`; enclosing-class visibility is `private` when the enclosing class name has a leading underscore OR the class itself is transitively nested inside a function body (any ancestor scope of the class is a function body), `public` otherwise, and `none` for `module`/`nested`

## 2. Surface-aware visibility extractor

- [x] 2.1 Update `visibility.extract` to accept `surface`, `enclosing_class_visibility`, and `effect_type`, applying the priority rules (nested → `PRIVATE_WEIGHT` except `ClosureCaptureMutation` → `None`; module-level dunder → `None`; dunder-method → class visibility; private-class method → `PRIVATE_WEIGHT`; else prior name/`__all__`) using only `PUBLIC_WEIGHT`/`PRIVATE_WEIGHT` (`src/snake_eyes/signals/visibility.py`)
- [x] 2.2 Wire `extract_signals` to pass surface, enclosing-class visibility, and effect type to `visibility.extract` (`src/snake_eyes/signals/adapter.py`)

## 3. Effect disposition table

- [x] 3.1 Author `docs/effect-disposition.md` recording a disposition (`incidental` / `contractual` / `unclaimed`) for each of the ten reachable `(surface, enclosing-class visibility, dunder, name-prefix, effect-type exception)` combinations, with a documentation banner and illustrative effect types in the rationale
- [x] 3.2 Add a conformance test (`tests/test_effect_disposition.py`) asserting the table covers all ten reachable combinations, has no conflicting duplicate keys, every disposition is in the closed set, every non-`unclaimed` cell has a non-empty rationale naming at least one effect type, and each row's disposition agrees with `visibility.extract`'s emitted weight (contractual ⇔ `10`, incidental ⇔ `-10`, unclaimed ⇔ no signal), and that the table carries the required documentation banner

## 4. Tests

- [x] 4.1 [P] Add surface-classification unit tests to `tests/test_signals_adapter.py`
- [x] 4.2 [P] Add surface-aware visibility unit tests to `tests/test_signals_visibility.py`
- [x] 4.3 [P] Extend `tests/test_signals_negative_label.py` to add `unclaimed` to the `FORBIDDEN` labels and to scan emitted `reasoning` strings for classification terms, and confirm it still passes against the updated `visibility.py`
- [x] 4.4 [P] Add a `classify_signals`-boundary integration test asserting a public-class `__init__` yields `visibility` weight `10` and a nested helper yields `-10` (`tests/test_classify_signals_method.py`)

## 5. Verification and measurement

- [x] 5.1 Add a `uv run coverage report --include='src/snake_eyes/signals/visibility.py,src/snake_eyes/signals/adapter.py' --fail-under=95` post-step to `ci.yml` (without lowering the protected `--cov-fail-under=85` floor; branch coverage is already enabled via `pyproject.toml` `branch = true`), then run CI parity gates: `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`, `uv run mypy src/`, and the coverage run; verify `visibility.py` and `adapter.py` combined statement+branch coverage ≥95%
- [x] 5.2 Re-measure `classification_counts` before and after with the same pinned dev gaze commit (pre-change against the snake-eyes checkout at the pre-change commit), recording both counts plus the gaze binary source/commit, protocol version, Go toolchain version, build command, and binary SHA-256 (if available) in `openspec/changes/reduce-ambiguous-effect-bucket/implementation-report.md` (committed)
- [x] 5.3 Constitution alignment verification: name all five principles (Protocol Fidelity, Detection Accuracy, Python-Native Analysis, Testability, Analysis Safety) with PASS/FAIL verdicts
- [x] 5.4 Reference `docs/effect-disposition.md` from the `README.md`/`AGENTS.md` project-structure sections, update the now-stale `visibility.py` (surface-aware; no longer defers dunder behavior to gaze-py), `_types.py` (`SignalResult` + two enums), and `adapter.py` (surface computation) descriptions, and update `AGENTS.md` "Shell Commands" and "Protected gates" to document the new per-module ≥95% coverage post-step

<!-- spec-review: passed -->
<!-- code-review: passed -->
