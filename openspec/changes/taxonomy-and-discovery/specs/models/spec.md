## ADDED Requirements

### Requirement: Effect dataclass
The system SHALL define a frozen `Effect` dataclass with fields `type: str` (the canonical `SideEffectType` string value, e.g. `"ReturnValue"`), `description: str` (required human-readable text), `location: str | None = None` (as `"file.py:25:5"` relative to root), `target: str | None = None` (attribute/parameter/exception name), and `detail: dict[str, Any] | None = None` (opaque Python-specific metadata).

#### Scenario: Effect is frozen
- **WHEN** an attempt is made to assign a new value to a field of an `Effect` instance
- **THEN** a `FrozenInstanceError` (or equivalent) is raised

#### Scenario: type holds the canonical string
- **WHEN** an `Effect` is constructed with `type="ReturnValue"`
- **THEN** `effect.type` equals the exact string `"ReturnValue"`

### Requirement: FunctionRecord dataclass
The system SHALL define a frozen `FunctionRecord` dataclass with fields `name: str`, `package: str` (dotted module path, e.g. `"snake_eyes.server"`), `file: str` (path relative to `root_path` with POSIX slashes), `line: int` (1-based def line), and `side_effects: tuple[Effect, ...] = ()`. It SHALL NOT include gaze-py-only fields (`visibility`, `is_test`, `is_generator`, `complexity`, `id`).

#### Scenario: FunctionRecord is frozen
- **WHEN** an attempt is made to assign a new value to a field of a `FunctionRecord` instance
- **THEN** a `FrozenInstanceError` (or equivalent) is raised

#### Scenario: side_effects defaults to empty tuple
- **WHEN** a `FunctionRecord` is constructed without `side_effects`
- **THEN** `record.side_effects` equals `()`

#### Scenario: gaze-py-only fields are absent
- **WHEN** `dataclasses.fields(FunctionRecord)` is inspected
- **THEN** none of `visibility`, `is_test`, `is_generator`, `complexity`, or `id` are present as field names

### Requirement: function_record_to_dict serialization
The system SHALL define `function_record_to_dict(record: FunctionRecord) -> dict[str, Any]` returning a dict with keys `name`, `package`, `file`, `line`, and `side_effects`. Each `Effect` in `side_effects` SHALL serialize with keys `type` and `description`, plus `location`, `target`, and `detail` only when non-`None`.

#### Scenario: None optionals are omitted
- **WHEN** a record whose effects have `location`, `target`, and `detail` all `None` is serialized
- **THEN** the resulting dict contains no `location`, `target`, or `detail` keys

#### Scenario: Present optionals are included
- **WHEN** a record whose effect has `location="file.py:25:5"`, `target="x"`, and `detail={"k": "v"}` is serialized
- **THEN** the effect dict contains `location` equal to `"file.py:25:5"`, `target` equal to `"x"`, and `detail` equal to `{"k": "v"}`

#### Scenario: side_effects serializes as a list
- **WHEN** a record with two effects is serialized
- **THEN** the `side_effects` value is a list of length 2

#### Scenario: type serializes as a canonical string
- **WHEN** a record with a `ReturnValue` effect is serialized
- **THEN** the effect's `type` key equals the string `"ReturnValue"`
