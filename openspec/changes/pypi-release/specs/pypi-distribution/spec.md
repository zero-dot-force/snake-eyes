## ADDED Requirements

### Requirement: Gaze analyzer entry-point alias

The package SHALL provide a `gaze-analyzer-python` console-script entry point in addition to the existing `snake-eyes` entry point, both pointing at `snake_eyes.__main__:main`, so Gaze tier-3 PATH auto-discovery can locate the Python analyzer.

#### Scenario: Alias and canonical entry point coexist
- **WHEN** `[project.scripts]` in `pyproject.toml` is inspected
- **THEN** it declares both `snake-eyes` and `gaze-analyzer-python`, both mapping to `snake_eyes.__main__:main`

#### Scenario: Alias launches the analyzer
- **WHEN** the `gaze-analyzer-python` console script is invoked with `--stdio`
- **THEN** it starts the same JSON-RPC server entry point as `snake-eyes --stdio`

### Requirement: PyPI package metadata

The package SHALL be publishable to PyPI with name `snake-eyes`, a version single-sourced from `src/snake_eyes/__init__.py` (resolving to `0.1.0`), `requires-python >=3.11`, license `Apache-2.0`, and a `readme` of `README.md`. The first published release SHALL be `v0.1.0`.

#### Scenario: Metadata is publish-ready
- **WHEN** the built distribution metadata is inspected
- **THEN** name is `snake-eyes`, version resolves to `0.1.0`, `requires-python` is `>=3.11`, license is `Apache-2.0`, and the long description is sourced from `README.md`

### Requirement: Trusted-publishing identity

The publish SHALL use PyPI trusted publishing (OIDC) so the `snake-eyes` PyPI project accepts uploads only from the `zero-dot-force/snake-eyes` `release.yml` workflow running behind a protected `release` environment, without any stored PyPI credential in the repository.

#### Scenario: OIDC audience is scoped
- **WHEN** trusted publishing is configured on the PyPI project
- **THEN** it permits the `zero-dot-force/snake-eyes` repository, the `release.yml` workflow, and the `release` environment, and rejects other identities
