"""Focused regressions for bounded target-result provenance."""

from pathlib import Path
from unittest import mock

import pytest

from snake_eyes.analysis.effects import SideEffectType
from snake_eyes.quality.pipeline import run_test_mapping


def _write_container_target(path: Path, value: str = "alpha") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "def build_items():\n"
        "    items = []\n"
        f"    items.append({value!r})\n"
        "    return items\n"
    )


def test_provenance_failure_retains_duplicate_name_pairings(
    tmp_path: Path,
) -> None:
    """Optional provenance failure must preserve the pre-change pairing rows."""
    _write_container_target(tmp_path / "pkg_a.py", "a")
    _write_container_target(tmp_path / "pkg_b.py", "b")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_containers.py").write_text(
        "import pkg_a\n\n\n"
        "def test_BUILD_ITEMS():\n"
        "    assert len(pkg_a.build_items()) == 1\n"
    )

    with mock.patch(
        "snake_eyes.quality._provenance.ProvenanceResolver.build_context",
        side_effect=RecursionError("depth exceeded"),
    ):
        rows = run_test_mapping(str(tmp_path), None)

    assert len(rows) == 2
    assert [row["target_package"] for row in rows] == ["pkg_a", "pkg_b"]
    assert {row["confidence"] for row in rows} == {70}
    assert {row["side_effect_type"] for row in rows} == {
        str(SideEffectType.ReturnValue)
    }


@pytest.mark.parametrize("layout_root", ["src", "lib"])
def test_source_layout_prefix_is_removed_when_not_a_package(
    tmp_path: Path,
    layout_root: str,
) -> None:
    """Conventional source roots are omitted from resolved import identity."""
    _write_container_target(tmp_path / layout_root / "acme" / "containers.py")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_containers.py").write_text(
        "import acme.containers\n\n\n"
        "def test_build_items():\n"
        "    assert len(acme.containers.build_items()) == 1\n"
    )

    rows = run_test_mapping(str(tmp_path), None)

    assert len(rows) == 1
    assert rows[0]["target_package"] == f"{layout_root}.acme.containers"
    assert rows[0]["side_effect_type"] == str(SideEffectType.ContainerMutation)


@pytest.mark.parametrize("package_name", ["src", "lib"])
def test_prefix_is_preserved_when_it_is_an_importable_package(
    tmp_path: Path,
    package_name: str,
) -> None:
    """Real packages named src or lib retain their complete module identity."""
    package = tmp_path / package_name
    package.mkdir()
    (package / "__init__.py").write_text("")
    _write_container_target(package / "containers.py")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_containers.py").write_text(
        f"import {package_name}.containers\n\n\n"
        "def test_build_items():\n"
        f"    assert len({package_name}.containers.build_items()) == 1\n"
    )

    rows = run_test_mapping(str(tmp_path), None)

    assert len(rows) == 1
    assert rows[0]["target_package"] == f"{package_name}.containers"
    assert rows[0]["side_effect_type"] == str(SideEffectType.ContainerMutation)


@pytest.mark.parametrize(
    "assertion",
    [
        "self.assertNotEqual(first=len(build_items()), second=2)",
        "self.assertNotAlmostEqual(first=len(build_items()), second=2)",
        "self.assertDictEqual(d1=build_items()[0], d2='alpha')",
        "self.assertListEqual(list1=build_items()[:], list2=['alpha'])",
        "self.assertMultiLineEqual(first=build_items()[0], second='alpha')",
        "self.assertCountEqual(first=build_items()[:], second=['alpha'])",
        "self.assertSequenceEqual(seq1=build_items()[:], seq2=['alpha'])",
    ],
    ids=[
        "not-equal",
        "not-almost-equal",
        "dict-equal",
        "list-equal",
        "multiline-equal",
        "count-equal",
        "sequence-equal",
    ],
)
def test_unittest_method_specific_keywords_observe_container_state(
    tmp_path: Path,
    assertion: str,
) -> None:
    """Each supported unittest signature resolves only its asserted operands."""
    _write_container_target(tmp_path / "containers.py")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_containers.py").write_text(
        "from containers import build_items\n\n\n"
        "def test_build_items():\n"
        f"    {assertion}\n"
    )

    rows = run_test_mapping(str(tmp_path), None)

    assert len(rows) == 1
    assert rows[0]["side_effect_type"] == str(SideEffectType.ContainerMutation)


