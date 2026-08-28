## ADDED Requirements

### Requirement: DiscoveryResult dataclass
The system SHALL define a frozen `DiscoveryResult` dataclass with fields `source_files: tuple[str, ...]` and `test_files: tuple[str, ...]`.

#### Scenario: DiscoveryResult is frozen
- **WHEN** an attempt is made to assign to a field of a `DiscoveryResult` instance
- **THEN** a `FrozenInstanceError` (or equivalent) is raised

### Requirement: discover only Python files
The `discover(root_path: str, patterns: list[str] | None = None)` function SHALL return only `.py` files, excluding `.pyi` stubs, and SHALL express returned paths relative to `root_path` with POSIX separators.

#### Scenario: Non-Python files excluded
- **WHEN** `discover` runs over a tree containing `a.py`, `b.txt`, and `c.pyi`
- **THEN** only `a.py` appears in the results

#### Scenario: Paths are relative and POSIX
- **WHEN** `discover` runs over a tree rooted at a directory containing `src/foo.py`
- **THEN** the result path is `src/foo.py` (no leading `./`, forward slashes)

### Requirement: patterns follow Gaze ./... convention
The `discover` function SHALL treat `patterns` of `None`, `[]`, `["./..."]`, or `["..."]` as "walk the whole tree". A relative directory pattern (e.g. `src` or `src/`) SHALL walk that subtree. A glob pattern (e.g. `**/*.py`) SHALL be applied relative to root. Go's `./pkg/...` package semantics SHALL be reduced to "directory prefix + recursive".

#### Scenario: Default patterns walk whole tree
- **WHEN** `discover` is called with `patterns=None` over a tree with files in `src/` and `tests/`
- **THEN** files from both subtrees are returned

#### Scenario: Directory pattern restricts to subtree
- **WHEN** `discover` is called with `patterns=["src"]`
- **THEN** only files under `src/` are returned

#### Scenario: Glob pattern matches relative to root
- **WHEN** `discover` is called with `patterns=["**/*.py"]`
- **THEN** all `.py` files under root are returned

### Requirement: test file classification
The `discover` function SHALL classify a file as a test file if its filename starts with `test_`, or ends with `_test.py`, or any of its path components is `tests` or `test`. A file SHALL NOT appear in both lists; a file matching test rules goes to `test_files` only.

#### Scenario: test_ prefix classified as test
- **WHEN** a tree contains `test_foo.py` at the root
- **THEN** `test_foo.py` appears in `test_files` and not `source_files`

#### Scenario: _test suffix classified as test
- **WHEN** a tree contains `foo_test.py`
- **THEN** `foo_test.py` appears in `test_files`

#### Scenario: tests directory component classified as test
- **WHEN** a tree contains `tests/test_foo.py`
- **THEN** `tests/test_foo.py` appears in `test_files`

#### Scenario: No file in both lists
- **WHEN** `discover` runs over any tree
- **THEN** `source_files` and `test_files` are disjoint

### Requirement: directory exclusion
The `discover` function SHALL not descend into a directory whose name is any of `.venv`, `venv`, `env`, `.env`, `__pycache__`, `.git`, `.hg`, `.svn`, `dist`, `build`, `.tox`, `.nox`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`, `node_modules`, `.eggs`, or any name ending in `.egg-info`.

#### Scenario: .venv excluded
- **WHEN** a tree contains `.venv/lib/python3.12/site.py`
- **THEN** `site.py` does not appear in the results

#### Scenario: __pycache__ excluded
- **WHEN** a tree contains `__pycache__/x.py`
- **THEN** `x.py` does not appear in the results

### Requirement: symlink handling
The `discover` function SHALL not follow directory symlinks, and SHALL skip file symlinks entirely (do not follow them).

#### Scenario: directory symlink not followed
- **WHEN** a tree contains a directory symlink pointing back to an ancestor
- **THEN** `discover` terminates and does not recurse into the symlink

#### Scenario: file symlink skipped
- **WHEN** a tree contains a regular file `a.py` and a file symlink `link.py` pointing to `a.py`
- **THEN** only `a.py` appears in the results and `link.py` is not followed

### Requirement: missing root_path raises FileNotFoundError
The `discover` function SHALL raise `FileNotFoundError` with the path in the message when `root_path` is missing or is not a directory.

#### Scenario: missing root raises
- **WHEN** `discover` is called with a nonexistent `root_path`
- **THEN** a `FileNotFoundError` whose message contains the path is raised

#### Scenario: non-directory root raises
- **WHEN** `discover` is called with a `root_path` that is a regular file
- **THEN** a `FileNotFoundError` is raised

### Requirement: empty project returns empty result
The `discover` function SHALL return `DiscoveryResult((), ())` for an empty project without error.

#### Scenario: empty project
- **WHEN** `discover` runs over an empty directory
- **THEN** both `source_files` and `test_files` are empty tuples

### Requirement: deterministic output ordering
The `discover` function SHALL return `source_files` and `test_files` in deterministic sorted order, each list ordered lexicographically by POSIX path, so that discovering the same tree twice yields byte-identical results regardless of filesystem traversal order.

#### Scenario: results are sorted lexicographically
- **WHEN** `discover` runs over a tree containing `b.py`, `a.py`, and `tests/c_test.py`
- **THEN** `source_files` is `("a.py", "b.py")` and `test_files` is `("tests/c_test.py",)`, each in lexicographic order
