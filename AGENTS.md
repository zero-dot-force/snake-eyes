# AGENTS.md

## Project Overview

Snake Eyes is a Python code analyzer that implements the
[Gaze external analyzer protocol](https://github.com/unbound-force/gaze/issues/95).
It detects observable side effects in Python functions and
reports them to Gaze's universal scoring engine via JSON-RPC
2.0 over stdin/stdout.

Snake Eyes does not have its own CLI for end users. Gaze is
the CLI -- Snake Eyes is invoked as a subprocess by Gaze
when analyzing Python projects.

- **Language**: Python 3.11+
- **Package**: `snake-eyes`
- **License**: Apache 2.0
- **Parent project**: [Gaze](https://github.com/unbound-force/gaze) (unbound-force)
- **Organization**: [zero-dot-force](https://github.com/zero-dot-force) (labs incubator for unbound-force)

## Constitution (Highest Authority)

The Snake Eyes constitution
(`.specify/memory/constitution.md`) is the highest-authority
document for this project. It extends the unbound-force org
constitution (v1.2.0) and pins Gaze protocol v1.1.0.
Constitution violations are CRITICAL severity and
non-negotiable.

**Five principles:**

1. **Protocol Fidelity** -- implement the Gaze analyzer
   protocol precisely; deterministic output; deviations are
   bugs
2. **Detection Accuracy** -- correctly identify all
   observable side effects; ambiguity over omission; false
   positives and false negatives are bugs
3. **Python-Native Analysis** -- use Python's own parsing
   infrastructure (ast, symtable, astroid); do not
   reimplement Python semantics
4. **Testability** -- every function testable in isolation;
   coverage strategy required in every spec; protocol
   conformance suites required
5. **Analysis Safety** -- analyzed source is untrusted
   input; static analysis only; never execute analyzed
   code; dependency necessity justified

## Architecture

Snake Eyes is a JSON-RPC server that Gaze spawns as a
subprocess. The division of responsibility:

**Gaze (Go core) owns:**
- CLI, TUI, and report formatting
- Universal side effect taxonomy
- Classification scoring (contractual vs incidental)
- CRAP and GazeCRAP computation
- AI report pipeline
- Analyzer lifecycle management

**Snake Eyes (this project) owns:**
- Python-specific side effect detection
- Python-specific classification signals
- Coverage data parsing (coverage.py)
- Cyclomatic complexity calculation (lifted gaze-py McCabe; no radon)
- Test-to-assertion mapping (pytest)
- File and project discovery

## Technology Stack

- **Parsing**: Python `ast` module (stdlib) for structural
  AST analysis
- **Scope analysis**: Python `symtable` module (stdlib) for
  global/nonlocal detection
- **Inference**: [Astroid](https://github.com/pylint-dev/astroid) `>=3.0,<4`
  (shipped) for caller-count inference in `analysis/inference.py`
- **Complexity**: lifted gaze-py McCabe implementation; no radon dependency
- **Coverage**: [coverage.py](https://github.com/nedbat/coveragepy) `>=7.0,<8`
  (shipped runtime dependency) for parsing `.coverage` data files
- **Project management**: [uv](https://docs.astral.sh/uv/)
- **Testing**: [pytest](https://docs.pytest.org/)

## Project Structure

```
snake-eyes/
├── src/snake_eyes/
│   ├── __init__.py
│   ├── __main__.py          # Entry point (snake-eyes --stdio)
│   ├── server.py            # JSON-RPC server (stdin/stdout)
│   ├── protocol.py          # Request/response types
│   ├── discovery.py         # File discovery (os.walk)
│   ├── coverage.py          # Coverage data parser (coverage.json / .coverage)
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── _shared.py       # Shared helpers (safe file reader, package derivation)
│   │   ├── effects.py       # 48-type SideEffectType taxonomy
│   │   ├── models.py        # Effect / FunctionRecord data models
│   │   ├── detector.py      # Python side-effect detector (analyze method)
│   │   ├── complexity.py    # McCabe cyclomatic complexity (complexity method)
│   │   └── inference.py     # astroid caller-count inference (classify_signals)
│   └── signals/
│       ├── __init__.py
│       ├── _routing.py      # effect-type → category routing (reconstructed from gaze-py)
│       ├── _types.py        # SignalResult value type
│       ├── interface.py     # interface source extractor (reconstructed from gaze-py)
│       ├── visibility.py    # visibility source extractor (reconstructed from gaze-py)
│       ├── caller.py        # caller_count source extractor (reconstructed from gaze-py)
│       ├── naming.py        # naming_convention source extractor (reconstructed from gaze-py)
│       ├── docstring.py     # docstring source extractor (reconstructed from gaze-py)
│       └── adapter.py       # extract_signals fan-out (classify_signals method)
├── tests/
├── .github/workflows/       # CI: ruff, mypy, pytest gates
├── pyproject.toml
├── uv.lock
├── README.md
├── LICENSE
└── NOTICE
```
Delivered in issue #4: `detector.py`, `complexity.py`, `coverage.py`, `_shared.py`, and the `analyze`, `complexity`, and `coverage` JSON-RPC methods.
Delivered in issue #5: the `signals/` extractors, `analysis/inference.py` (astroid caller-count inference), and the `classify_signals` JSON-RPC method.

## Shell Commands

Commands are derived from `.github/workflows/ci.yml`.
Do not rely on memory -- check the workflow file for the
current gates.

```bash
# Install dependencies (CI uses --locked)
uv sync --locked

# Linting
uv run ruff check src/ tests/

# Format check (CI runs --check, not auto-format)
uv run ruff format --check src/ tests/

# Type checking
uv run mypy src/

# Run tests with coverage (85% is the protected gate)
uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85

# Run snake-eyes in stdio mode (for testing with gaze)
uv run snake-eyes --stdio
```

**Protected gates** (agents MUST NOT lower these):
- `--cov-fail-under=85` -- minimum coverage percentage
- `ruff format --check` -- formatting must pass, not auto-fix
- `uv sync --locked` -- lockfile integrity

## Core Mission

- **Protocol fidelity**: Snake Eyes implements Gaze's
  analyzer protocol precisely. The protocol is the contract
  -- deviations are bugs.
- **Python-native analysis**: Use Python's own parsing
  infrastructure (ast, symtable, astroid) to understand
  Python code natively. Do not reimplement Python semantics
  from scratch.
- **Platform pattern**: Snake Eyes establishes the pattern
  for future language analyzers (TypeScript, Rust, etc.).
  Decisions here set precedent.

## Behavioral Constraints

- **Zero-Waste Mandate**: No orphaned code, unused
  dependencies, or feature bloat.
- **Neighborhood Rule**: Changes must be audited for
  impacts on the Gaze protocol contract.
- **Intent Drift Detection**: Implementation must stay
  aligned with the analyzer protocol spec and Gaze's
  universal taxonomy.

### Gatekeeping Value Protection

Agents MUST NOT modify values that serve as quality or
governance gates to make an implementation pass:

1. **Coverage thresholds** -- minimum coverage percentages,
   coverage ratchets
2. **Severity definitions** -- CRITICAL/HIGH/MEDIUM/LOW
   boundaries
3. **Convention pack rule classifications** -- MUST/SHOULD/MAY
   designations (downgrading MUST to SHOULD is prohibited)
4. **CI flags and linter configuration** -- ruff rules,
   mypy strictness, pytest markers
5. **Constitution MUST rules** -- any MUST rule in
   `.specify/memory/constitution.md`

When an implementation cannot meet a gate, the agent MUST
stop, report which gate is blocking and why, and let the
human decide.

### Workflow Phase Boundaries

Agents MUST NOT cross workflow phase boundaries:

- **Specify/Clarify/Plan/Tasks** phases: spec artifacts
  ONLY. No source code, test, or config changes.
- **Implement** phase: source code changes allowed, guided
  by spec artifacts.
- **Review** phase: findings and minor fixes only. No new
  features.

## Technical Guardrails

- **Protocol compliance**: All JSON-RPC responses MUST
  conform to the analyzer protocol schema. Invalid
  responses are bugs.
- **Graceful degradation**: When analysis cannot determine
  an effect with confidence (dynamic dispatch, eval, etc.),
  report it as ambiguous rather than omitting it. Silent
  false negatives violate the constitution.
- **CI Parity Gate**: Before marking any task complete,
  agents MUST run the same checks CI runs. Derive commands
  from workflow files, not memory.

## Spec Organization

Snake Eyes uses two spec pipelines. Choose based on scope:

| Criterion | Speckit (`specs/NNN-*/`) | OpenSpec (`openspec/changes/`) |
|---|---|---|
| **Scope** | Strategic: ≥3 tasks or cross-cutting | Tactical: 1–2 tasks, focused |
| **Artifacts** | spec, plan, tasks, checklists | proposal, design, tasks |
| **When to use** | New analysis capabilities, protocol changes, architecture | Bug fixes, small features, docs |
| **Example** | `specs/001-jsonrpc-prototype/` | `openspec/changes/fix-parse-error/` |

**Ordering constraints**: spec artifacts MUST be committed
before implementation begins. Implementation commits MUST
NOT be in the same commit as spec changes.

**Task Completion Bookkeeping**: When completing a task
from a tasks file, mark the checkbox `- [x]` immediately
-- not in a batch at the end.

## Workflow Gates

### Constitution Check

Before implementation, verify alignment with all five
constitution principles. The check MUST name each principle
and give a PASS/FAIL verdict:

1. Protocol Fidelity
2. Detection Accuracy
3. Python-Native Analysis
4. Testability
5. Analysis Safety

### Review Council Gate

Run `uf.review-council` before creating a PR. All
reviewers MUST APPROVE before the PR is eligible for
merge. Exempt: constitution amendments, docs-only changes,
emergency hotfixes.

### CI Parity Gate

Before marking any task complete, agents MUST run the same
checks CI runs. Derive commands from
`.github/workflows/ci.yml`, not from memory.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
under `specs/` or `openspec/changes/`.
<!-- SPECKIT END -->

## Convention Packs

This repository uses convention packs scaffolded by
unbound-force. Agents MUST read the applicable pack(s)
before writing or reviewing code.

- `.opencode/uf/packs/default.md`
- `.opencode/uf/packs/default-custom.md`
- `.opencode/uf/packs/severity.md`
- `.opencode/uf/packs/content.md`
- `.opencode/uf/packs/content-custom.md`
- `.opencode/uf/packs/python.md`
- `.opencode/uf/packs/python-custom.md`
- `.opencode/uf/packs/ci.md`
- `.opencode/uf/packs/ci-custom.md`
