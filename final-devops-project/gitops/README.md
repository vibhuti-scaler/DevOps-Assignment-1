# GitOps for the Notes service

[`application.yaml`](application.yaml) is the only thing applied by hand. After
that, Argo CD reconciles `final-devops-project/kubernetes/` from `main` into the
`notes` namespace, continuously.

```bash
kubectl apply -f application.yaml
kubectl -n argocd get application notes -o wide
```

A deployment becomes a pull request that changes the image tag in
[`../kubernetes/04-deployment.yaml`](../kubernetes/04-deployment.yaml). Merging it
is the release. Rolling back is `git revert`.

Two settings carry most of the behaviour:

- `selfHeal: true` undoes changes made directly against the cluster, so
  `kubectl edit` is not a deployment mechanism any more.
- `ignoreDifferences` on `/spec/replicas` stops Argo CD and the HorizontalPod
  Autoscaler fighting over the replica count. Without it, Argo CD would reset
  the count to what Git says every time the autoscaler changed it.

The live reconciliation demo, including the self-heal behaviour, is in
[Session 20](../../monitoring-observability-gitops/README.md#gitops-in-practice);
it runs against a public example repository so it does not depend on this
repository being pushed first.
