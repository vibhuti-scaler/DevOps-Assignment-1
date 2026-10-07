# DevSecOps execution evidence

**Vibhuti Bhatnagar · 24BCS10288 · vibhuti.24bcs10288@sst.scaler.com**

Transcripts from [`devsecops/scripts/run-security-scan.sh`](../../devsecops/scripts/run-security-scan.sh),
captured on 7 October 2026. Every scanner runs from a pinned container image. The last line of
`06-security-gate.txt` is the gate's verdict.

| Transcript | What to inspect |
| --- | --- |
| [01-unit-tests.txt](01-unit-tests.txt) | pytest with the 85% coverage threshold. |
| [02-sast.txt](02-sast.txt) | Bandit over the application, then the same scanner against a file with three planted defects. |
| [03-sca.txt](03-sca.txt) | pip-audit against the declared dependencies. |
| [04-secret-scanning.txt](04-secret-scanning.txt) | Gitleaks over the repository history, then over the working tree, then against a file containing a randomly generated credential. |
| [05-image-scan.txt](05-image-scan.txt) | The image build, Trivy filesystem scan, Trivy image scan, and `python:3.12` for comparison. |
| [06-security-gate.txt](06-security-gate.txt) | The verdict. |

## The run that blocked

[`blocked-run/`](blocked-run/) is the first execution, kept deliberately. It failed three stages and
stopped the pipeline before the registry push:

| Stage | Finding |
| --- | --- |
| SCA | `flask 3.1.0` — PYSEC-2026-1377 and PYSEC-2026-2151, fixed in 3.1.3. |
| SAST | Bandit B104: the development entrypoint bound `0.0.0.0`. |
| Image scan | Trivy AVD-KSV-0014 and AVD-KSV-0118 on `cicd-github-actions/kubernetes/deployment.yaml`. |

All three were fixed; the transcripts above are the run afterwards.
[Session 17](../../devsecops/README.md) has the detail.
