## Why

snake-eyes cannot be installed from a package manager today — the README says "From a clone (not published to PyPI)". Gaze spawns snake-eyes as a subprocess and, at tier 3, auto-discovers analyzers on `PATH` by the `gaze-analyzer-*` name convention, so a clone-only install leaves Gaze users with no supported way to obtain the Python analyzer. Publishing to PyPI (with an org-infra-gated release pipeline mirroring Gaze's) makes `uv tool install snake-eyes` the supported path. Implements #23.

## What Changes

- Add `.github/workflows/release.yml`: a `workflow_dispatch` release pipeline with a `preflight` job (`complytime/org-infra` `reusable_release_preflight.yml`, pinned SHA `0c784711926c9864f027ec565fd7c06a382d80f8`, `allow_prerelease: true`, explicit `ci_checks` JSON for the py3.11/3.12 `ci` matrix) and a `publish` job (`needs: preflight`) that runs `uv build`, publishes to PyPI via `pypa/gh-action-pypi-publish` (trusted publishing / OIDC), generates an SPDX SBOM via `anchore/sbom-action`, and hosts the SBOM + sdist/wheel on a GitHub Release.
- Modify `pyproject.toml`: add `gaze-analyzer-python = "snake_eyes.__main__:main"` to `[project.scripts]` so Gaze tier-3 PATH discovery finds the analyzer (keeping the existing `snake-eyes` entry point).
- Modify `README.md`: replace the clone-only installation instructions with `uv tool install snake-eyes` (plus `pipx`/`pip` fallbacks) and note the `gaze-analyzer-python` alias for `.gaze.yaml`/auto-discovery.
- Out-of-repo (org/human, tracked as tasks but not deliverable in this repo): create the PyPI project `snake-eyes` under `zero-dot-force` and configure trusted publishing (OIDC) for the `zero-dot-force/snake-eyes` `release.yml` workflow behind a protected `release` environment.

No changes to the JSON-RPC protocol, detection logic, or protected CI gates (`ci.yml` ruff / format / mypy / pytest `--cov-fail-under=85` stays as-is).

## Capabilities

### New Capabilities

- `release-pipeline`: the org-infra-gated PyPI release workflow — `workflow_dispatch` with a `tag` input, the `preflight` job (org-infra reusable preflight with explicit CI checks), the `publish` job (`uv build` → PyPI trusted publishing → syft SBOM → GitHub Release), and its permissions/environment contract.
- `pypi-distribution`: what makes snake-eyes pip-installable — the `snake-eyes` and `gaze-analyzer-python` console-script entry points, PyPI package metadata (name/version/license/requires-python), and the trusted-publishing (OIDC) + release-environment requirements for the publish job.

### Modified Capabilities

None — no JSON-RPC method or detection behavior changes. `openspec/specs/` holds no archived capabilities yet.

## Impact

- New files: `.github/workflows/release.yml`.
- Modified files: `pyproject.toml` (new `gaze-analyzer-python` entry point); `README.md` (installation section); `uv.lock` regenerated only if the script entry changes the lock (no new runtime dependency, so likely unchanged).
- Dependencies: none added. Publishing uses GitHub Actions (`astral-sh/uv` for `uv build`, `pypa/gh-action-pypi-publish`, `anchore/sbom-action`) and the existing `complytime/org-infra` reusable preflight; no Python dependency changes.
- Systems: PyPI (trusted publishing / OIDC) and GitHub Releases. Requires an org-side setup step (PyPI project + protected `release` environment) that is a human/org task, not a code deliverable.
- CI parity: no change to protected gates; `release.yml` is additive and triggered manually (`workflow_dispatch`).
