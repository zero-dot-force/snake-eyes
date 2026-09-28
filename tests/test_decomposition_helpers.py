"""Focused tests for helpers extracted during the high-complexity decomposition.

Issue #27 decomposed six high-complexity functions. The existing regression
suites exercise the public entry points end-to-end; this module pins the
behavior of each newly extracted helper in isolation.
"""

from __future__ import annotations

import ast
import pathlib
from unittest import mock

import astroid  # type: ignore[import-untyped]
import pytest
from astroid.util import Uninferable  # type: ignore[import-untyped]

from snake_eyes.analysis._shared import MAX_AST_DEPTH
from snake_eyes.analysis.detector import (
    _append_descriptor_effect,
    _append_env_effects,
    _append_resource_effects,
    _collect_env_mutation_nodes,
    _collect_scope_bindings,
    _resolve_local_names,
    _ScopeBindingCollector,
)
from snake_eyes.analysis.effects import SideEffectType
from snake_eyes.analysis.models import Effect
from snake_eyes.quality._provenance import (
    _append_bound_names,
    _append_classdef_bound_names,
    _append_funcdef_bound_names,
)
from snake_eyes.quality.assertions import collect_assertions
from snake_eyes.quality.pairing import (
    _callee_file,
    _collect_defined_names,
    _parse_modules,
    _resolve_call_edges,
)
from snake_eyes.quality.pipeline import (
    _build_mapping_rows,
    _build_target_indexes,
    _collect_test_evidence,
)

# -- _append_bound_names helpers (quality/_provenance.py) -------------------


