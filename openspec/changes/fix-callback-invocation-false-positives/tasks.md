## 1. Expand known-name collection

- [x] 1.1 In `_analyze_tree`, add `ast.ClassDef` to the `module_func_names` comprehension so module-level class names are included in the known-callable set
- [x] 1.2 In `_analyze_single_function`, add `ast.ClassDef` to the nested-child check alongside `FunctionDef`/`AsyncFunctionDef` so nested class names are included in `local_func_names`

## 2. Add import-aware and PascalCase resolution to `_handle_call`

- [x] 2.1 In `_handle_call`, after the `local_func_names` check and before the `CallbackInvocation` fallthrough, add a check against `self.import_aliases` — if the name is a key in `import_aliases`, return without emitting
- [x] 2.2 Add a PascalCase regex constant (e.g., `_PASCAL_CASE_RE = re.compile(r'^[A-Z][a-zA-Z0-9]*$')`) near the top of detector.py
- [x] 2.3 In `_handle_call`, after the `import_aliases` check, add a PascalCase pattern match — if the name matches, return without emitting

## 3. Tests

- [x] 3.1 Add test for import-aware resolution: function calling an imported name (in `import_aliases`) should NOT produce `CallbackInvocation`
- [x] 3.2 Add test for same-module class resolution: function calling a class defined at module level should NOT produce `CallbackInvocation`
- [x] 3.3 Add test for nested class resolution: function calling a nested class should NOT produce `CallbackInvocation`
- [x] 3.4 Add test for PascalCase heuristic: unknown PascalCase name should NOT produce `CallbackInvocation`
- [x] 3.5 Add test that genuinely unknown lowercase name still produces `CallbackInvocation` (regression guard)
- [x] 3.6 Add test for ALL_CAPS name (not PascalCase) still producing `CallbackInvocation`
- [x] 3.7 Add test for resolution order: name in `import_aliases` but not `local_func_names` still resolves (no effect)
- [x] 3.8 Update `test_p0_golden_full_equality` and any other existing tests that assert `CallbackInvocation` for PascalCase class names or imported names — the behavioral change means these effects will no longer be emitted

## 4. Verification

- [x] 4.1 Run `uv run ruff check src/ tests/` — must pass
- [x] 4.2 Run `uv run ruff format --check src/ tests/` — must pass
- [x] 4.3 Run `uv run mypy src/` — must pass
- [x] 4.4 Run `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85` — must pass with ≥85% coverage

<!-- spec-review: passed -->
<!-- code-review: passed -->