@pytest.mark.parametrize("layout_root", ["src", "lib"])
def test_source_layout_namespace_package_without_init_py(
    tmp_path: Path,
    layout_root: str,
) -> None:
    """PEP 420 namespace packages named src or lib retain their full identity."""
    (tmp_path / layout_root).mkdir()
    _write_container_target(tmp_path / layout_root / "containers.py")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_containers.py").write_text(
        f"import {layout_root}.containers\n\n\n"
        "def test_build_items():\n"
        f"    assert len({layout_root}.containers.build_items()) == 1\n"
    )

    rows = run_test_mapping(str(tmp_path), None)

    assert len(rows) == 1
    assert rows[0]["target_package"] == f"{layout_root}.containers"
    assert rows[0]["side_effect_type"] == str(SideEffectType.ContainerMutation)


def test_imported_module_escape_invalidates_target_provenance(
    tmp_path: Path,
) -> None:
    """A helper mutating an imported module must not fabricate target credit."""
    _write_container_target(tmp_path / "containers.py")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_containers.py").write_text(
        "import containers\n"
        "from unittest import mock\n\n\n"
        "def test_build_items():\n"
        "    mock.patch.object(containers, 'build_items', lambda: [])\n"
        "    assert len(containers.build_items()) == 0\n"
    )

    rows = run_test_mapping(str(tmp_path), None)

    assert rows
    assert {row["side_effect_type"] for row in rows} == {
        str(SideEffectType.ReturnValue)
    }


def test_same_module_duplicate_target_disables_override(
    tmp_path: Path,
) -> None:
    """Same-package name collisions must not receive a false mutation override."""
    (tmp_path / "m.py").write_text(
        "class Box:\n"
        "    def build_items(self):\n"
        "        items = []\n"
        "        items.append('alpha')\n"
        "        return items\n\n\n"
        "def build_items():\n"
        "    items = []\n"
        "    items.append('beta')\n"
        "    return items\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_m.py").write_text(
        "from m import build_items\n\n\n"
        "def test_build_items():\n"
        "    assert len(build_items()) == 1\n"
    )

    rows = run_test_mapping(str(tmp_path), None)

    assert rows
    assert {row["side_effect_type"] for row in rows} == {
        str(SideEffectType.ReturnValue)
    }


@pytest.mark.parametrize(
    "assertion",
    [
        "self.assertRegex(text=build_items()[0], expected_regex='alpha')",
        "self.assertNotRegex(text=build_items()[0], expected_regex='beta')",
        "self.assertIsInstance(obj=build_items()[0], cls=str)",
        "self.assertNotIsInstance(obj=build_items()[0], cls=int)",
    ],
    ids=["regex", "not-regex", "is-instance", "not-is-instance"],
)
def test_unittest_auxiliary_keywords_observe_container_state(
    tmp_path: Path,
    assertion: str,
) -> None:
    """Regex and isinstance signatures resolve only their asserted operands."""
    _write_container_target(tmp_path / "containers.py")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_containers.py").write_text(
        "from containers import build_items\n\n\n"
        "def test_build_items():\n"
        f"    {assertion}\n"
    )

    rows = run_test_mapping(str(tmp_path), None)

    assert len(rows) == 1
    assert rows[0]["side_effect_type"] == str(SideEffectType.ContainerMutation)


@pytest.mark.parametrize(
    "assertion",
    [
        'assert self.assertIn("alpha", build_items())',
        'assert self.assertNotIn("beta", build_items())',
    ],
    ids=["assertIn", "assertNotIn"],
)
def test_bare_assert_method_form_membership_observes_container_state(
    tmp_path: Path,
    assertion: str,
) -> None:
    """A bare ``assert`` over a unittest membership call still qualifies."""
    _write_container_target(tmp_path / "containers.py")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_containers.py").write_text(
        "from containers import build_items\n\n\n"
        "def test_build_items():\n"
        f"    {assertion}\n"
    )

    rows = run_test_mapping(str(tmp_path), None)

    assert len(rows) == 1
    assert rows[0]["side_effect_type"] == str(SideEffectType.ContainerMutation)
