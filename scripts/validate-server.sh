#!/usr/bin/env bash
# Submit every manifest to the API server individually with strict validation.
# Alternative versions of the same object must not be applied together, kind
# configuration is not an API object, and the injected-fault files are
# strategic-merge patches rather than complete objects.
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir"
# A server dry-run still resolves the target namespace, so the namespaces the
# manifests refer to have to exist before the loop.
for namespace in task-api notes monitoring; do
  kubectl --kubeconfig "$repo_dir/.lab/kubeconfig" --context kind-vibhuti-devops \
    create namespace "$namespace" --dry-run=client -o yaml \
    | kubectl --kubeconfig "$repo_dir/.lab/kubeconfig" --context kind-vibhuti-devops \
      apply -f - >/dev/null
done
kubectl --kubeconfig "$repo_dir/.lab/kubeconfig" --context kind-vibhuti-devops \
  apply -f devsecops/kubernetes/namespace.yaml >/dev/null

files=0
for manifest in kubernetes-*/*.yaml kubernetes-*/*/*.yaml \
                cicd-github-actions/kubernetes/*.yaml \
                devsecops/kubernetes/*.yaml \
                final-devops-project/kubernetes/*.yaml \
                final-devops-project/monitoring/*.yaml; do
  [[ "$manifest" == */kind-config.yaml ]] && continue
  printf '\n$ kubectl apply --dry-run=server --validate=strict -f %s\n' "$manifest"
  kubectl --kubeconfig "$repo_dir/.lab/kubeconfig" --context kind-vibhuti-devops \
    apply --dry-run=server --validate=strict -f "$manifest"
  files=$((files + 1))
done

printf '\n$ helm lint helm/notes-chart final-devops-project/helm/notes\n'
"$repo_dir/.lab/bin/helm" lint helm/notes-chart final-devops-project/helm/notes

for chart in helm/notes-chart final-devops-project/helm/notes; do
  printf '\n$ helm template check %s | kubectl apply --dry-run=server --validate=strict -f -\n' "$chart"
  # A distinct host: the ingress-nginx admission webhook rejects a second
  # Ingress claiming a host and path that a live one already owns.
  "$repo_dir/.lab/bin/helm" template check "$chart" --set ingress.host=check.devops.test \
    | kubectl --kubeconfig "$repo_dir/.lab/kubeconfig" --context kind-vibhuti-devops \
      -n devops-homework apply --dry-run=server --validate=strict -f -
done

printf '\nPASS: server accepted all Kubernetes objects in %s manifest files and 2 rendered charts\n' "$files"
