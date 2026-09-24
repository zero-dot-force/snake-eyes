## Context

snake-eyes is a JSON-RPC analyzer backend that Gaze spawns as a subprocess. It has no user-facing CLI of its own, and today it is distributed only "from a clone" — the README explicitly says "not published to PyPI". Gaze (Go) ships a release pipeline driven by `complytime/org-infra` reusable workflows: a `workflow_dispatch` with a `tag` input triggers `reusable_release_preflight.yml` (semver + tag + CI gating) followed by a GoReleaser publish. The upstream org-infra has a fully generic preflight reusable workflow but no PyPI publish workflow — every existing `reusable_publish_*` targets an OCI registry.

This change publishes snake-eyes to PyPI via a release workflow that mirrors Gaze's preflight gating, so Gaze users can `uv tool install snake-eyes`. The work is constrained by the Snake Eyes constitution, the CI gates (`ruff`, `mypy --strict`, `pytest --cov-fail-under=85`, `uv sync --locked`, `ruff format --check`), and the org convention that all GitHub Actions are pinned to full commit SHAs with explicit `permissions` blocks.

Existing building blocks this design reuses without modification: the `snake-eyes = "snake_eyes.__main__:main"` entry point in `pyproject.toml`, the hatchling build backend (`[build-system]`, `[tool.hatch.version]` single-sourcing `0.1.0` from `src/snake_eyes/__init__.py`), and the `ci.yml` workflow (ruff / format / mypy / pytest gates on a Python 3.11/3.12 matrix).

## Goals / Non-Goals

**Goals:**
- Make snake-eyes installable from PyPI via `uv tool install snake-eyes` (with `pipx`/`pip` fallbacks).
- Ship a `workflow_dispatch` release pipeline gated by the same org-infra preflight as Gaze, with a `tag` input and `allow_prerelease: true`.
- Publish with PyPI trusted publishing (OIDC) — no stored PyPI token — and attach an SPDX SBOM plus the sdist/wheel to a GitHub Release.
- Add the `gaze-analyzer-python` entry-point alias so Gaze tier-3 PATH auto-discovery finds the analyzer, without removing `snake-eyes`.

**Non-Goals:**
- Changing any JSON-RPC method, detection rule, capability flag, or the `initialize` handshake.
- Modifying the protected CI gates in `ci.yml`; `release.yml` is purely additive.
- Contributing a generic `reusable_release_pypi.yml` upstream to org-infra now (deferred to a follow-up after v0.1.0 proves the inline workflow).
- Publishing any artifact to an OCI registry.
- Implementing semver/tag logic in-repo — that is owned by the org-infra preflight reusable workflow.

This change introduces no new Python code — only a CI workflow, `pyproject.toml` config, and documentation. Constitution IV's coverage-strategy requirement therefore does not apply to new code; verification is delegated to the build/CI/release checks in `tasks.md` section 5 (CI parity gates, wheel/sdist content verification, and the end-to-end `uv tool install` smoke test).

## Decisions

**D1 — Inline the PyPI publish in snake-eyes `release.yml` now; propose a generic reusable upstream later.** The publish job is authored directly in this repo's `release.yml`. org-infra has no `reusable_release_pypi.yml` yet, and inventing one here would violate the zero-waste mandate and set a precedent before the pattern is proven. Once v0.1.0 ships via this inline workflow, a follow-up proposes the generic reusable to `complytime/org-infra`. Alternative considered: author a reusable PyPI workflow in org-infra first — rejected because it front-loads cross-repo coordination and blocks the v0.1.0 release on infra work that is not yet validated.

**D2 — `workflow_dispatch` with a `tag` input; preflight creates the annotated tag.** The trigger matches Gaze exactly: a manual `workflow_dispatch` carrying a `tag` input, with `allow_prerelease: true`. The org-infra preflight job validates the semver and creates the annotated release tag and release draft; the publish job consumes that. No `on: push: tags:` trigger is used, so tag creation is centralized in preflight and cannot drift from validation. Alternative considered: trigger on `push` of a `v*` tag — rejected because it bypasses preflight's controlled tag creation and duplicates tag semantics.

