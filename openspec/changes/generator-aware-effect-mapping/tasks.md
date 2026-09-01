## 1. Update Mapping Logic

- [x] 1.1 In `quality/mapping.py`, add generator-yield check to the value-type assertion chain: after the P0 scan loop, check for `GeneratorYield` in `effect_types`, then `AsyncGeneratorYield`, before the `ReturnValue` fallback
- [x] 1.2 Update the docstring of `infer_side_effect_type` to document the expanded value-type chain: `ReturnValue → first P0 → GeneratorYield → AsyncGeneratorYield → ReturnValue (fallback)`

## 2. Tests

- [x] 2.1 Add test: value-type assertion with target that has only `GeneratorYield` effect maps to `GeneratorYield` — this is the primary regression test for issue #13; the assertion MUST be `== "GeneratorYield"` (on unfixed code, this returns `"ReturnValue"`)
- [x] 2.2 Add test: value-type assertion with target that has only `AsyncGeneratorYield` effect maps to `AsyncGeneratorYield` — assertion MUST be `== "AsyncGeneratorYield"` (on unfixed code, this returns `"ReturnValue"`)
- [x] 2.3 Add test: value-type assertion with target that has both `ReturnValue` and `GeneratorYield` maps to `ReturnValue` (precedence)
- [x] 2.4 Add test: value-type assertion with target that has `GeneratorYield` and a P0 effect (not `ReturnValue`) maps to the P0 effect (P0 takes precedence over generator yield)
- [x] 2.5 Add test: value-type assertion with target that has no effects still falls back to `ReturnValue`
- [x] 2.6 Add test: generic assertion with target that has `GeneratorYield` as first effect followed by at least one other effect (e.g., `[GeneratorYield, GlobalMutation]`) maps to `GeneratorYield` — regression guard confirming generic chain returns first effect, not a generator-specific lookup
- [x] 2.7 Add test: value-type assertion with target that has both `GeneratorYield` and `AsyncGeneratorYield` (no `ReturnValue`, no P0) maps to `GeneratorYield` (GeneratorYield takes precedence over AsyncGeneratorYield)

## 3. CI Verification

- [x] 3.1 Run `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/` — fix any issues
- [x] 3.2 Run `uv run mypy src/` — fix any type errors
- [x] 3.3 Run `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85` — all tests pass, coverage gate met
<!-- spec-review: passed -->
<!-- code-review: passed -->
