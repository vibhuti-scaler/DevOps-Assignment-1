# Session 12: Kubernetes Ingress, ConfigMaps & Secrets

- **Name:** Vibhuti Bhatnagar
- **Roll no:** 24BCS10288
- **Email:** vibhuti.24bcs10288@sst.scaler.com
- **Batch:** B

Use the [local lab setup](../kubernetes-fundamentals/README.md#local-lab-setup). Run commands from
this folder. The demo has an Nginx frontend and a small Python API. It does not connect to or
create a database. The API reports configuration and only a boolean indicating whether the
demonstration Secret loaded.

```text
Host: devops.test
       |
Ingress controller
       |-- /api -> demo-backend Service -> Python Pods :5000
       +-- /    -> demo-frontend Service -> Nginx Pods :80

demo-config ConfigMap -> environment variables
demo-credentials Secret -> backend DEMO_TOKEN
demo-backend-code ConfigMap -> read-only /app/app.py
```

## Files and concepts

| File / object | Purpose |
| --- | --- |
| [configmap.yaml](configmap.yaml) | Non-sensitive environment, log level, and currency. |
| `demo-credentials` | Secret created locally from an ignored file; no real secret value is committed. |
| [backend-code.yaml](backend-code.yaml) | Python source mounted as a ConfigMap to keep this classroom example build-free. |
| [backend.yaml](backend.yaml) | Two API replicas, readiness check, configuration references, and ClusterIP Service. |
| [frontend.yaml](frontend.yaml) | Two Nginx replicas and ClusterIP Service. |
| [ingress.yaml](ingress.yaml) | Host and Prefix routes for `/` and `/api`. |
| [optional/ingress-tls.yaml](optional/ingress-tls.yaml) | TLS and separate frontend/API hostnames. |

A ConfigMap stores configuration. A Secret is a resource for sensitive values; base64 encoding
alone does not encrypt them. Access control and encryption at rest must be configured by the
cluster operator. Avoid putting credentials into screenshots, logs, source control, or form answers.

## 1. Create the configuration and local demonstration Secret

The following Python command creates a random disposable value in `.env.secret`, which is
ignored by Git. It sets restrictive file permissions and does not print the value.

```bash
python3 - <<'PY'
from pathlib import Path
import secrets
p = Path('.env.secret')
with p.open('x') as f:
    p.chmod(0o600)
    f.write('DEMO_TOKEN=' + secrets.token_hex(16) + '\n')
PY
kubectl --context=kind-vibhuti-devops -n devops-homework apply -f configmap.yaml -f backend-code.yaml
kubectl --context=kind-vibhuti-devops -n devops-homework create secret generic demo-credentials --from-env-file=.env.secret
kubectl --context=kind-vibhuti-devops -n devops-homework describe secret demo-credentials
```

This is a first-run command. If `.env.secret` or the Secret already exists, reuse it rather than
overwriting it. `describe secret` shows key names and sizes, not the value.

## 2. Start the applications

```bash
kubectl --context=kind-vibhuti-devops -n devops-homework apply -f frontend.yaml -f backend.yaml
kubectl --context=kind-vibhuti-devops -n devops-homework rollout status deployment/demo-frontend --timeout=120s
kubectl --context=kind-vibhuti-devops -n devops-homework rollout status deployment/demo-backend --timeout=120s
kubectl --context=kind-vibhuti-devops -n devops-homework get pods,services
kubectl --context=kind-vibhuti-devops -n devops-homework exec deployment/demo-backend -- python3 -c 'import os; print("environment:", os.environ["ENVIRONMENT"]); print("secret_loaded:", bool(os.environ.get("DEMO_TOKEN")))'
```

First check the API directly with a port-forward in one terminal:

```bash
kubectl --context=kind-vibhuti-devops -n devops-homework port-forward service/demo-backend 8083:80
```

From another terminal:

```bash
curl --fail http://localhost:8083/api/health
```

Expected fields include `environment: coursework`, `currency: INR`, and `secret_loaded: true`.
This direct check does not verify Ingress routing.

## 3. Route through the Ingress controller

This lab supplies a [Traefik controller and its RBAC](controller.yaml) and uses
`ingressClassName: traefik`. This adapts the reference's Ingress examples to a controller
that can be installed directly in kind. The controller watches only `devops-homework`;
its namespaced Role grants access to the lab's Services, EndpointSlices, Ingresses and
TLS Secrets. A separate ClusterRole allows discovery of IngressClasses and nodes.
See the [Traefik Kubernetes Ingress documentation](https://doc.traefik.io/traefik/reference/install-configuration/providers/kubernetes/kubernetes-ingress/).

```bash
kubectl --context=kind-vibhuti-devops apply -f controller.yaml
kubectl --context=kind-vibhuti-devops -n devops-homework rollout status deployment/lab-ingress --timeout=180s
kubectl --context=kind-vibhuti-devops get ingressclass
kubectl --context=kind-vibhuti-devops -n devops-homework apply -f ingress.yaml
kubectl --context=kind-vibhuti-devops -n devops-homework describe ingress demo-ingress
kubectl --context=kind-vibhuti-devops -n devops-homework port-forward service/lab-ingress 8084:80
```

Leave that port-forward running and use a second terminal:

```bash
curl --fail -H 'Host: devops.test' http://localhost:8084/
curl --fail -H 'Host: devops.test' http://localhost:8084/api/
curl --fail -H 'Host: devops.test' http://localhost:8084/api/health
```

The root path should return the frontend text and `/api/` should return API JSON. The API
understands the `/api` prefix, so no controller-specific rewrite annotation is required.
Prefix `/api` matches `/api` and `/api/...`, but not `/apix`. An Ingress object alone does not
start a controller. Testing through its Service exercises the controller's HTTP routes, while
external exposure still depends on the local cluster network.

## 4. Update a ConfigMap

```bash
kubectl --context=kind-vibhuti-devops -n devops-homework patch configmap demo-config --type=merge -p '{"data":{"ENVIRONMENT":"staging"}}'
kubectl --context=kind-vibhuti-devops -n devops-homework exec deployment/demo-backend -- python3 -c 'import os; print(os.environ["ENVIRONMENT"])'
kubectl --context=kind-vibhuti-devops -n devops-homework rollout restart deployment/demo-backend
kubectl --context=kind-vibhuti-devops -n devops-homework rollout status deployment/demo-backend --timeout=120s
curl --fail -H 'Host: devops.test' http://localhost:8084/api/
```

Environment variables are fixed when a container starts: expect `coursework` before the
restart and `staging` afterward. ConfigMap volume contents can update eventually, but an
application must reload them; a `subPath` mount does not receive these updates. This demo's
Python process also needs a restart when its mounted source code changes.

Restore the declared configuration after capturing the exercise:

```bash
kubectl --context=kind-vibhuti-devops -n devops-homework apply -f configmap.yaml
kubectl --context=kind-vibhuti-devops -n devops-homework rollout restart deployment/demo-backend
kubectl --context=kind-vibhuti-devops -n devops-homework rollout status deployment/demo-backend --timeout=120s
```

## 5. Optional TLS and multiple hosts

Generate a self-signed certificate for the two lab domains. Generated certificate/key files
are ignored by Git. The TLS Secret and Ingress must be in the same namespace.
The optional Ingress also enables Traefik's TLS router on `websecure` through annotations;
`spec.tls` selects the certificate and does not alone enable that router. See
[Traefik TLS routing](https://doc.traefik.io/traefik/reference/routing-configuration/kubernetes/ingress/#enabling-tls-via-annotations).

```bash
openssl req -x509 -nodes -newkey rsa:2048 -days 2 -keyout tls.key -out tls.crt -subj '/CN=portal.devops.test' -addext 'subjectAltName=DNS:portal.devops.test,DNS:api.devops.test'
kubectl --context=kind-vibhuti-devops -n devops-homework create secret tls demo-tls --cert=tls.crt --key=tls.key
kubectl --context=kind-vibhuti-devops -n devops-homework apply -f optional/ingress-tls.yaml
kubectl --context=kind-vibhuti-devops -n devops-homework port-forward service/lab-ingress 8443:443
```

In a second terminal, trust only the lab certificate and set both hostname resolution and SNI:

```bash
curl --fail --noproxy '*' --cacert tls.crt --resolve portal.devops.test:8443:127.0.0.1 https://portal.devops.test:8443/
curl --fail --noproxy '*' --cacert tls.crt --resolve api.devops.test:8443:127.0.0.1 https://api.devops.test:8443/api/health
```

## 6. Base64 newline exercise

Use a public dummy string to inspect encoding without exposing the generated Secret:

```bash
python3 - <<'PY'
import base64
for value in (b'classroom-demo', b'classroom-demo\n'):
    encoded = base64.b64encode(value)
    print(encoded.decode(), repr(base64.b64decode(encoded)))
PY
```

`echo` normally adds a newline; `printf '%s' VALUE` does not. Decoded bytes determine the
value, so check the bytes instead of guessing from a base64 suffix.

## Evidence, troubleshooting, and cleanup

[Raw logs](../evidence/kubernetes/README.md) and [validation results](../KUBERNETES-VALIDATION.md)
record actual Ingress requests and configuration checks from this repository's local cluster.

Capture resource listings, non-sensitive configuration, HTTP route responses, the ConfigMap
before/after restart, and TLS responses. Do not capture the value of `DEMO_TOKEN`.
For missing configuration, inspect Pod events and referenced object/key names. For routing
failures, inspect the Ingress class, host/path, backend Service port, and ready EndpointSlices.

See [validation evidence](../KUBERNETES-VALIDATION.md) for checks actually performed. After
capturing the live lab, delete only these objects and the generated local files:

```bash
kubectl --context=kind-vibhuti-devops -n devops-homework delete -f optional/ingress-tls.yaml -f ingress.yaml -f frontend.yaml -f backend.yaml -f backend-code.yaml -f configmap.yaml --ignore-not-found
kubectl --context=kind-vibhuti-devops -n devops-homework delete secret demo-credentials demo-tls --ignore-not-found
rm -f .env.secret tls.key tls.crt
```

Stop port-forwards with Ctrl+C. Remove the kind cluster only after finishing the other labs.

References: [instructor session 12](https://github.com/Nency-Ravaliya/devops-heros/tree/1a24fe08c4956db0f8f22ffd6655581f7185699e/session-12-ingress-configmaps-secrets),
[ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/),
[Secrets](https://kubernetes.io/docs/concepts/configuration/secret/),
[Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/).