**D3 — `preflight` job calls `complytime/org-infra/.github/workflows/reusable_release_preflight.yml` at pinned SHA `0c784711926c9864f027ec565fd7c06a382d80f8`.** The reusable is pinned to the exact SHA Gaze uses today, with an explicit `ci_checks` JSON that names the `ci` workflow's Python 3.11 and 3.12 matrix check runs so preflight only greenlights a release after the protected CI gates pass. The job carries a minimal, explicit `permissions` block granting `contents: write` so the reusable workflow can create the annotated tag and release draft, matching org convention. Alternative considered: pinning a tag/branch — rejected because mutable refs defeat supply-chain pinning.

**D4 — `publish` job (`needs: preflight`) runs `uv build` → PyPI trusted publishing → syft SBOM → GitHub Release.** The job runs on a fresh checkout of the preflight-created tag, builds sdist + wheel with `astral-sh/setup-uv` + `uv` (`uv build`), publishes with `pypa/gh-action-pypi-publish` configured for trusted publishing (OIDC — no token), generates an SPDX SBOM with `anchore/sbom-action`, and attaches the SBOM, sdist, and wheel to the GitHub Release that preflight drafted. All actions are SHA-pinned with version comments; the publish step runs inside a protected `release` environment (see D6) so PyPI OIDC only accepts this workflow's identity. Alternative considered: `pypa/gh-action-pypi-publish` with a stored API token — rejected in favor of trusted publishing (no long-lived secret in the repo).

**D5 — Add `gaze-analyzer-python = "snake_eyes.__main__:main"`; keep `snake-eyes`.** The alias exists so Gaze tier-3 discovery (`gaze-analyzer-*` on `PATH`) finds the analyzer automatically, while `snake-eyes` remains the canonical name for direct invocation and existing `.gaze.yaml` configs. Both entry points invoke the same `snake_eyes.__main__:main`. No new runtime dependency is introduced, so `uv.lock` is not expected to change beyond what `uv sync --locked` already pins.

**D6 — Org-side PyPI/environment setup is a tracked task, not a code deliverable.** The `publish` job requires three things that live outside this repo: a PyPI project named `snake-eyes` under the `zero-dot-force` org, a protected GitHub `release` environment on `zero-dot-force/snake-eyes`, and trusted-publishing (OIDC) configured on PyPI for the `release.yml` workflow behind that environment. These are captured as tasks for a human/org actor and documented in `tasks.md` with the exact wiring, but the code change is independent and can land first (the workflow simply cannot publish until the org step completes).

## Risks / Trade-offs

- PyPI project name `snake-eyes` may already be taken → mitigated by confirming ownership/availability as the first org-side task; if unavailable, a suffix (e.g. `snake-eyes-gaze`) is agreed before wiring trusted publishing.
- A misconfigured trusted-publishing identity would let an unrelated workflow publish to this project → mitigated by restricting the OIDC audience to the `release.yml` workflow within a protected `release` environment that requires approvers.
- org-infra reusable preflight drift across versions → mitigated by pinning the exact SHA and by Gaze already depending on the same reusable, so behavioral changes surface in Gaze first.
- `uv build`/hatchling producing an incomplete wheel (e.g. missing package data) → mitigated by verifying the built wheel/sdist contents (and the `gaze-analyzer-python` entry point) as part of the tasks, and by the SBOM covering the published artifacts.
- Manual `workflow_dispatch` means releases are human-initiated (no automatic tag trigger) → this is intentional (matches Gaze) and keeps tag creation under preflight control.
- The first release (`v0.1.0`) is unproven infrastructure → mitigated by the D1 follow-up to upstream the reusable after v0.1.0 succeeds.

## Migration Plan

The change is additive to distribution and docs; it does not touch runtime code or the protocol. Deploy steps: (1) add the `gaze-analyzer-python` entry point to `pyproject.toml` and confirm `uv sync --locked` still passes; (2) land `.github/workflows/release.yml`; (3) update `README.md` installation instructions; (4) complete the org-side setup (PyPI project + protected `release` environment + trusted publishing) as a human task; (5) trigger `workflow_dispatch` with `tag: v0.1.0` and verify the PyPI upload + GitHub Release + SBOM. Rollback is a straight revert of the additive files/edits; the `release` environment can be deleted or its protection restored. Note that a version already uploaded to PyPI cannot be overwritten or re-uploaded — a bad release must be yanked via the PyPI project (or superseded by an immediate patch version) rather than "reverted". There is no data migration or persisted state.

## Open Questions

None blocking — issue #23 fixes every decision. Deferred (not open questions): contributing a generic `reusable_release_pypi.yml` upstream to `complytime/org-infra` after v0.1.0, and any `analyze/stream` streaming work (unrelated to this change).
