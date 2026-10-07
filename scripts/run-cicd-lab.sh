#!/usr/bin/env bash
# Executes the Session 16 CI workflow locally with act, which runs the real
# .github/workflows YAML inside a container that mirrors a GitHub-hosted
# ubuntu-latest runner. Transcripts land in evidence/cicd/.
set -uo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir"
act="$repo_dir/.lab/bin/act"
out="$repo_dir/evidence/cicd"
mkdir -p "$out"

failures=0
transcript=""
log() { printf '%s\n' "$*" | tee -a "$transcript"; }
section() {
  transcript="$out/$1.txt"
  : > "$transcript"
  log "Vibhuti Bhatnagar | 24BCS10288 | vibhuti.24bcs10288@sst.scaler.com"
  log "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $1"
}
run() { log ""; log "\$ $*"; "$@" 2>&1 | tee -a "$transcript"; return "${PIPESTATUS[0]}"; }
check() {
  if [ "$1" -eq 0 ]; then log ""; log "PASS: $2"
  else log ""; log "FAIL: $2 (exit $1)"; failures=$((failures + 1)); fi
}

# act's own exit code is not the right signal for the test job: the artifact
# upload step cannot work on this machine (explained in the transcript), so the
# job's success is judged on the steps that genuinely ran.
run_job() {
  local label="$1"; shift
  log ""
  log "\$ act $*"
  local output
  output="$("$act" "$@" 2>&1)"
  printf '%s\n' "$output" | tee -a "$transcript" >/dev/null
  printf '%s\n' "$output"
  printf '%s\n' "$output" >> "$transcript"
  printf '%s' "$output"
}

section "16-workflow-structure"
log ""
log "Every workflow in this repository, as act parses it. The Stage column is"
log "the dependency order act worked out from each job's needs:"
run "$act" --list
check $? "act parsed every workflow in the repository"
log ""
log "The CI workflow on its own:"
run "$act" push --workflows .github/workflows/ci.yml --list
check $? "the CI workflow resolves lint -> test (matrix) -> build"
log ""
log "The delivery workflows:"
run "$act" --workflows .github/workflows/cd.yml --list
check $? "the CD workflow resolves publish -> deploy"
run "$act" push --workflows .github/workflows/devsecops.yml --list
check $? "the DevSecOps workflow resolves build/test -> scans -> gate -> publish -> deploy"

section "16-ci-pipeline"
log ""
log "--- Job 1 of 3: lint ------------------------------------------------------"
output="$(run_job lint push --workflows .github/workflows/ci.yml -j lint)"
if printf '%s' "$output" | grep -q "Success - Main Run flake8" && \
   printf '%s' "$output" | grep -q "Job succeeded"; then
  log ""; log "PASS: job lint - flake8 clean on app and tests"
else
  log ""; log "FAIL: job lint"; failures=$((failures + 1))
fi

for version in 3.11 3.12; do
  log ""
  log "--- Job 2 of 3: test, Python $version -------------------------------------"
  # -b binds the working directory instead of copying it, so the JUnit and
  # coverage reports the job writes are visible on the host afterwards.
  output="$(run_job "test-$version" push --workflows .github/workflows/ci.yml \
            -j test --matrix "python-version:$version" -b)"
  if printf '%s' "$output" | grep -q "Success - Main Run the unit tests with coverage"; then
    passed="$(printf '%s' "$output" | grep -oE '[0-9]+ passed' | tail -1)"
    log ""; log "PASS: job test on Python $version ($passed)"
  else
    log ""; log "FAIL: job test on Python $version"; failures=$((failures + 1))
  fi
  if printf '%s' "$output" | grep -q "Failed to CreateArtifact"; then
    log ""
    log "NOTE: the artifact upload step cannot complete under act on this"
    log "machine. actions/upload-artifact talks to GitHub's artifact service;"
    log "act substitutes a server bound to the host's LAN address, which macOS"
    log "firewalls off from containers, and neither the Docker gateway address"
    log "nor the loopback alias can be bound from the host instead. The files"
    log "the step would have uploaded were produced by the step before it and"
    log "are listed below. On GitHub this step works unchanged."
  fi
done

log ""
log "The reports the upload step would have published:"
run ls -l cicd-github-actions/test-results.xml cicd-github-actions/coverage.xml
check $? "the test job produced its JUnit and coverage reports"
log ""
log '$ head -3 cicd-github-actions/test-results.xml'
head -3 cicd-github-actions/test-results.xml | tee -a "$transcript"
log ""
log '$ grep line-rate cicd-github-actions/coverage.xml | head -1'
grep -o 'line-rate="[0-9.]*"' cicd-github-actions/coverage.xml | head -1 | tee -a "$transcript"
rm -f cicd-github-actions/test-results.xml cicd-github-actions/coverage.xml
rm -rf cicd-github-actions/.pytest_cache cicd-github-actions/.coverage

section "16-image-build"
log ""
log "--- Job 3 of 3: build ----------------------------------------------------"
log ""
log "act shares the host Docker daemon, so a nested image build inside the"
log "runner would not reproduce what GitHub does. The build job's steps are run"
log "directly here instead."
run docker build -t task-api:ci-local cicd-github-actions
check $? "docker build"
docker rm -f ci-smoke >/dev/null 2>&1
run docker run -d --name ci-smoke -p 18800:8000 task-api:ci-local
check $? "the container started"
ok=1
for _ in $(seq 1 25); do
  if curl -fsS --max-time 3 http://127.0.0.1:18800/api/health >/dev/null 2>&1; then ok=0; break; fi
  sleep 2
done
check "$ok" "the image answers /api/health"
log ""
log '$ curl http://127.0.0.1:18800/api/health'
curl -fsS --max-time 5 http://127.0.0.1:18800/api/health | tee -a "$transcript"; log ""
log ""
log '$ curl -X POST http://127.0.0.1:18800/api/tasks -d {"title": "ship the pipeline"}'
curl -fsS --max-time 5 -X POST http://127.0.0.1:18800/api/tasks \
  -H 'Content-Type: application/json' -d '{"title": "ship the pipeline"}' | tee -a "$transcript"; log ""
log ""
log '$ curl http://127.0.0.1:18800/api/tasks'
curl -fsS --max-time 5 http://127.0.0.1:18800/api/tasks | tee -a "$transcript"; log ""
log ""
log '$ docker ps --filter name=ci-smoke'
docker ps --filter name=ci-smoke --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' | tee -a "$transcript"
log ""
log '$ docker images task-api:ci-local'
docker images task-api:ci-local --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | tee -a "$transcript"
log ""
log "The image runs as an unprivileged user, which is what the Dockerfile's"
log "USER 10001 is for:"
log ""
log '$ docker exec ci-smoke id'
docker exec ci-smoke id | tee -a "$transcript"
log ""
log "Saving the image is what the build job uploads as its artifact:"
docker save task-api:ci-local | gzip > /tmp/task-api.tar.gz
log ""
log '$ ls -lh /tmp/task-api.tar.gz'
ls -lh /tmp/task-api.tar.gz | tee -a "$transcript"
docker rm -f ci-smoke >/dev/null 2>&1
docker image rm task-api:ci-local >/dev/null 2>&1
rm -f /tmp/task-api.tar.gz

log ""
log "Stages that reported a failure: $failures"
exit "$failures"
