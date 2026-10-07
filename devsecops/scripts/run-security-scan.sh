#!/usr/bin/env bash
# Runs the same security stages as .github/workflows/devsecops.yml, locally,
# through pinned container images so the result does not depend on what happens
# to be installed on this laptop. Every transcript lands in
# evidence/devsecops/ and the exit code is the security gate's verdict.
set -uo pipefail

repo_dir="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo_dir"
app_dir="cicd-github-actions"
out="evidence/devsecops"
mkdir -p "$out"

BANDIT_IMAGE="python:3.12-slim"
GITLEAKS_IMAGE="zricethezav/gitleaks:v8.21.2"
TRIVY_IMAGE="aquasec/trivy:0.58.1"
IMAGE_TAG="task-api:security-scan"

stage=0
failed=0

log() { printf '%s\n' "$*" | tee -a "$transcript"; }

run() {
  log ""
  log "\$ $*"
  "$@" 2>&1 | tee -a "$transcript"
  return "${PIPESTATUS[0]}"
}

begin() {
  stage=$((stage + 1))
  transcript="$out/0${stage}-$1.txt"
  : > "$transcript"
  log "Vibhuti Bhatnagar | 24BCS10288 | vibhuti.24bcs10288@sst.scaler.com"
  log "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $1"
}

record() {
  if [ "$1" -eq 0 ]; then
    log ""
    log "PASS: $2"
  else
    log ""
    log "FAIL: $2 (exit $1)"
    failed=$((failed + 1))
  fi
}

# ---------------------------------------------------------------- unit tests
begin "unit-tests"
docker run --rm -v "$repo_dir/$app_dir":/src -w /src "$BANDIT_IMAGE" sh -c \
  'pip install --quiet -r requirements-dev.txt && pytest --cov=app --cov-report=term --cov-fail-under=85' \
  2>&1 | tee -a "$transcript"
record "${PIPESTATUS[0]}" "unit tests and the 85% coverage gate"

# ---------------------------------------------------------------------- SAST
begin "sast"
docker run --rm -v "$repo_dir":/src -w /src "$BANDIT_IMAGE" sh -c \
  "pip install --quiet bandit==1.8.0 && bandit -c devsecops/config/bandit.yaml -r $app_dir/app --severity-level medium --confidence-level medium" \
  2>&1 | tee -a "$transcript"
record "${PIPESTATUS[0]}" "Bandit static analysis of the application source"

# Prove the rules actually fire: scan a throwaway file with the three defects
# the repository rules describe, then confirm the real source is clean.
# The planted key is generated at run time, so this script does not itself
# contain a credential-shaped literal for the secret scanner below to find.
fixture="$(mktemp -d)"
{
  printf 'import subprocess\n\nfrom flask import Flask\n\napp = Flask(__name__)\n'
  printf 'app.secret_key = "%s"\n\n\n' "$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)"
  printf '@app.get("/run")\ndef run_command():\n'
  printf '    return subprocess.run("ls /tmp", shell=True, capture_output=True).stdout\n\n\n'
  printf 'app.run(debug=True)\n'
} > "$fixture/insecure_example.py"
log ""
log "Negative control: the same scanner against a file with known defects"
docker run --rm -v "$fixture":/src -w /src "$BANDIT_IMAGE" sh -c \
  'pip install --quiet bandit==1.8.0 && bandit -r insecure_example.py --severity-level medium --confidence-level medium' \
  2>&1 | tee -a "$transcript"
control=${PIPESTATUS[0]}
rm -rf "$fixture"
if [ "$control" -ne 0 ]; then
  log ""
  log "PASS: the scanner reports the planted defects, so a clean run means something"
else
  log ""
  log "FAIL: the scanner missed the planted defects"
  failed=$((failed + 1))
fi

# ----------------------------------------------------------------------- SCA
begin "sca"
docker run --rm -v "$repo_dir/$app_dir":/src -w /src "$BANDIT_IMAGE" sh -c \
  'pip install --quiet pip-audit==2.7.3 && pip-audit -r requirements.txt --strict' \
  2>&1 | tee -a "$transcript"
