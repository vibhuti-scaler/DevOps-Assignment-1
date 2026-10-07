# Session 17: Complete CI/CD & DevSecOps

- **Name:** Vibhuti Bhatnagar
- **Roll no:** 24BCS10288
- **Email:** vibhuti.24bcs10288@sst.scaler.com
- **Batch:** B

The [Session 16 application](../cicd-github-actions/README.md) with security stages added to its
delivery path. Everything here was executed: the pipeline first **blocked a release** on three real
findings, each was fixed, and the second run passed the gate. Both runs are kept:

| Run | Transcripts | Result |
| --- | --- | --- |
| First | [evidence/devsecops/blocked-run/](../evidence/devsecops/blocked-run/) | `GATE: blocked` — three findings |
| After the fixes | [evidence/devsecops/](../evidence/devsecops/) | `GATE: passed` |

```bash
bash devsecops/scripts/run-security-scan.sh
```

The script runs each scanner from a pinned container image, so the result does not depend on what
happens to be installed locally, and it mirrors
[.github/workflows/devsecops.yml](../.github/workflows/devsecops.yml) stage for stage.

## The pipeline

```text
Code
 ↓
Build ──▶ Unit test (85% coverage gate)
 ↓
SAST (Bandit + Semgrep)   ┐
SCA (pip-audit)           ├── run in parallel; all three must pass
Secret scan (Gitleaks)    ┘
 ↓
Docker build
 ↓
Container image scan (Trivy: filesystem + image)
 ↓
Security gate  ──── blocked ───▶ pipeline stops, nothing is published
 ↓ passed
Push to the registry (GHCR)
 ↓
Deploy to Kubernetes
```

The ordering is deliberate. Unit tests run before any scanner, because a scanner takes minutes and a
broken build should fail in seconds. The three source-level scans run in parallel, because they are
independent. The image is built once and scanned before it is pushed — scanning after the push means
the vulnerable image already exists where someone can pull it.

## What each stage is for

| Stage | Tool | What it finds | What it cannot find |
| --- | --- | --- | --- |
| **SAST** | Bandit, Semgrep | Insecure patterns in code you wrote: `shell=True`, a hardcoded key, `debug=True`. | Anything that depends on runtime values. |
| **SCA** | pip-audit | Known CVEs in declared dependencies. | A vulnerability nobody has disclosed yet. |
| **Secret scanning** | Gitleaks | Credential-shaped strings in the working tree *and in the history*. | A secret that was never committed in a recognisable form. |
| **Image scanning** | Trivy | OS and language package vulnerabilities in the built image, plus misconfiguration in manifests. | Logic flaws in the application. |
| **Security gate** | the pipeline itself | Nothing. It decides what the findings mean. | — |

The gate is the part that matters. Scanners that report into a dashboard nobody reads change
nothing; a gate that fails the build is what makes a finding expensive to ignore.

## The findings, and the fixes

### 1. SCA — Flask 3.1.0 had two known vulnerabilities

```text
Name  Version ID              Fix Versions
----- ------- --------------- ------------
flask 3.1.0   PYSEC-2026-1377 3.1.1
flask 3.1.0   PYSEC-2026-2151 3.1.3
Found 2 known vulnerabilities in 1 package
```

**Fix:** `Flask==3.1.3` in `requirements.txt`, in both the Session 16 and the final-project
application. Re-scan: `No known vulnerabilities found`.

This is why the SCA stage earns its runtime. Nothing in the source changed, nothing failed a test,
and the dependency became vulnerable while the code sat still.

### 2. SAST — a development entrypoint binding every interface

```text
>> Issue: [B104:hardcoded_bind_all_interfaces] Possible binding to all interfaces.
   Severity: Medium   Confidence: Medium
   Location: cicd-github-actions/app/main.py:55:17
55	    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
```

**Fix:** that `__main__` block is the Flask development server, not how the container runs — the
image runs gunicorn, which binds `0.0.0.0` from its own command line, where it belongs. The
entrypoint now reads `HOST` and defaults to `127.0.0.1`.

A finding worth looking at twice: the naive reaction is "the container needs 0.0.0.0, so suppress
it". The correct reaction is that the *container* needs it and this code path does not.

### 3. Trivy — the Kubernetes manifest ran with the default security context

```text
Failures: 3 (HIGH: 3, CRITICAL: 0)

AVD-KSV-0014 (HIGH): Container 'api' of Deployment 'task-api' should set
  'securityContext.readOnlyRootFilesystem' to true
AVD-KSV-0118 (HIGH): container task-api in task-api namespace is using the default security context
AVD-KSV-0118 (HIGH): deployment task-api in task-api namespace is using the default security context,
  which allows root privileges
```

**Fix:** `cicd-github-actions/kubernetes/deployment.yaml` now carries `runAsNonRoot`,
`runAsUser: 10001`, `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false`,
`readOnlyRootFilesystem: true`, `capabilities.drop: ["ALL"]` and a writable `/tmp` emptyDir.

