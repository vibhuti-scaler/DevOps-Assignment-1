# Reference commits and adaptations

Student: **Vibhuti Bhatnagar**, **24BCS10288**, **vibhuti.24bcs10288@sst.scaler.com**.

The requested reference was [jaivardhandrao/DevOps-Term-9](https://github.com/jaivardhandrao/DevOps-Term-9),
inspected at main commit `fe09667` on 20 September 2026 (Asia/Kolkata).
The Kubernetes manifests, teaching notes and relationship/API validator are adapted from that
repository. The new runner, kind setup, controller installation and execution evidence were
prepared for this repository. The reference author's captured output and images are not used
as this student's execution evidence.

| Reference commit | Relevant change | How it is used here |
| --- | --- | --- |
| [e8e76a2](https://github.com/jaivardhandrao/DevOps-Term-9/commit/e8e76a2) | Four Kubernetes sections and submission links | Adapted manifests and explanations, with Vibhuti's identity and repository links. |
| [808682b](https://github.com/jaivardhandrao/DevOps-Term-9/commit/808682b) | Validation images and execution runbook | Separate actual execution logs from expected behavior. |
| [f5b9a78](https://github.com/jaivardhandrao/DevOps-Term-9/commit/f5b9a78) | Startup waits and resumable execution | Wait for CoreDNS, default ServiceAccount and client readiness; permit section reruns. |
| [9f2e955](https://github.com/jaivardhandrao/DevOps-Term-9/commit/9f2e955) | Screenshot picker recovery and fundamentals evidence | Use portable text transcripts so interactive screenshot capture cannot stop execution. |
| [f446b6f](https://github.com/jaivardhandrao/DevOps-Term-9/commit/f446b6f) | Retry transient Service reads | Bounded retries also verify expected HTTP content after updates and rollback. |

The existing Linux, shell, networking, Git, Docker applications, multi-stage build and Docker
networking folders were retained. Student email and navigation were updated.

## Corrections and local choices

- Fixed the frontend Pod-template label `version: DevOps session 12 frontend` to
  `version: frontend-v1`. Kubernetes label values cannot contain spaces; the application
  text remains in its environment variable.
- Used a dedicated kind cluster and ignored kubeconfig, including a real host-to-NodePort
  mapping for Docker Desktop on macOS.
- Included Traefik installation and namespaced RBAC, changed the Ingress class to `traefik`,
  and kept frontend/API routes and the optional TLS exercise. The reference uses the retired
  community Ingress NGINX controller; see the
  [official retirement notice](https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/).
- Extended execution to release strategies, all twelve lifecycle examples, Service recovery,
  configuration restart and certificate-verified TLS. The validation report records results.
- Created [SUBMISSION.md](SUBMISSION.md) using the eleven fields visible in the supplied
  Section B screenshot. No form URL or unseen form questions were assumed.

Technical references are linked in each session README. Controller configuration follows the
[Traefik Kubernetes Ingress provider documentation](https://doc.traefik.io/traefik/reference/install-configuration/providers/kubernetes/kubernetes-ingress/).