record "${PIPESTATUS[0]}" "pip-audit against the declared dependencies"

# ------------------------------------------------------------- secret scanning
begin "secret-scanning"
log ""
log "History first: a secret that was committed and later removed is still in the"
log "repository, so the whole history is scanned, not only the current files."
docker run --rm -v "$repo_dir":/repo -w /repo "$GITLEAKS_IMAGE" \
  detect --source=/repo --config=/repo/devsecops/config/.gitleaks.toml \
  --redact --no-banner --verbose 2>&1 | tee -a "$transcript"
record "${PIPESTATUS[0]}" "Gitleaks over the repository history"
log ""
log "Then the working tree, which also covers files that are not committed yet:"
docker run --rm -v "$repo_dir":/repo -w /repo "$GITLEAKS_IMAGE" \
  detect --source=/repo --no-git --config=/repo/devsecops/config/.gitleaks.toml \
  --redact --no-banner --verbose 2>&1 | tee -a "$transcript"
record "${PIPESTATUS[0]}" "Gitleaks over the working tree"

# The credential below is generated at random on every run. The well-known
# AWS documentation example key is deliberately not used: it is on Gitleaks'
# own allowlist, so testing with it would prove nothing.
fixture="$(mktemp -d)"
{
  printf 'AWS_ACCESS_KEY_ID=AKIA%s\n' "$(LC_ALL=C tr -dc 'A-Z0-9' </dev/urandom | head -c 16)"
  printf 'AWS_SECRET_ACCESS_KEY=%s\n' "$(LC_ALL=C tr -dc 'A-Za-z0-9/+' </dev/urandom | head -c 40)"
  printf 'GITHUB_TOKEN=ghp_%s\n' "$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 36)"
} > "$fixture/leak.env"
log ""
log "Negative control: a throwaway file containing credential-shaped strings"
docker run --rm -v "$fixture":/repo -w /repo "$GITLEAKS_IMAGE" \
  detect --source=/repo --no-git --redact --no-banner 2>&1 | tee -a "$transcript"
control=${PIPESTATUS[0]}
rm -rf "$fixture"
if [ "$control" -ne 0 ]; then
  log ""
  log "PASS: the planted credential is detected, so the clean repository result is meaningful"
else
  log ""
  log "FAIL: the planted credential was not detected"
  failed=$((failed + 1))
fi

# ------------------------------------------------- image build and image scan
begin "image-scan"
run docker build -t "$IMAGE_TAG" "$app_dir"
record "$?" "application image built"

docker run --rm -v "$repo_dir":/src -w /src "$TRIVY_IMAGE" \
  fs --scanners vuln,secret,misconfig --severity HIGH,CRITICAL --exit-code 1 \
  --ignorefile devsecops/config/trivyignore.txt --no-progress "$app_dir" \
  2>&1 | tee -a "$transcript"
record "${PIPESTATUS[0]}" "Trivy filesystem scan (dependencies, secrets, misconfiguration)"

docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$repo_dir":/src -w /src -v "$HOME/.cache/trivy":/root/.cache/trivy "$TRIVY_IMAGE" \
  image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 \
  --ignorefile devsecops/config/trivyignore.txt --no-progress "$IMAGE_TAG" \
  2>&1 | tee -a "$transcript"
record "${PIPESTATUS[0]}" "Trivy image scan, failing on fixable HIGH or CRITICAL findings"

docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$HOME/.cache/trivy":/root/.cache/trivy "$TRIVY_IMAGE" \
  image --severity HIGH,CRITICAL --ignore-unfixed --no-progress --format table \
  python:3.12 2>&1 | tail -40 | tee -a "$transcript"
log ""
log "Context: the unslimmed python:3.12 base image above is shown for comparison."

# ------------------------------------------------------------- security gate
begin "security-gate"
log ""
log "Stages that reported a failure: $failed"
if [ "$failed" -eq 0 ]; then
  log "GATE: passed - the image may be pushed and deployed."
else
  log "GATE: blocked - the pipeline stops before the registry push."
fi
docker image rm "$IMAGE_TAG" >/dev/null 2>&1 || true
exit "$failed"
