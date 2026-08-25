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
- Cyclomatic complexity calculation (radon)
- Test-to-assertion mapping (pytest)
- File and project discovery

## Technology Stack

- **Parsing**: Python `ast` module (stdlib) for structural
  AST analysis
- **Scope analysis**: Python `symtable` module (stdlib) for
  global/nonlocal detection
- **Inference**: [Astroid](https://github.com/pylint-dev/astroid)
  for name resolution, type inference, cross-module imports
- **Complexity**: [radon](https://github.com/rubik/radon)
  for cyclomatic complexity
- **Coverage**: [coverage.py](https://github.com/nedbat/coveragepy)
  for parsing coverage data
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
│   ├── discovery.py         # File discovery (source + tests)
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── detector.py      # Side effect detection
│   │   ├── inference.py     # Name/type resolution (astroid)
│   │   ├── effects.py       # Effect type definitions
│   │   └── patterns.py      # Known I/O and mutation patterns
│   ├── complexity.py        # Cyclomatic complexity (radon)
│   └── coverage.py          # coverage.py data parsing
├── tests/
├── pyproject.toml
└── .gaze.yaml
```

## Shell Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=snake_eyes --cov-report=term-missing

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/ tests/

# Formatting
uv run ruff format src/ tests/

# Run snake-eyes in stdio mode (for testing with gaze)
uv run snake-eyes --stdio
```

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

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
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
