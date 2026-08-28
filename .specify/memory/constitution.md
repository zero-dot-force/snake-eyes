<!--
SYNC IMPACT REPORT
Version change: 1.0.0 → 1.1.0
Amendment date: 2026-08-27
Feature: Constitution alignment with org patterns

Added sections:
- parent_constitution declaration (org v1.2.0)
- Principle V: Analysis Safety (new principle)
- Determinism MUST rules under Principle I
- Protocol version pin (v1.1.0) in upgraded Upstream Alignment
- Conflict Resolution clause in Governance
- Org supremacy clause in Governance
- This Sync Impact Report

Modified sections:
- Principle I: Protocol Fidelity (added determinism rules)
- Governance: Upstream Alignment (upgraded with version pin
  and conformance-suite requirement)

Unchanged sections:
- Principle II: Detection Accuracy
- Principle III: Python-Native Analysis
- Principle IV: Testability
- Development Workflow

Org alignment check: ALIGNED
- All five existing principles are compatible with org v1.2.0
- Principle V: Analysis Safety derives from org Principle V
  (Security by Default) adapted for static analysis context

Template compatibility: constitution v1 template

Version history:
- 1.0.0 (2026-05-17): Initial ratification. Four principles
  (Protocol Fidelity, Detection Accuracy, Python-Native
  Analysis, Testability). Upstream Alignment clause.
-->

# Snake Eyes Constitution

**parent_constitution**: unbound-force/unbound-force v1.2.0

## Core Principles

### I. Protocol Fidelity

Snake Eyes MUST implement Gaze's external analyzer protocol
precisely. The protocol is the contract between Gaze and
every language analyzer -- deviations break the platform.

- Every JSON-RPC response MUST conform to the analyzer
  protocol schema. Malformed responses are bugs, not edge
  cases.
- Response data MUST use Gaze's universal side effect
  taxonomy. Inventing local type names that diverge from
  the taxonomy is prohibited.
- When the protocol evolves (new methods, new fields),
  Snake Eyes MUST maintain backward compatibility with
  older Gaze versions through capability negotiation.
- Analysis of the same input tree with the same Snake Eyes
  version and the same protocol version MUST produce
  byte-identical JSON-RPC output. Responses MUST NOT
  contain timestamps, random values, hostnames, or any
  other environment-dependent data. JSON serialization
  MUST be deterministic (stable key ordering).

**Rationale**: Snake Eyes is not a standalone tool. It is
one half of a two-process system. If the protocol contract
is broken, nothing downstream (classification, scoring,
reports, TUI) can function correctly. Protocol fidelity is
the foundation on which all other value depends.

### II. Detection Accuracy

Snake Eyes MUST correctly identify all observable side
effects produced by Python functions. An observable side
effect includes return values, raised exceptions, mutations
to state, I/O operations, and any other externally
detectable change.

- Every reported side effect MUST correspond to a real
  observable effect in the analyzed code. False positives
  erode trust and MUST be treated as bugs.
- Every actual observable side effect that goes unreported
  is a false negative. False negatives MUST be tracked,
  measured, and driven toward zero.
- When analysis cannot determine an effect with confidence
  (dynamic dispatch, `eval`, metaclasses, etc.), the effect
  MUST be reported as ambiguous rather than omitted. Silent
  false negatives are worse than acknowledged uncertainty.
- Accuracy claims MUST be backed by automated regression
  tests covering known-good and known-bad detection
  scenarios.

**Rationale**: Gaze's entire value proposition depends on
accurate side effect data. Snake Eyes is the source of
truth for Python -- if it misses effects or fabricates them,
every metric Gaze computes is wrong.

### III. Python-Native Analysis

Snake Eyes MUST use Python's own parsing and analysis
infrastructure to understand Python code. Do not
reimplement Python semantics from scratch.

- Primary analysis MUST use the `ast` and `symtable`
  modules from Python's standard library. These are the
  same tools CPython's own compiler uses.
- Name resolution, type inference, and cross-module import
  resolution SHOULD use Astroid or equivalent established
  libraries rather than custom implementations.
- Analysis MUST NOT require users to annotate, restructure,
  or configure their Python code. Snake Eyes works with
  what exists.
- Python-specific idioms (decorators, descriptors, context
  managers, generators, monkey-patching) MUST be treated as
  first-class analysis targets, not edge cases to handle
  later.

**Rationale**: Python analyzing Python is a natural
advantage. The `ast` module produces the exact same abstract
syntax tree that CPython uses. Astroid provides battle-tested
inference. Reimplementing these capabilities would be slower,
less accurate, and harder to maintain.

### IV. Testability

Every function Snake Eyes analyzes, and every function
within Snake Eyes itself, MUST be testable in isolation
without requiring external services or shared mutable state.

- Test contracts MUST verify observable side effects (return
  values, detected effects, JSON-RPC responses), not
  implementation details.
