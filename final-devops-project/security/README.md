# Security controls in the final project

| Control | Where it is enforced | What it stops |
| --- | --- | --- |
| SAST (Bandit, Semgrep) | [`devsecops.yml`](../../.github/workflows/devsecops.yml) | Insecure code patterns reaching `main`. |
| SCA (pip-audit) | same workflow | Known-vulnerable dependency versions. |
| Secret scanning (Gitleaks, full history) | same workflow | Credentials committed now or in the past. |
| Image scanning (Trivy) | same workflow | Vulnerable OS and language packages in the published image. |
| Security gate | same workflow | Any of the above reaching the registry or the cluster. |
| Non-root, read-only root filesystem, dropped capabilities | [`04-deployment.yaml`](../kubernetes/04-deployment.yaml) | Container escape and tampering after a compromise. |
| Pod Security Admission (`restricted`) | [`00-namespace.yaml`](../kubernetes/00-namespace.yaml) | A privileged Pod being admitted at all. |
| Default-deny NetworkPolicy | [`08-networkpolicy.yaml`](../kubernetes/08-networkpolicy.yaml) | Lateral movement from a neighbouring namespace. |
| Secret supplied out of band | [`02-secret.yaml`](../kubernetes/02-secret.yaml) | The API token living in Git. |

The scanner configuration itself is shared with Session 17 and lives in
[`devsecops/config/`](../../devsecops/config/).

## Threats this project does not address

Being explicit about the gaps matters more than a longer table:

- **Image signing and provenance.** Nothing verifies that the image the cluster
  pulls is the one the pipeline built. Cosign plus an admission policy would
  close this.
- **Runtime detection.** The controls above are all build-time or
  admission-time. Nothing watches a running container for unexpected
  behaviour.
- **Secret rotation.** The token is generated once. There is no rotation
  schedule and no external secret store behind it.
