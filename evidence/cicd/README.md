# CI/CD execution evidence

**Vibhuti Bhatnagar · 24BCS10288 · vibhuti.24bcs10288@sst.scaler.com**

Transcripts from [`scripts/run-cicd-lab.sh`](../../scripts/run-cicd-lab.sh), captured on
7 October 2026. The workflow files executed are the real ones at
[`.github/workflows/`](../../.github/workflows/); act runs them inside a container that mirrors a
GitHub-hosted `ubuntu-latest` runner.

| Transcript | What to inspect |
| --- | --- |
| [16-workflow-structure.txt](16-workflow-structure.txt) | Every workflow parsed, with the job order act derived from each `needs:`. |
| [16-ci-pipeline.txt](16-ci-pipeline.txt) | The lint job, and the test job on Python 3.11 and 3.12 with coverage. |
| [16-image-build.txt](16-image-build.txt) | The image build, the smoke test against a running container, and the saved image artifact. |

One step cannot complete locally: `actions/upload-artifact` needs GitHub's artifact service, and
act's substitute is unreachable from containers on this machine. The transcript explains why and
shows the files the step would have uploaded. [Session 16](../../cicd-github-actions/README.md)
has the detail.