def _parse_func(source: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    (node,) = tree.body
    assert isinstance(node, ast.FunctionDef)
    return node


def test_append_funcdef_bound_names_binds_name_and_nested_targets() -> None:
    node = _parse_func("def build(x=(y := 1)):\n    return x\n")
    names: set[str] = set()
    _append_funcdef_bound_names(node, names, depth=1)
    assert "build" in names
    assert "y" in names


def test_append_classdef_bound_names_binds_name() -> None:
    tree = ast.parse("class Foo(Base):\n    pass\n")
    (node,) = tree.body
    assert isinstance(node, ast.ClassDef)
    names: set[str] = set()
    _append_classdef_bound_names(node, names, depth=1)
    assert names == {"Foo"}


def test_append_bound_names_respects_depth_budget() -> None:
    node = ast.Name(id="x", ctx=ast.Load())
    with pytest.raises(RecursionError):
        _append_bound_names(node, set(), depth=MAX_AST_DEPTH + 1)


def test_append_bound_names_import_binds_first_dot_part() -> None:
    tree = ast.parse("import os.path\n")
    names: set[str] = set()
    _append_bound_names(tree.body[0], names, depth=1)
    assert "os" in names


# -- _parse_modules / _collect_defined_names / _callee_file / _resolve_call_edges


def test_parse_modules_collects_analyzable_files(tmp_path: pathlib.Path) -> None:
    (tmp_path / "prod.py").write_text("def add(a, b):\n    return a + b\n")
    parsed = _parse_modules(astroid.MANAGER, tmp_path, ["prod.py"])
    assert len(parsed) == 1
    norm, module = parsed[0]
    assert norm == str((tmp_path / "prod.py").resolve())
    assert module is not None


def test_parse_modules_rereads_file_not_found(tmp_path: pathlib.Path) -> None:
    (tmp_path / "prod.py").write_text("def add(a, b):\n    return a + b\n")
    manager = mock.Mock()
    manager.ast_from_file.side_effect = FileNotFoundError("missing")
    with pytest.raises(FileNotFoundError):
        _parse_modules(manager, tmp_path, ["prod.py"])


def test_collect_defined_names(tmp_path: pathlib.Path) -> None:
    (tmp_path / "prod.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef helper():\n    return add(1, 2)\n"
    )
    parsed = _parse_modules(astroid.MANAGER, tmp_path, ["prod.py"])
    defined = _collect_defined_names(parsed)
    assert {"add", "helper"} <= defined


def test_callee_file_uninferable_returns_none() -> None:
    assert _callee_file(Uninferable) is None


def test_resolve_call_edges_finds_in_project_callee(tmp_path: pathlib.Path) -> None:
    (tmp_path / "a.py").write_text("def compute():\n    return 1\n")
    (tmp_path / "b.py").write_text("import a\n\n\ndef run():\n    return a.compute()\n")
    parsed = _parse_modules(astroid.MANAGER, tmp_path, ["a.py", "b.py"])
    defined = _collect_defined_names(parsed)
    edges: dict[str, set[str]] = {}
    _resolve_call_edges(parsed, defined, edges)
    norm_a = str((tmp_path / "a.py").resolve())
    norm_b = str((tmp_path / "b.py").resolve())
    assert norm_b in edges
    assert norm_a in edges[norm_b]


# -- collect_assertions (drives the visit_stmt helper dispatch) -------------


def test_collect_assertions_assert_stmt() -> None:
    node = _parse_func("def test_x():\n    assert x == 1\n")
    results = collect_assertions(node, "test_x.py")
    assert len(results) == 1
    assert results[0].assertion_type == "equality"


def test_collect_assertions_with_raises_call() -> None:
    node = _parse_func(
        "def test_x():\n"
        "    with pytest.raises(ValueError):\n"
        "        raise ValueError()\n"
    )
    results = collect_assertions(node, "test_x.py")
    assert any(r.assertion_type == "error_check" for r in results)


# -- _process_class_statement / _record_class_bindings -----------------------


def test_process_class_statement_records_bindings() -> None:
    statement = ast.parse("x = 1\n").body[0]
    collector = _ScopeBindingCollector()
    collector.visit(statement)
    visitor = _ScopeBindingCollector()
    class_names: set[str] = set()
    class_aliases: dict[str, set[str]] = {}
    visitor._process_class_statement(
        statement, collector, set(), class_names, class_aliases
    )
    assert "x" in class_names


def test_process_class_statement_delete_removes_names() -> None:
    statement = ast.parse("del x\n").body[0]
    collector = _ScopeBindingCollector()
    collector.visit(statement)
    visitor = _ScopeBindingCollector()
    class_names = {"x"}
    class_aliases: dict[str, set[str]] = {"x": {"x"}}
    visitor._process_class_statement(
        statement, collector, set(), class_names, class_aliases
    )
    assert "x" not in class_names
    assert "x" not in class_aliases


# -- _analyze_func_node helpers ---------------------------------------------


def test_resolve_local_names_resolves_nested_function() -> None:
    node = _parse_func(
        "def outer():\n    def inner():\n        return 1\n    return inner()\n"
    )
    scope_bindings = _collect_scope_bindings(node)
    bound_names = set(scope_bindings.counts)
    resolved = _resolve_local_names(
        node, scope_bindings, bound_names, None, None, scope_bindings.global_names
    )
    assert "inner" in resolved


def test_collect_env_mutation_nodes() -> None:
    node = _parse_func("def f():\n    os.environ['K'] = 'v'\n")
    nodes = _collect_env_mutation_nodes(node)
    assert len(nodes) == 1


def test_append_env_effects() -> None:
    node = _parse_func("def f():\n    os.environ['K'] = 'v'\n")
    env_nodes = _collect_env_mutation_nodes(node)
    effects: list[Effect] = []
    _append_env_effects(effects, env_nodes, "f.py")
    assert len(effects) == 1
    assert effects[0].type == str(SideEffectType.EnvVarMutation)


def test_append_descriptor_effect() -> None:
    node = _parse_func("def __get__(self, obj, objtype):\n    return self\n")
    effects: list[Effect] = []
    _append_descriptor_effect(effects, node, "d.py", True)
    assert len(effects) == 1
    assert effects[0].type == str(SideEffectType.DescriptorEffect)


def test_append_resource_effects_method_and_contextmanager() -> None:
    node = _parse_func("def __enter__(self):\n    return self\n")
    effects: list[Effect] = []
    _append_resource_effects(effects, node, "r.py", True)
    assert len(effects) == 1
    assert effects[0].type == str(SideEffectType.ResourceManagement)

    decorated = _parse_func("@contextmanager\ndef cm():\n    yield 1\n")
    effects = []
    _append_resource_effects(effects, decorated, "r.py", False)
    assert len(effects) == 1
    assert effects[0].type == str(SideEffectType.ResourceManagement)


# -- run_test_mapping helpers (quality/pipeline.py) -------------------------


def test_collect_test_evidence_empty_input() -> None:
    assertions, contexts = _collect_test_evidence([], {}, None)
    assert assertions == {}
    assert contexts == {}


def test_build_target_indexes_empty_pairs() -> None:
    by_identity, counts, import_packages = _build_target_indexes([], [], None)
    assert by_identity == {}
    assert counts == {}
    assert import_packages == {}


def test_build_mapping_rows_empty_pairs() -> None:
    rows = _build_mapping_rows([], {}, {}, {}, {}, {}, None)
    assert rows == []
