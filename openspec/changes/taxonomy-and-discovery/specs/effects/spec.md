## ADDED Requirements

### Requirement: 48-value SideEffectType enum
The system SHALL define `SideEffectType` as an `enum.StrEnum` with exactly 48 members whose names and string values are the canonical Gaze type strings. The members SHALL be, by tier: P0 `ReturnValue`, `ErrorReturn`, `SentinelError`, `ReceiverMutation`, `PointerArgMutation`, `ErrorSignal`; P1 `SliceMutation`, `MapMutation`, `GlobalMutation`, `WriterOutput`, `HTTPResponseWrite`, `ChannelSend`, `ChannelClose`, `DeferredReturnMutation`, `GeneratorYield`, `ContainerMutation`, `StreamOutput`; P2 `FileSystemWrite`, `FileSystemDelete`, `FileSystemMeta`, `DatabaseWrite`, `DatabaseTransaction`, `GoroutineSpawn`, `Panic`, `CallbackInvocation`, `LogWrite`, `ContextCancellation`, `AsyncGeneratorYield`, `MetaprogrammingMutation`, `DescriptorEffect`, `ResourceManagement`, `ImportSideEffect`, `MonkeyPatch`; P3 `StdoutWrite`, `StderrWrite`, `EnvVarMutation`, `MutexOp`, `WaitGroupOp`, `AtomicOp`, `TimeDependency`, `ProcessExit`, `RecoverBehavior`; P4 `ReflectionMutation`, `UnsafeMutation`, `CgoCall`, `FinalizerRegistration`, `SyncPoolOp`, `ClosureCaptureMutation`.

#### Scenario: Enum has exactly 48 members
- **WHEN** `len(SideEffectType)` is computed
- **THEN** the result is 48

#### Scenario: Existing P0 members are retained
- **WHEN** the P0 tier members are inspected
- **THEN** `ReturnValue`, `ErrorReturn`, `SentinelError`, `ReceiverMutation`, and `PointerArgMutation` are present as members

#### Scenario: The 10 added members are present
- **WHEN** the enum is inspected for the added types
- **THEN** `ErrorSignal`, `GeneratorYield`, `ContainerMutation`, `StreamOutput`, `AsyncGeneratorYield`, `MetaprogrammingMutation`, `DescriptorEffect`, `ResourceManagement`, `ImportSideEffect`, and `MonkeyPatch` are present as members

#### Scenario: Member values are canonical strings
- **WHEN** a member such as `SideEffectType.ReturnValue` is serialized
- **THEN** its value is the exact string `"ReturnValue"` with no language-neutral alias

### Requirement: Tier enum
The system SHALL define a `Tier` enum with exactly five members `P0`, `P1`, `P2`, `P3`, `P4`, each with a string value equal to its name.

#### Scenario: Five tiers exist
- **WHEN** `len(Tier)` is computed
- **THEN** the result is 5

#### Scenario: Tier values match names
- **WHEN** `Tier.P0.value` is evaluated
- **THEN** the result is `"P0"`

### Requirement: TIER_MAP completeness and correctness
The system SHALL define `TIER_MAP: dict[SideEffectType, Tier]` mapping every `SideEffectType` member to exactly one `Tier`. Every member SHALL have an entry, and the 10 added members SHALL map to their specified tiers: `ErrorSignal` → P0; `GeneratorYield`, `ContainerMutation`, `StreamOutput` → P1; `AsyncGeneratorYield`, `MetaprogrammingMutation`, `DescriptorEffect`, `ResourceManagement`, `ImportSideEffect`, `MonkeyPatch` → P2.

#### Scenario: Every member has a tier entry
- **WHEN** `TIER_MAP` is compared against all `SideEffectType` members
- **THEN** every member is a key in `TIER_MAP`

#### Scenario: Added members map to specified tiers
- **WHEN** the tier of each added member is looked up in `TIER_MAP`
- **THEN** `ErrorSignal` is P0, `GeneratorYield`/`ContainerMutation`/`StreamOutput` are P1, and `AsyncGeneratorYield`/`MetaprogrammingMutation`/`DescriptorEffect`/`ResourceManagement`/`ImportSideEffect`/`MonkeyPatch` are P2

#### Scenario: Existing tier assignments are unchanged
- **WHEN** the tier of each of the original 38 members is looked up in `TIER_MAP`
- **THEN** the assignment matches the lifted gaze-py mapping (e.g. `ReturnValue` → P0, `FileSystemWrite` → P2, `StdoutWrite` → P3, `ReflectionMutation` → P4)

### Requirement: Provenance header on lifted file
The system SHALL retain provenance attribution on `effects.py` crediting gaze-py (Matt Peter) under Apache 2.0, since the taxonomy is lifted from gaze-py.

#### Scenario: Attribution is present
- **WHEN** `src/snake_eyes/analysis/effects.py` is read
- **THEN** the file's header or module docstring references gaze-py and the Apache 2.0 license
