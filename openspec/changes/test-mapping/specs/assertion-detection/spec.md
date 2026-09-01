## ADDED Requirements

### Requirement: One mapping row per assertion

For each paired test function, the detector SHALL collect every assertion in the test body and produce one mapping row per assertion. Rows from the same test share the same `target_function` and `target_package` but carry distinct `assertion_location` values.

#### Scenario: Test with multiple assertions yields multiple rows
- **WHEN** a paired test function contains three assertions
- **THEN** three mapping rows are produced, all with the same target but different `assertion_location` values

### Requirement: Assertion node identification

The detector SHALL identify assertion nodes within a paired test's body as: every `ast.Assert` statement; every call whose callee is a unittest `assert*` method (e.g. `self.assertEqual(...)`) or a pytest/bare `raises`/`warns` callable; and every `with` item using `pytest.raises(...)`, `raises(...)`, or `self.assertRaises(...)`. Traversal SHALL descend into nested `with`, `for`, `if`, `while`, and `try` blocks of the test body, but SHALL NOT descend into nested function or class definitions. A `raises`/`warns`/`assertRaises` call that appears as the context expression of a `with` item SHALL be counted once — as the `with` item — and SHALL NOT additionally be counted as a bare call. Each identified node SHALL produce exactly one mapping row.

#### Scenario: A pytest.raises context manager counts as one assertion
- **WHEN** a paired test body contains `with pytest.raises(ValueError): ...`
- **THEN** exactly one assertion row is produced with `assertion_type` `error_check`

### Requirement: Assertion type classification

Each assertion SHALL be classified into exactly one `assertion_type` from the closed set `equality | error_check | membership | identity | comparison | generic`, supporting both pytest bare-`assert` expressions and unittest `assert*` methods, according to a fixed classification table that is exhaustive over recognized pytest and unittest forms. Any recognized assertion form not matched by a more specific rule SHALL be classified as `generic`.

#### Scenario: Equality assertions
- **WHEN** an assertion is `assert x == y`, `assertEqual(...)`, `assertEquals(...)`, `assertAlmostEqual(...)`, `assertDictEqual(...)`, `assertListEqual(...)`, `assertMultiLineEqual(...)`, `assertCountEqual(...)`, or `assertSequenceEqual(...)`
- **THEN** its `assertion_type` is `equality`

#### Scenario: Comparison assertions
- **WHEN** an assertion is `assert x != y`, `assert x < y` / `>` / `<=` / `>=`, `assertNotEqual(...)`, `assertNotAlmostEqual(...)`, or an `assertLess*`/`assertGreater*` method
- **THEN** its `assertion_type` is `comparison`

#### Scenario: Identity assertions
- **WHEN** an assertion is `assert x is y`, `assert x is not y`, `assertIs(...)`, `assertIsNot(...)`, `assertIsNone(...)`, or `assertIsNotNone(...)`
- **THEN** its `assertion_type` is `identity`

#### Scenario: Membership assertions
- **WHEN** an assertion is `assert x in y`, `assert x not in y`, `assertIn(...)`, or `assertNotIn(...)`
- **THEN** its `assertion_type` is `membership`

#### Scenario: Error-check assertions
- **WHEN** an assertion uses `pytest.raises(...)`, `unittest`'s `assertRaises(...)`, `assertRaisesRegex(...)`, `assertRaisesRegexp(...)`, `pytest.warns(...)`, or a bare `raises(...)`
- **THEN** its `assertion_type` is `error_check`

#### Scenario: Generic fallback
- **WHEN** an assertion is any other `assert`, `assertTrue(...)`, or `assertFalse(...)`
- **THEN** its `assertion_type` is `generic`

### Requirement: Assertion location format

Each assertion row SHALL record `assertion_location` as `path:line`, where `path` is relative to `root_path` and `line` is the assertion's source line; no column component is required.

#### Scenario: Location is root-relative path plus line
- **WHEN** an assertion occurs at line 10 of `tests/test_ops.py`
- **THEN** `assertion_location` is `tests/test_ops.py:10`
