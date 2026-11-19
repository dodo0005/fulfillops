# Supply chain

## Vulnerability policy (enforced in `build-scan-sbom`)

| Finding | Effect | Why |
| --- | --- | --- |
| CRITICAL or HIGH **with a fix available** (`--ignore-unfixed`) | **Blocks the PR** (Trivy exit code 1, required check fails, merge button disabled) | We can act on it: bump the base image or dependency |
| CRITICAL/HIGH with no fix yet, MEDIUM, LOW, UNKNOWN | **Informational**: second Trivy run, `exit-code 0`, full JSON report uploaded as artifact `trivy-<sha>` | Blocking on unfixable findings would freeze delivery without making anything safer; they are reviewed, not ignored |

Red-to-green proof of this gate: `docs/evidence/E13-ci-red-green.md`.

## SBOM

Syft (via `anchore/sbom-action`) generates a CycloneDX JSON SBOM of the exact image that was scanned. It is uploaded on every run as artifact `sbom-<commit-sha>`.

## Immutable artifact

- `publish` runs only on pushes to `main`, only after `lint`, `unit-tests`, `integration-and-contract` and `build-scan-sbom` pass.
- It pushes the **same image that was scanned** (passed between jobs as a tar artifact, not rebuilt) to `ghcr.io/dodo0005/fulfillops:<full-commit-sha>`. Tags are never reused.
- It is the only job with `packages: write`; every other job has `contents: read`.
- Promotion to the cluster = a PR changing `newTag` in `infra/k8s/kustomization.yaml` (`scripts/promote.sh <sha>`).
- Final digest: `docs/evidence/E15-image-digest.txt`.

## Pinned actions (full commit SHA, version in comment)

| Action | Version | SHA |
| --- | --- | --- |
| actions/checkout | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| astral-sh/setup-uv | v10.3.2 | `07a047e608db84b3d8c06cd9a7c7dcc9c355c18e` |
| actions/upload-artifact | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |
| actions/download-artifact | v8.0.2 | `9000827ccba6bdab643e8b6fd33ac0654aef8333` |
| docker/setup-buildx-action | v4.4.1 | `f87e5991a6d7451dcb8d9637bfbc97413f497069` |
| docker/build-push-action | v7.4.0 | `c3c9e263c25d99ce0380d002d59b67737d91b0dc` |
| docker/login-action | v4.7.0 | `81c6f93d4bc991e510b342a00b419b3bb4efc5c6` |
| aquasecurity/trivy-action | v0.36.0 (Trivy v0.76.1) | `ed142fd0673e97e23eac54620cfb913e5ce36c25` |
| anchore/sbom-action | v0.24.3 | `66cbf4bc1f1c0d2edc94016e65bc221b6bb0ad6c` |

Why SHAs and not tags: a tag can be moved to malicious code after we reviewed it (this happened to `trivy-action` tags in March 2026). A SHA cannot change. Every pinned release was at least two weeks old when chosen.

## Pinned images

| Image | Tag | Digest |
| --- | --- | --- |
| Python base (builder + runtime) | `python:3.12.16-slim-trixie` | TODO: `docker buildx imagetools inspect python:3.12.16-slim-trixie --format '{{.Manifest.Digest}}'` |
| uv (builder only) | `ghcr.io/astral-sh/uv:0.13.5` | TODO |
| Postgres | `postgres:16.15-alpine` | TODO |
| Redis | `redis:7.4.12-alpine` | TODO |
| Argo CD install manifest | `v3.5.6` | — |
