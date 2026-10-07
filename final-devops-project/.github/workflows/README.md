# Workflows

GitHub only executes workflows from `.github/workflows/` at the **repository root**, so the real
files live there rather than here. This directory exists because the project structure in the brief
asks for it, and it points at them.

| Workflow | What it does |
| --- | --- |
| [`ci.yml`](../../../.github/workflows/ci.yml) | Lint, test on a Python matrix, build the image, upload artefacts. |
| [`cd.yml`](../../../.github/workflows/cd.yml) | After CI succeeds on `main`: publish to GHCR and roll the Deployment. |
| [`devsecops.yml`](../../../.github/workflows/devsecops.yml) | The full pipeline with SAST, SCA, secret scanning, image scanning and the security gate. |

Executed locally with [act](https://github.com/nektos/act); see
[Session 16](../../../cicd-github-actions/README.md) and
[Session 17](../../../devsecops/README.md).
