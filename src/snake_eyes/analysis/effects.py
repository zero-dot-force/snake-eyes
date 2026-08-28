"""Side effect type taxonomy for snake-eyes.

Defines the canonical 48-value ``SideEffectType`` enum, the 5-tier ``Tier``
enum, and the ``TIER_MAP`` mapping each effect type to its tier.

Portions of this module are derived from gaze-py
(https://github.com/mpeter/gaze-py), Copyright Matt Peter, licensed under
Apache 2.0. The original 38-value taxonomy is extended with 10 additional
Python-specific effect types. Tier assignments are fixed by the Gaze
universal taxonomy and MUST NOT be configurable.
"""

from __future__ import annotations

import enum


class Tier(enum.Enum):
    """Priority tier for a side effect type.

    Tiers determine the detection requirement level (P0 = zero false
    negatives). The tier names and values are fixed by the Gaze universal
    taxonomy.
    """

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class SideEffectType(enum.StrEnum):
    """Canonical 48-value side effect type taxonomy.

    Values are retained verbatim from the Go gaze taxonomy to preserve JSON
    schema compatibility. Python-specific detection uses language-appropriate
    patterns, but the type string remains unchanged.
    """

    # --- P0: Must Detect (6) ---
    ReturnValue = "ReturnValue"
    ErrorReturn = "ErrorReturn"
    SentinelError = "SentinelError"
    ReceiverMutation = "ReceiverMutation"
    PointerArgMutation = "PointerArgMutation"
    ErrorSignal = "ErrorSignal"

    # --- P1: High Value (11) ---
    SliceMutation = "SliceMutation"
    MapMutation = "MapMutation"
    GlobalMutation = "GlobalMutation"
    WriterOutput = "WriterOutput"
    HTTPResponseWrite = "HTTPResponseWrite"
    ChannelSend = "ChannelSend"
    ChannelClose = "ChannelClose"
    DeferredReturnMutation = "DeferredReturnMutation"
    GeneratorYield = "GeneratorYield"
    ContainerMutation = "ContainerMutation"
    StreamOutput = "StreamOutput"

    # --- P2: Important (16) ---
    FileSystemWrite = "FileSystemWrite"
    FileSystemDelete = "FileSystemDelete"
    FileSystemMeta = "FileSystemMeta"
    DatabaseWrite = "DatabaseWrite"
    DatabaseTransaction = "DatabaseTransaction"
    GoroutineSpawn = "GoroutineSpawn"
    Panic = "Panic"
    CallbackInvocation = "CallbackInvocation"
    LogWrite = "LogWrite"
    ContextCancellation = "ContextCancellation"
    AsyncGeneratorYield = "AsyncGeneratorYield"
    MetaprogrammingMutation = "MetaprogrammingMutation"
    DescriptorEffect = "DescriptorEffect"
    ResourceManagement = "ResourceManagement"
    ImportSideEffect = "ImportSideEffect"
    MonkeyPatch = "MonkeyPatch"

    # --- P3: Nice to Have (9) ---
    StdoutWrite = "StdoutWrite"
    StderrWrite = "StderrWrite"
    EnvVarMutation = "EnvVarMutation"
    MutexOp = "MutexOp"
    WaitGroupOp = "WaitGroupOp"
    AtomicOp = "AtomicOp"
    TimeDependency = "TimeDependency"
    ProcessExit = "ProcessExit"
    RecoverBehavior = "RecoverBehavior"

    # --- P4: Exotic (6) ---
    ReflectionMutation = "ReflectionMutation"
    UnsafeMutation = "UnsafeMutation"
    CgoCall = "CgoCall"
    FinalizerRegistration = "FinalizerRegistration"
    SyncPoolOp = "SyncPoolOp"
    ClosureCaptureMutation = "ClosureCaptureMutation"


# Mapping from each SideEffectType to its Tier. This is the authoritative
# source for tier lookups -- do not duplicate inline.
TIER_MAP: dict[SideEffectType, Tier] = {
    # P0 -- 6 types
    SideEffectType.ReturnValue: Tier.P0,
    SideEffectType.ErrorReturn: Tier.P0,
    SideEffectType.SentinelError: Tier.P0,
    SideEffectType.ReceiverMutation: Tier.P0,
    SideEffectType.PointerArgMutation: Tier.P0,
    SideEffectType.ErrorSignal: Tier.P0,
    # P1 -- 11 types
    SideEffectType.SliceMutation: Tier.P1,
    SideEffectType.MapMutation: Tier.P1,
    SideEffectType.GlobalMutation: Tier.P1,
    SideEffectType.WriterOutput: Tier.P1,
    SideEffectType.HTTPResponseWrite: Tier.P1,
    SideEffectType.ChannelSend: Tier.P1,
    SideEffectType.ChannelClose: Tier.P1,
    SideEffectType.DeferredReturnMutation: Tier.P1,
    SideEffectType.GeneratorYield: Tier.P1,
    SideEffectType.ContainerMutation: Tier.P1,
    SideEffectType.StreamOutput: Tier.P1,
    # P2 -- 16 types
    SideEffectType.FileSystemWrite: Tier.P2,
    SideEffectType.FileSystemDelete: Tier.P2,
    SideEffectType.FileSystemMeta: Tier.P2,
    SideEffectType.DatabaseWrite: Tier.P2,
    SideEffectType.DatabaseTransaction: Tier.P2,
    SideEffectType.GoroutineSpawn: Tier.P2,
    SideEffectType.Panic: Tier.P2,
    SideEffectType.CallbackInvocation: Tier.P2,
    SideEffectType.LogWrite: Tier.P2,
    SideEffectType.ContextCancellation: Tier.P2,
    SideEffectType.AsyncGeneratorYield: Tier.P2,
    SideEffectType.MetaprogrammingMutation: Tier.P2,
    SideEffectType.DescriptorEffect: Tier.P2,
    SideEffectType.ResourceManagement: Tier.P2,
    SideEffectType.ImportSideEffect: Tier.P2,
    SideEffectType.MonkeyPatch: Tier.P2,
    # P3 -- 9 types
    SideEffectType.StdoutWrite: Tier.P3,
    SideEffectType.StderrWrite: Tier.P3,
    SideEffectType.EnvVarMutation: Tier.P3,
    SideEffectType.MutexOp: Tier.P3,
    SideEffectType.WaitGroupOp: Tier.P3,
    SideEffectType.AtomicOp: Tier.P3,
    SideEffectType.TimeDependency: Tier.P3,
    SideEffectType.ProcessExit: Tier.P3,
    SideEffectType.RecoverBehavior: Tier.P3,
    # P4 -- 6 types
    SideEffectType.ReflectionMutation: Tier.P4,
    SideEffectType.UnsafeMutation: Tier.P4,
    SideEffectType.CgoCall: Tier.P4,
    SideEffectType.FinalizerRegistration: Tier.P4,
    SideEffectType.SyncPoolOp: Tier.P4,
    SideEffectType.ClosureCaptureMutation: Tier.P4,
}
