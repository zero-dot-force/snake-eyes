"""Bounded static provenance analysis for test-mapping assertions.

This module owns import identity, lexical shadowing, mutation invalidation, and
paired-target result tracing. It intentionally exposes only a narrow internal
context/query API so ``pipeline.py`` remains orchestration-focused.
"""

from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass
from typing import Any

from ..analysis._shared import MAX_AST_DEPTH, _is_plain_len_call
from .assertions import AssertionInfo


@dataclass(frozen=True)
class _NameEvent:
    """One binding or invalidation event in a test scope."""

    position: tuple[int, int]
    value: ast.expr | None
    writes: bool
    escapes: bool


@dataclass
class _ModuleContext:
    """Reusable module-level import and mutation evidence for one test file."""

    imports: dict[str, str]
    shadowed_names: frozenset[str]
    name_events: dict[str, list[_NameEvent]]
    current_package: str


@dataclass
class _ProvenanceContext:
    """Precomputed lexical and binding evidence for one test function."""

    imports: dict[str, str]
    import_positions: dict[str, tuple[int, int]]
    module_shadowed_names: frozenset[str]
    module_name_events: dict[str, list[_NameEvent]]
    function_local_names: frozenset[str]
    name_events: dict[str, list[_NameEvent]]


def _node_position(node: ast.AST) -> tuple[int, int]:
    """Return a source position for deterministic ordering checks."""
    return (
        int(getattr(node, "lineno", 0)),
        int(getattr(node, "col_offset", 0)),
    )


def _dotted_name(node: ast.expr) -> tuple[str, ...] | None:
    """Return bounded dotted-name components, or ``None`` for dynamic receivers."""
    components: list[str] = []
    depth = 1
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        if depth > MAX_AST_DEPTH:
            raise RecursionError("AST depth budget exceeded in result provenance")
        components.append(current.attr)
        current = current.value
        depth += 1
    if not isinstance(current, ast.Name):
        return None
    components.append(current.id)
    components.reverse()
    return tuple(components)


def _canonical_import_packages(root: pathlib.Path, rel_file: str) -> frozenset[str]:
    """Derive valid module identities for source layouts and real packages."""
    relative_path = pathlib.PurePosixPath(rel_file)
    module_parts = list(relative_path.with_suffix("").parts)
    if module_parts[-1] == "__init__":
        module_parts.pop()
    packages = {".".join(module_parts)}
    if module_parts and module_parts[0] in {"src", "lib"}:
        source_root = root / module_parts[0]
        if not (source_root / "__init__.py").is_file():
            packages.add(".".join(module_parts[1:]))
    return frozenset(package for package in packages if package)


def _canonical_test_module(root: pathlib.Path, rel_file: str) -> str:
    """Choose the test module identity used to resolve relative imports."""
    candidates = _canonical_import_packages(root, rel_file)
    without_layout = [
        candidate
        for candidate in candidates
        if not candidate.startswith(("src.", "lib."))
    ]
    return min(without_layout or list(candidates), key=lambda value: value.count("."))


def _resolve_import_from(node: ast.ImportFrom, current_package: str) -> str | None:
    """Resolve one absolute or package-relative import module statically."""
    if node.level == 0:
        return node.module
    package_parts = current_package.split(".") if current_package else []
    parent_count = node.level - 1
    if parent_count > len(package_parts):
        return None
    base_parts = package_parts[: len(package_parts) - parent_count]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts) or None


