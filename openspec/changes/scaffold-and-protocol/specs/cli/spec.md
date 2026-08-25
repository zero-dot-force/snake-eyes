## ADDED Requirements

### Requirement: Package scaffold and entry point
The system SHALL provide a `snake-eyes` package installable via `uv sync`, with `pyproject.toml` declaring name `snake-eyes`, version `0.1.0`, `requires-python >=3.11`, `license Apache-2.0`, `src/` layout, and a `snake-eyes` script entry pointing to `snake_eyes.__main__:main`. `src/snake_eyes/__init__.py` SHALL expose `__version__ = "0.1.0"`.

#### Scenario: Package metadata is correct
- **WHEN** `pyproject.toml` is inspected
- **THEN** name is `snake-eyes`, version is `0.1.0`, `requires-python` is `>=3.11`, and license is `Apache-2.0`

#### Scenario: Version constant is exposed
- **WHEN** `snake_eyes.__version__` is read
- **THEN** it equals `"0.1.0"`

### Requirement: stdio flag parsing
The `__main__` module SHALL parse argv and support only the `--stdio` flag. With `--stdio` present, it SHALL start the JSON-RPC server on stdin/stdout and block. With `--stdio` absent, it SHALL print the one-line usage `snake-eyes --stdio` to stderr and exit with code 2. No other CLI behavior is supported. `main` SHALL accept an optional argv list and optional injected `stdin`/`stdout`/`stderr` streams (defaulting to `sys.*`) so tests can drive the entry point in-process.

#### Scenario: stdio starts the server
- **WHEN** `main` is invoked with `--stdio`
- **THEN** the server loop is started and blocks on stdin

#### Scenario: missing flag prints usage and exits 2
- **WHEN** `main` is invoked without `--stdio`
- **THEN** the usage line is written to stderr, nothing is written to stdout, and the process exits with code 2

### Requirement: NOTICE attribution placeholder
The system SHALL include a `NOTICE` file recording zero-dot-force copyright and the attribution statement for code originally developed in gaze-py by Matt Peter under Apache License 2.0. The file SHALL contain the exact text:

```
snake-eyes
Copyright 2026 zero-dot-force

This product includes software originally developed in gaze-py
(https://github.com/mpeter/gaze-py) by Matt Peter, licensed under
Apache License 2.0. Copyright headers on lifted files are preserved.
```

#### Scenario: NOTICE present
- **WHEN** the repository root is inspected
- **THEN** a `NOTICE` file exists containing the exact gaze-py attribution text above
