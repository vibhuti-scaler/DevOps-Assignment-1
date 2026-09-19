#!/usr/bin/env bash
# Validate alternative versions individually; kind configuration is not an API object.
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir"
files=0
for manifest in kubernetes-*/*.yaml kubernetes-*/*/*.yaml; do
  [[ "$manifest" == */kind-config.yaml ]] && continue
  printf '\n$ kubectl apply --dry-run=server --validate=strict -f %s\n' "$manifest"
  kubectl --kubeconfig "$repo_dir/.lab/kubeconfig" --context kind-vibhuti-devops \
    apply --dry-run=server --validate=strict -f "$manifest"
  files=$((files + 1))
done
printf '\nPASS: server accepted all Kubernetes objects in %s manifest files\n' "$files"