def _append_bound_names(
    node: ast.AST,
    names: set[str],
    *,
    depth: int = 1,
) -> None:
    """Append names bound by *node* without entering a nested runtime scope."""
    if depth > MAX_AST_DEPTH:
        raise RecursionError("AST depth budget exceeded in lexical provenance")
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names.add(node.name)
        expressions = [
            *node.decorator_list,
            *node.args.defaults,
            *(default for default in node.args.kw_defaults if default is not None),
        ]
        if node.returns is not None:
            expressions.append(node.returns)
        for expression in expressions:
            _append_bound_names(expression, names, depth=depth + 1)
        return
    if isinstance(node, ast.ClassDef):
        names.add(node.name)
        for expression in (*node.decorator_list, *node.bases):
            _append_bound_names(expression, names, depth=depth + 1)
        for keyword in node.keywords:
            _append_bound_names(keyword.value, names, depth=depth + 1)
        return
    if isinstance(node, ast.Lambda):
        return
    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        names.add(node.id)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        names.update(
            alias.asname or alias.name.split(".", 1)[0] for alias in node.names
        )
        return
    if isinstance(node, ast.ExceptHandler) and node.name is not None:
        names.add(node.name)
    if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name is not None:
        names.add(node.name)
    if isinstance(node, ast.MatchMapping) and node.rest is not None:
        names.add(node.rest)
    for child in ast.iter_child_nodes(node):
        _append_bound_names(child, names, depth=depth + 1)


def _record_import(
    imports: dict[str, str],
    shadowed: set[str],
    local_name: str,
    qualified_name: str,
) -> None:
    previous = imports.get(local_name)
    if previous is not None and previous != qualified_name:
        shadowed.add(local_name)
    imports[local_name] = qualified_name


def _module_name_context(
    tree: ast.Module, current_package: str
) -> tuple[dict[str, str], frozenset[str]]:
    """Return unambiguous imports and conflicting module bindings."""
    imports: dict[str, str] = {}
    shadowed: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                qualified_name = alias.name if alias.asname else local_name
                _record_import(imports, shadowed, local_name, qualified_name)
            continue
        if isinstance(statement, ast.ImportFrom):
            imported_module = _resolve_import_from(statement, current_package)
            for alias in statement.names:
                if alias.name == "*":
                    continue
                local_name = alias.asname or alias.name
                if imported_module is None:
                    shadowed.add(local_name)
                    continue
                _record_import(
                    imports,
                    shadowed,
                    local_name,
                    f"{imported_module}.{alias.name}",
                )
            continue
        bound_names: set[str] = set()
        _append_bound_names(statement, bound_names)
        shadowed.update(bound_names)
    return imports, frozenset(shadowed)


def _function_name_context(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    current_package: str,
) -> tuple[frozenset[str], dict[str, str], dict[str, tuple[int, int]]]:
    """Return true local shadows and resolvable direct function imports."""
    names = {
        argument.arg
        for argument in (
            *func_node.args.posonlyargs,
            *func_node.args.args,
            *func_node.args.kwonlyargs,
        )
    }
    if func_node.args.vararg is not None:
        names.add(func_node.args.vararg.arg)
    if func_node.args.kwarg is not None:
        names.add(func_node.args.kwarg.arg)

    imports: dict[str, str] = {}
    import_positions: dict[str, tuple[int, int]] = {}
    for statement in func_node.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                imports[local_name] = alias.name if alias.asname else local_name
                import_positions[local_name] = _node_position(statement)
            continue
        if isinstance(statement, ast.ImportFrom):
            imported_module = _resolve_import_from(statement, current_package)
            if imported_module is not None:
                for alias in statement.names:
                    if alias.name == "*":
                        continue
                    local_name = alias.asname or alias.name
                    imports[local_name] = f"{imported_module}.{alias.name}"
                    import_positions[local_name] = _node_position(statement)
                continue
        _append_bound_names(statement, names)
    return frozenset(names), imports, import_positions


def _simple_assignment(stmt: ast.stmt) -> tuple[str, ast.expr | None] | None:
    """Return a top-level simple assignment's name and value."""
    if (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and isinstance(stmt.targets[0], ast.Name)
    ):
        return stmt.targets[0].id, stmt.value
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return stmt.target.id, stmt.value
    return None