- Coverage strategy (unit vs. integration, with targets)
  MUST be specified in the implementation plan for all new
  code.
- Missing coverage strategy in a spec or plan is a
  CRITICAL-severity finding and MUST be resolved before
  implementation begins.
- The JSON-RPC protocol is inherently testable: mock
  analyzers, canned request/response pairs, and protocol
  conformance suites MUST be used to verify correctness.

**Rationale**: Snake Eyes is a component of a test quality
tool. If its own tests are poorly structured, it undermines
the credibility of the entire system. Testability is also
a practical necessity: the JSON-RPC boundary provides a
clean seam for integration testing without requiring a
running Gaze process.

### V. Analysis Safety

Snake Eyes analyzes arbitrary Python codebases. Analyzed
source code is untrusted input and MUST be treated as such.

- Analysis MUST be strictly static. Snake Eyes MUST NOT
  execute, import, or otherwise run analyzed code. All
  inspection MUST use parse-level tools (`ast.parse`,
  `symtable.symtable`, Astroid's AST inference) that do
  not trigger code execution.
- Inputs MUST be validated and bounded. File paths MUST be
  resolved and checked for traversal. Resource limits
  (file size, AST depth, recursion budget) MUST prevent
  analyzed code from causing denial of service.
- Every dependency is attack surface. The default answer
  to adding a dependency is "do not add." Current
  dependencies (astroid, radon, coverage.py) are justified
  as established, maintained libraries that provide
  capabilities impractical to reimplement. New dependencies
  MUST be justified against this standard.
- CI actions MUST be pinned by commit SHA, not by mutable
  tag. Supply-chain integrity is a structural property,
  not a per-change review item.

**Rationale**: Snake Eyes runs in developer and CI
environments on codebases it does not control. A
compromised or malicious project must not achieve code
execution through the analyzer. Static-only analysis is
not a limitation -- it is the security boundary.

## Development Workflow

- **Spec-First Development**: All changes that modify
  production code, test code, or configuration MUST be
  preceded by a spec workflow (either the Speckit pipeline
  under `specs/` or the OpenSpec pipeline under
  `openspec/changes/`). The spec artifacts (proposal,
  design, tasks at minimum) MUST exist before
  implementation begins. Exempt from this requirement:
    - Constitution amendments (governed by the Governance
      section below)
    - Trivial fixes: typo corrections, comment-only
      changes, and single-line formatting fixes that do not
      alter behavior
    - Emergency hotfixes: critical bugs where the fix is a
      single well-understood correction (must be
      retroactively documented)
- **Branching**: All work MUST occur on feature branches.
  Direct commits to the main branch are prohibited except
  for trivial documentation fixes.
- **Code Review**: Every pull request MUST receive at least
  one approving review before merge.
- **Continuous Integration**: The CI pipeline MUST pass
  (build, lint, type check, tests) before a pull request is
  eligible for merge.
- **Releases**: Follow semantic versioning
  (MAJOR.MINOR.PATCH). Breaking changes to the JSON-RPC
  protocol require a MAJOR bump.
- **Commit Messages**: Use conventional commit format
  (`type: description`).

## Governance

This constitution extends the unbound-force org constitution
(v1.2.0). On matters where this document and the org
constitution conflict, the org constitution prevails and
this constitution MUST be amended to resolve the conflict.

This constitution is the highest-authority document for the
Snake Eyes project. All development practices, pull request
reviews, and architectural decisions MUST be consistent with
the principles defined above.

- **Amendments**: Any change to this constitution MUST be
  proposed via pull request, reviewed, and approved before
  merge. The amendment MUST include a migration plan if it
  alters or removes existing principles.
- **Versioning**: The constitution follows semantic
  versioning:
  - MAJOR: Principle removal or incompatible redefinition.
  - MINOR: New principle or materially expanded guidance.
  - PATCH: Clarifications, wording, or non-semantic
    refinements.
- **Compliance Review**: At each planning phase (spec,
  plan, tasks), the Constitution Check gate MUST verify
  that the proposed work aligns with all active principles.
- **Upstream Alignment**: This constitution is subordinate
  to Gaze's analyzer protocol specification. Snake Eyes
  implements **protocol v1.1.0** (defined at
  `unbound-force/gaze/docs/protocol.md`). Protocol
  conformance MUST be verified by an automated conformance
  suite (canned request/response pairs validated against
  the protocol schema). When Gaze bumps the protocol
  version, Snake Eyes MUST open an alignment issue within
  one release cycle.
- **Conflict Resolution**: When two principles appear to
  conflict in a specific scenario, the tradeoff MUST be
  explicitly documented in the relevant spec or plan. No
  principle has implicit priority over another; resolution
  is context-dependent and requires written justification.

**Version**: 1.1.0 | **Ratified**: 2026-05-17 | **Last Amended**: 2026-08-27
