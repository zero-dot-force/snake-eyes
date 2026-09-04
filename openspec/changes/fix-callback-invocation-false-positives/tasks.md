## 1. Expand known-name collection

- [x] 1.1 In `_analyze_tree`, add safe trivial `ast.ClassDef` names to `module_func_names`
- [x] 1.2 In `_analyze_func_node`, add safe trivial nested `ast.ClassDef` names to `local_func_names`

## 2. Add scope-aware ClassDef resolution to `_handle_call`

- [x] 2.1 Ensure a function parameter shadows a same-named module ClassDef before local-name suppression
- [x] 2.2 Collect all lexical binding forms without entering child scopes and preserve enclosing-function bindings
- [x] 2.3 Reject conditional, duplicate, wildcard-imported, globally mutated, and constructor-mutated class bindings
- [x] 2.4 Bound binding traversal depth and share module/closure resolution state without per-function module-set copies
- [x] 2.5 Canonicalize direct-name aliases and propagate constructor mutations through transitive and class-body aliases

## 3. Tests

- [x] 3.2 Add test for same-module class resolution: function calling a class defined at module level should NOT produce `CallbackInvocation`
- [x] 3.3 Add test for nested class resolution: function calling a nested class should NOT produce `CallbackInvocation`
- [x] 3.4 Add tests that imported and PascalCase calls remain ambiguous
- [x] 3.5 Add a test that a parameter shadows a same-named module ClassDef
- [x] 3.8 Update existing golden tests only for trivial same-module class constructors; imported and unresolved PascalCase calls remain ambiguous
- [x] 3.9 Add lexical-scope regressions for control-flow binders, definition headers, closure shadowing, duplicate definitions, and nested-scope isolation
- [x] 3.10 Add regressions for control-flow-nested globals and direct/reflective constructor mutation
- [x] 3.11 Add alias regressions for transitive chains, class bodies, annotation, rebinding, deletion, and cycles

## 4. Verification

- [x] 4.1 Run `uv run ruff check src/ tests/` — must pass
- [x] 4.2 Run `uv run ruff format --check src/ tests/` — must pass
- [x] 4.3 Run `uv run mypy src/` — must pass
- [x] 4.4 Run `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85` — must pass with ≥85% coverage

<!-- spec-review: passed -->
<!-- code-review: passed -->
