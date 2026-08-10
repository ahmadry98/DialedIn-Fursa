# DialedIN Kubernetes Manifests

These manifests deploy the local Docker Compose services into a kubeadm cluster on AWS EC2.
They are designed to be applied after `infra/terraform` creates the optional EC2 Kubernetes cluster.

## Services

- `dialchat-agent`: FastAPI `/chat`, `/machines`, media, profile, and recommendation API on port `8000`.
- `espresso-mcp`: HTTP health/tool wrapper for the espresso MCP package on port `9000`.
- `dialchat-frontend`: Next.js admin/local web UI on port `3000`.
- `dialedin-backend`: existing DialedIn Django API on port `8010`.
- `dialedin-landing`: public landing app on port `3002`.

## Before Apply

Replace placeholder secrets in:

- `agent.yaml`: `DIALEDIN_MEDIA_UPLOAD_BUCKET`, `DIALEDIN_PROFILE_TABLE`, `DIALEDIN_SHOT_RESULTS_TABLE`
- `landing.yaml`: `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

Confirm the image names match the registry you pushed during the CI/CD checkpoint. For EC2 workers, build and push Linux/AMD64 images even if you build from an Apple Silicon Mac.

## ECR Pull Secret

The dev kubeadm cluster currently uses a Docker registry secret to pull ECR images. Create or refresh it before applying workloads:

```bash
ECR_PASSWORD=$(aws ecr get-login-password --region us-east-1)
kubectl create secret docker-registry ecr-pull-secret -n dev \
  --docker-server=228281126655.dkr.ecr.us-east-1.amazonaws.com \
  --docker-username=AWS \
  --docker-password="$ECR_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Apply Order

```bash
kubectl apply -f infra/k8s/00-namespaces.yaml
kubectl apply -n dev -f infra/k8s/agent.yaml
kubectl apply -n dev -f infra/k8s/espresso-mcp.yaml
kubectl apply -n dev -f infra/k8s/frontend.yaml
kubectl apply -n dev -f infra/k8s/dialedin-backend.yaml
kubectl apply -n dev -f infra/k8s/landing.yaml
kubectl apply -n dev -f infra/k8s/hpa.yaml
kubectl apply -n dev -f infra/k8s/ingress.yaml
```

For the full Stage 1 manual cloud smoke, apply `agent.yaml`, `espresso-mcp.yaml`, `frontend.yaml`, `dialedin-backend.yaml`, `landing.yaml`, and `hpa.yaml`. Ingress is still optional and disabled until the public URL/domain phase.

## Smoke Test

```bash
kubectl get pods -n dev
kubectl port-forward -n dev svc/dialchat-agent-svc 8000:8000
curl http://127.0.0.1:8000/health
```
