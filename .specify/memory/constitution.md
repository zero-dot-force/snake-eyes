# Snake Eyes Constitution

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
  to Gaze's analyzer protocol specification. If a
  constitutional principle conflicts with the protocol
  spec, the protocol spec takes precedence and the
  constitution MUST be amended.

**Version**: 1.0.0 | **Ratified**: 2026-05-17 | **Last Amended**: 2026-05-17