Trivy's filesystem scanner reads manifests as well as dependency files, which is how a Kubernetes
misconfiguration gets caught by the same stage that checks the image.

### Result after the fixes

```text
PASS: unit tests and the 85% coverage gate
PASS: Bandit static analysis of the application source
PASS: pip-audit against the declared dependencies
PASS: Gitleaks over the repository history
PASS: Gitleaks over the working tree
PASS: Trivy filesystem scan (dependencies, secrets, misconfiguration)
PASS: Trivy image scan, failing on fixable HIGH or CRITICAL findings
GATE: passed - the image may be pushed and deployed.
```

## Proving the scanners actually work

A clean report means nothing unless the scanner would have spoken up. Two stages therefore run a
**negative control** against a throwaway fixture created at runtime and deleted immediately.

**SAST control** — a file with the three defects the
[repository rules](config/semgrep-rules.yaml) describe: `debug=True`, a literal `secret_key`, and
`subprocess.run(..., shell=True)`. Bandit reports them:

```text
>> Issue: [B201:flask_debug_true] A Flask app appears to be run with debug=True …
   Severity: High   Confidence: Medium
Total issues (by severity): Low: 4, Medium: 0, High: 1
```

**Secret-scanning control** — a file containing an AWS key pair and a GitHub token, generated at
random on each run:

```text
leaks found: 2
```

The randomness is not decoration. The well-known `AKIAIOSFODNN7EXAMPLE` key from the AWS
documentation is on Gitleaks' own allowlist, so testing with it would produce a confident green that
proves nothing.

## Configuration

| File | What it does |
| --- | --- |
| [`config/.gitleaks.toml`](config/.gitleaks.toml) | Extends the default rules and allowlists only placeholders — `REPLACE_WITH_*`, `<your-…>`, `.env.example`, the evidence transcripts. |
| [`config/bandit.yaml`](config/bandit.yaml) | Excludes `tests/`, where `assert` is intentional and B101 would bury the real findings. |
| [`config/semgrep-rules.yaml`](config/semgrep-rules.yaml) | Three repository-specific rules, run alongside Semgrep's `p/python`, `p/flask` and `p/secrets` registry packs. |
| [`config/trivyignore.txt`](config/trivyignore.txt) | Empty, deliberately. Every entry would need a CVE, a justification and a review date. |

An empty ignore file is the honest state of this project. The format in the comment exists so that a
future exception carries an expiry rather than quietly becoming permanent.

## Kubernetes deployment

[`kubernetes/`](kubernetes/) is the hardened version of the Session 16 manifests:

- **`namespace.yaml`** sets `pod-security.kubernetes.io/enforce: restricted`. A Pod that does not
  meet the profile is rejected at admission — it never reaches the scheduler.
- **`deployment.yaml`** runs as UID 10001, non-root, read-only root filesystem, all capabilities
  dropped, `RuntimeDefault` seccomp, and `automountServiceAccountToken: false` because the
  application never calls the API server.
- **`networkpolicy.yaml`** denies all ingress and egress, then allows exactly two things: port 8000
  from the ingress controller and a labelled client, and DNS to CoreDNS.

Pod Security Admission is not theoretical here. In the final project, enforcement rejected a load
generator that had no security context at all — the ReplicaSet could not create a single Pod and
said so in its events. The fix was to make the throwaway Pod comply; the point is that the namespace
refused, rather than warning.

## Container registry

The workflow publishes to GitHub Container Registry using `secrets.GITHUB_TOKEN`, which GitHub mints
per run and expires at the end of it, so there is no long-lived registry password anywhere in this
repository. The push job is guarded by `if: github.event_name == 'push'`: a pull request, including
one from a fork, runs every scan and publishes nothing.

Publishing is not demonstrated locally — it would mean putting a real registry credential on this
machine, which is the thing the design avoids. What is demonstrated is that the gate stops the
pipeline before it: the first run exited non-zero at the gate and never reached the push stage.

## Base image choice, measured

```text
task-api:security-scan (debian 13.7)   Total: 0 (HIGH: 0, CRITICAL: 0)
python:3.12            (debian 13.7)   Total: 0 (HIGH: 0, CRITICAL: 0)
```

Both are clean today, which is the useful result to record rather than a convenient one. The slim
base still wins on the metric that matters over time: fewer packages means fewer future CVEs and a
smaller image, and the multi-stage build keeps the compiler and the pip cache out of the runtime
layer entirely.

## What this pipeline does not cover

- **Image signing and provenance.** Nothing verifies that the image the cluster pulls is the one
  this pipeline built. Cosign plus an admission policy would close that gap.
- **Runtime security.** Every control here is build-time or admission-time. Nothing watches a
  running container.
- **DAST.** The application is never scanned while running.
- **Secret rotation.** Tokens are generated once; there is no rotation schedule behind them.

These are listed because a security section that claims completeness is the least trustworthy kind.
