## 1. Package metadata

- [x] 1.1 Add `gaze-analyzer-python = "snake_eyes.__main__:main"` to `[project.scripts]` in `pyproject.toml`, keeping the existing `snake-eyes` entry point
- [x] 1.2 Run `uv sync --locked` and verify the lockfile is unchanged (no new runtime dependency introduced)

## 2. Release workflow

- [x] 2.1 Create `.github/workflows/release.yml` with `name: release`, a `workflow_dispatch` trigger carrying a `tag` input (and a header comment describing the workflow's purpose)
- [x] 2.2 Add a `preflight` job that calls `complytime/org-infra/.github/workflows/reusable_release_preflight.yml` pinned to `0c784711926c9864f027ec565fd7c06a382d80f8`, with `allow_prerelease: true` and an explicit `ci_checks` JSON naming the `ci` workflow's `test (3.11)` and `test (3.12)` matrix check runs
- [x] 2.3 Add a `publish` job (`needs: preflight`) that checks out the preflight-created tag, runs `uv build` via `astral-sh/setup-uv` + `uv`, publishes with `pypa/gh-action-pypi-publish` in trusted-publishing mode, generates an SPDX SBOM with `anchore/sbom-action`, and attaches SBOM + sdist + wheel to the GitHub Release
- [x] 2.4 Pin every `uses:` action to a full commit SHA with a version comment and declare explicit `permissions` blocks (workflow level read-only; `preflight` and `publish` scoped to `contents: write` for tag/release creation, and `publish` additionally `id-token: write` for OIDC)
- [x] 2.5 Guard the `publish` job behind the protected `release` environment and set `id-token` permission so PyPI trusted publishing accepts the OIDC token

## 3. Documentation

- [x] 3.1 Replace the clone-only "Installation" section in `README.md` with `uv tool install snake-eyes` (plus `pipx`/`pip` fallbacks) and keep the `uv run snake-eyes --stdio` local-dev path
- [x] 3.2 Document the `gaze-analyzer-python` alias and note it for Gaze tier-3 PATH auto-discovery / `.gaze.yaml` configuration

## 4. Org-side setup (human / out-of-repo tasks)

- [x] 4.1 Confirm the PyPI project name `snake-eyes` is available under the `zero-dot-force` org (or agree a suffix if taken)
- [x] 4.2 Create the protected `release` environment on `zero-dot-force/snake-eyes` with required approvers
- [x] 4.3 Configure PyPI trusted publishing (OIDC) for the `zero-dot-force/snake-eyes` repository, `release.yml` workflow, and `release` environment

## 5. Verification and release

- [x] 5.1 Run the CI parity gates locally: `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`, `uv run mypy src/`, `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85`
- [x] 5.2 Build locally with `uv build` and verify the wheel/sdist contain both `snake-eyes` and `gaze-analyzer-python` entry points and correct metadata

<!-- spec-review: passed -->
<!-- code-review: passed -->
