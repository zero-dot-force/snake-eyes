## ADDED Requirements

### Requirement: Manual release trigger with tag input

The system SHALL provide a `.github/workflows/release.yml` workflow triggered by `workflow_dispatch` with a `tag` input, and the preflight gate SHALL allow prerelease tags (`allow_prerelease: true`). The workflow SHALL NOT trigger on tag push events.

#### Scenario: Release is dispatched with a tag
- **WHEN** a maintainer triggers `workflow_dispatch` and supplies a `tag` value
- **THEN** the release workflow starts with the preflight job using that tag

#### Scenario: Prerelease tags are accepted
- **WHEN** the supplied `tag` is a prerelease (e.g. `v0.1.0-rc1`)
- **THEN** preflight accepts it because `allow_prerelease` is `true`

### Requirement: Org-infra preflight gate

The `preflight` job SHALL call `complytime/org-infra/.github/workflows/reusable_release_preflight.yml` pinned to the full commit SHA `0c784711926c9864f027ec565fd7c06a382d80f8`, passing an explicit `ci_checks` value that names the `ci` workflow's Python 3.11 and 3.12 test matrix check runs. The job SHALL declare an explicit `permissions` block granting `contents: write` so the reusable workflow can create the annotated tag and release draft; it SHALL NOT create tags or releases outside the reusable workflow.

#### Scenario: Preflight runs before publish
- **WHEN** the release workflow is dispatched
- **THEN** the `preflight` job runs the pinned org-infra reusable and the `publish` job declares `needs: preflight`

#### Scenario: CI gates are required for release
- **WHEN** preflight evaluates the release
- **THEN** it blocks unless the `ci` workflow's Python 3.11 and 3.12 test runs (as listed in `ci_checks`) have passed

### Requirement: Publish via trusted publishing with SBOM

The `publish` job SHALL build the package with `uv build`, publish to PyPI using `pypa/gh-action-pypi-publish` in trusted-publishing (OIDC) mode without any stored PyPI token, generate an SPDX SBOM using `anchore/sbom-action`, and attach the SBOM, sdist, and wheel to a GitHub Release. Every action referenced in the workflow SHALL be pinned to a full commit SHA with a version comment.

#### Scenario: Successful publish produces a release
- **WHEN** preflight completes successfully
- **THEN** the publish job builds the sdist and wheel, uploads them to PyPI via OIDC, and attaches them plus the SPDX SBOM to the GitHub Release

#### Scenario: No stored PyPI secret
- **WHEN** the workflow is inspected
- **THEN** no PyPI username/password or API-token secret is referenced by the publish step

### Requirement: Supply-chain pinning and permissions

The release workflow SHALL pin every `uses:` action to a full commit SHA and SHALL declare an explicit `permissions` block on every job and at the workflow level.

#### Scenario: Actions are pinned
- **WHEN** the workflow file is inspected
- **THEN** every `uses:` reference resolves to a full commit SHA (not a mutable tag or branch)