class _NameEventVisitor(ast.NodeVisitor):
    """Build invalidation events in one bounded pass without nested scopes."""

    def __init__(self, events: dict[str, list[_NameEvent]]) -> None:
        self._events = events
        self._invalidate_loads = 0
        self._write_loads = 0
        self._escape_loads = 0
        self._simple_target_id: int | None = None
        self._depth = 0

    def visit(self, node: ast.AST) -> Any:
        """Visit within the shared AST depth budget."""
        self._depth += 1
        if self._depth > MAX_AST_DEPTH:
            self._depth -= 1
            raise RecursionError("AST depth budget exceeded in result provenance")
        try:
            return super().visit(node)
        finally:
            self._depth -= 1

    def _record(
        self,
        name: str,
        node: ast.AST,
        value: ast.expr | None = None,
        *,
        writes: bool = False,
        escapes: bool = False,
    ) -> None:
        self._events.setdefault(name, []).append(
            _NameEvent(_node_position(node), value, writes, escapes)
        )

    def visit_Name(self, node: ast.Name) -> None:
        """Record writes and loads in invalidating expression contexts."""
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            if id(node) != self._simple_target_id:
                self._record(node.id, node, writes=True)
        elif isinstance(node.ctx, ast.Load) and self._invalidate_loads:
            self._record(
                node.id,
                node,
                writes=bool(self._write_loads),
                escapes=bool(self._escape_loads),
            )

    def _visit_invalidating(
        self,
        node: ast.AST | None,
        *,
        writes: bool = False,
        escapes: bool = False,
    ) -> None:
        if node is None:
            return
        self._invalidate_loads += 1
        self._write_loads += int(writes)
        self._escape_loads += int(escapes)
        try:
            self.visit(node)
        finally:
            self._escape_loads -= int(escapes)
            self._write_loads -= int(writes)
            self._invalidate_loads -= 1

    def visit_Assign(self, node: ast.Assign) -> None:
        """Treat RHS references as aliases and complex targets as mutations."""
        for target in node.targets:
            if isinstance(target, (ast.Attribute, ast.Subscript)):
                self._visit_invalidating(target, writes=True)
            else:
                self.visit(target)
        self._visit_invalidating(node.value, escapes=True)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Handle annotated assignments without revisiting subtrees."""
        if isinstance(node.target, (ast.Attribute, ast.Subscript)):
            self._visit_invalidating(node.target, writes=True)
        else:
            self.visit(node.target)
        self.visit(node.annotation)
        self._visit_invalidating(node.value, escapes=True)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Augmented assignment invalidates its target and RHS aliases."""
        self._visit_invalidating(node.target, writes=True)
        self._visit_invalidating(node.value, escapes=True)

    def visit_Delete(self, node: ast.Delete) -> None:
        """Deleting a name or member invalidates its provenance."""
        for target in node.targets:
            self._visit_invalidating(target, writes=True)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        """Walrus assignments bind a name and can alias their value."""
        self.visit(node.target)
        self._visit_invalidating(node.value, escapes=True)

    def visit_Call(self, node: ast.Call) -> None:
        """Treat non-builtin-len calls as mutation or alias escape."""
        if _is_plain_len_call(node):
            self.visit(node.func)
            for argument in node.args:
                self.visit(argument)
            return
        self._visit_invalidating(node.func)
        for argument in node.args:
            self._visit_invalidating(argument, escapes=True)
        for keyword in node.keywords:
            self._visit_invalidating(keyword.value, escapes=True)

    def visit_Return(self, node: ast.Return) -> None:
        """A returned local escapes conservative provenance."""
        self._visit_invalidating(node.value, escapes=True)

    def visit_Yield(self, node: ast.Yield) -> None:
        """A yielded local escapes conservative provenance."""
        self._visit_invalidating(node.value, escapes=True)

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        """A delegated yielded local escapes conservative provenance."""
        self._visit_invalidating(node.value, escapes=True)

    def _visit_definition_expressions(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        if node.returns is not None:
            self.visit(node.returns)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Inspect definition expressions, not the nested body."""
        self._visit_definition_expressions(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Inspect definition expressions, not the nested body."""
        self._visit_definition_expressions(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Inspect class expressions, not the nested body."""
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_statement(
        self,
        statement: ast.stmt,
        simple_assignment: tuple[str, ast.expr | None] | None,
    ) -> None:
        """Visit one statement with its allowed simple binding."""
        self._simple_target_id = None
        if simple_assignment is not None:
            if isinstance(statement, ast.Assign):
                target = statement.targets[0]
            elif isinstance(statement, ast.AnnAssign):
                target = statement.target
            else:
                raise TypeError("simple assignment metadata requires an assignment")
            self._simple_target_id = id(target)
            self._record(
                simple_assignment[0],
                statement,
                simple_assignment[1],
                writes=True,
                escapes=False,
            )
        try:
            self.visit(statement)
        finally:
            self._simple_target_id = None


def _build_name_events(
    statements: list[ast.stmt],
) -> dict[str, list[_NameEvent]]:
    """Index bindings and conservative invalidations once."""
    events: dict[str, list[_NameEvent]] = {}
    visitor = _NameEventVisitor(events)
    for statement in statements:
        visitor.visit_statement(statement, _simple_assignment(statement))
    for name_events in events.values():
        name_events.sort(key=lambda event: event.position)
    return events


def _build_module_context(
    tree: ast.Module, root: pathlib.Path, test_file: str
) -> _ModuleContext:
    """Build reusable module evidence once per parsed test file."""
    test_module = _canonical_test_module(root, test_file)
    if test_file.endswith("/__init__.py"):
        current_package = test_module
    elif "." in test_module:
        current_package = test_module.rsplit(".", 1)[0]
    else:
        current_package = ""
    imports, shadowed_names = _module_name_context(tree, current_package)
    non_import_statements = [
        statement
        for statement in tree.body
        if not isinstance(statement, (ast.Import, ast.ImportFrom))
    ]
    return _ModuleContext(
        imports=imports,
        shadowed_names=shadowed_names,
        name_events=_build_name_events(non_import_statements),
        current_package=current_package,
    )


def _build_provenance_context(
    module_context: _ModuleContext,
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> _ProvenanceContext:
    """Build reusable provenance evidence for one parsed test function."""
    local_names, function_imports, import_positions = _function_name_context(
        func_node, module_context.current_package
    )
    imports = dict(module_context.imports)
    imports.update(function_imports)
    return _ProvenanceContext(
        imports=imports,
        import_positions=import_positions,
        module_shadowed_names=module_context.shadowed_names,
        module_name_events=module_context.name_events,
        function_local_names=local_names,
        name_events=_build_name_events(func_node.body),
    )


def _empty_provenance_context() -> _ProvenanceContext:
    """Return evidence that disables every container-state override."""
    return _ProvenanceContext(
        imports={},
        import_positions={},
        module_shadowed_names=frozenset(),
        module_name_events={},
        function_local_names=frozenset(),
        name_events={},
    )


def _is_direct_target_call(
    candidate: ast.expr,
    target_function: str,
    target_package: frozenset[str] | str | None = None,
    context: _ProvenanceContext | None = None,
) -> bool:
    """Match a bare or qualified direct call to the exact paired target."""
    if not isinstance(candidate, ast.Call):
        return False
    callee_name = _dotted_name(candidate.func)
    if callee_name is None:
        return False
    if target_package is None or context is None:
        return callee_name[-1] == target_function

    local_name = callee_name[0]
    if (
        local_name in context.function_local_names
        or local_name in context.module_shadowed_names
    ):
        return False
    imported_name = context.imports.get(local_name)
    if imported_name is None:
        return False
    candidate_position = _node_position(candidate)
    import_position = context.import_positions.get(local_name)
    if import_position is not None and import_position >= candidate_position:
        return False
    if any(
        (event.writes or event.escapes) and event.position < candidate_position
        for event in context.name_events.get(local_name, [])
    ):
        return False
    if any(
        event.writes or event.escapes
        for event in context.module_name_events.get(local_name, [])
    ):
        return False
    resolved_name = ".".join((imported_name, *callee_name[1:]))
    target_packages = (
        target_package
        if isinstance(target_package, frozenset)
        else frozenset({target_package})
    )
    return resolved_name in {
        f"{package}.{target_function}" for package in target_packages
    }


def _name_is_direct_target_result(
    name: str,
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    assertion: AssertionInfo,
    target_function: str,
    target_package: frozenset[str] | str | None,
    context: _ProvenanceContext | None,
) -> bool:
    """Trace one simple local name without aliases or control-flow merging."""
    assertion_position = (assertion.line, assertion.col)
    events = (
        _build_name_events(func_node.body).get(name, [])
        if context is None
        else context.name_events.get(name, [])
    )
    binding: ast.expr | None = None
    for event in events:
        if event.position >= assertion_position:
            break
        if event.value is None or binding is not None:
            return False
        binding = event.value
    return binding is not None and _is_direct_target_call(
        binding, target_function, target_package, context
    )


def _expression_invalidates_name(expression: ast.expr | None, name: str) -> bool:
    """Return whether an assertion expression can mutate or escape *name*."""
    if expression is None:
        return False
    events: dict[str, list[_NameEvent]] = {}
    _NameEventVisitor(events).visit(expression)
    return bool(events.get(name))


def _observes_container_state(
    assertion: AssertionInfo,
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    target_function: str,
    target_package: frozenset[str] | str | None = None,
    context: _ProvenanceContext | None = None,
) -> bool:
    """Resolve assertion observations against one conservatively paired target."""
    for observation in assertion.observations:
        candidate = observation.candidate
        try:
            if (
                observation.kind == "len"
                and context is not None
                and (
                    "len" in context.function_local_names
                    or "len" in context.module_shadowed_names
                    or "len" in context.imports
                )
            ):
                continue
            if _is_direct_target_call(
                candidate, target_function, target_package, context
            ):
                return True
            if isinstance(candidate, ast.Name):
                if _expression_invalidates_name(assertion.expression, candidate.id):
                    continue
                if _name_is_direct_target_result(
                    candidate.id,
                    func_node,
                    assertion,
                    target_function,
                    target_package,
                    context,
                ):
                    return True
        except (RecursionError, MemoryError):
            continue
    return False


class ProvenanceResolver:
    """Build and query bounded provenance while caching per-file module state."""

    def __init__(self, root: pathlib.Path) -> None:
        """Create a resolver scoped to one analyzed project root."""
        self._root = root
        self._module_contexts: dict[str, _ModuleContext] = {}

    def target_packages(self, target_file: str) -> frozenset[str]:
        """Return valid import identities for one target source file."""
        return _canonical_import_packages(self._root, target_file)

    def build_context(
        self,
        tree: ast.Module,
        test_file: str,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> _ProvenanceContext:
        """Build function evidence, reusing module evidence for the test file."""
        module_context = self._module_contexts.get(test_file)
        if module_context is None:
            module_context = _build_module_context(tree, self._root, test_file)
            self._module_contexts[test_file] = module_context
        return _build_provenance_context(module_context, func_node)

    @staticmethod
    def empty_context() -> _ProvenanceContext:
        """Return a conservative context that disables provenance overrides."""
        return _empty_provenance_context()

    @staticmethod
    def observes_container_state(
        assertion: AssertionInfo,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        target_function: str,
        target_packages: frozenset[str],
        context: _ProvenanceContext,
    ) -> bool:
        """Resolve one assertion against the selected target identities."""
        return _observes_container_state(
            assertion,
            func_node,
            target_function,
            target_packages,
            context,
        )
