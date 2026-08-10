# DialedIN AI Shot Analysis

AI espresso shot coach for DialedIN. The app collects machine, grinder, dose, grind setting, roast, taste, and shot timing/video through chat, analyzes audio timing, and recommends the next grind adjustment.

## Project Location

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
```

## First-Time Setup After Moving The Folder

If `.venv/bin/uvicorn` says `bad interpreter`, recreate the virtual environment because the old venv stored the previous path.

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
deactivate 2>/dev/null || true
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r services/agent/requirements.txt
python -m pip install -r services/espresso_mcp/requirements.txt
python -m pip install -r modeling/requirements.txt
```

## Run Backend

Use `0.0.0.0` so the iPhone simulator or real phone can reach the backend through your Mac LAN IP.

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
source .venv/bin/activate
python -m uvicorn services.agent.app:app --host 0.0.0.0 --port 8000
```

Local backend URL:

```text
http://127.0.0.1:8000
```

LAN backend URL:

```text
http://192.168.68.101:8000
```

## Run Web Frontend

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project/services/frontend
npm run dev -- --hostname 0.0.0.0
```

Local frontend URL:

```text
http://localhost:3000
```

LAN/mobile frontend URL:

```text
http://192.168.68.101:3000
```

## Run DialedIn Mobile App

The mobile app currently opens the web AI Shot Analysis screen from:

```text
http://192.168.68.101:3000
```

Run the Expo app:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
npm run ios
```

To override the AI chat URL:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
EXPO_PUBLIC_AI_SHOT_ANALYSIS_URL=http://YOUR_MAC_IP:3000 npm run ios
```

## Media Upload Storage

For local simulator testing, leave storage in local mode. Uploaded shot videos are saved under `data/uploads/` and the analyzer receives that local path.

```bash
DIALEDIN_MEDIA_STORAGE_MODE=local
DIALEDIN_LOCAL_MEDIA_UPLOAD_DIR=data/uploads
```

For AWS/S3 mode, apply the Terraform in `infra/terraform`, then set the bucket output in the backend env:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project/infra/terraform
terraform init
terraform workspace new dev || terraform workspace select dev
terraform apply -var-file=dev.tfvars
terraform output dialchat_media_bucket
```

The dev Terraform config also adds S3 CORS for `localhost`, `127.0.0.1`, and your current LAN dev origin so browser/mobile presigned uploads can use `PUT`. Re-run `terraform apply -var-file=dev.tfvars` after changing those origins.

```bash
DIALEDIN_MEDIA_STORAGE_MODE=s3
DIALEDIN_MEDIA_UPLOAD_BUCKET=<terraform output dialchat_media_bucket>
DIALEDIN_MEDIA_UPLOAD_PREFIX=dialchat-media
AWS_REGION=us-east-1
```

To persist shot history in DynamoDB instead of memory, also set the table output:

```bash
terraform output shot_results_table
DIALEDIN_SHOT_RESULTS_TABLE=<terraform output shot_results_table>
# Optional strict mode; setting the table is enough to enable DynamoDB persistence.
DIALEDIN_SHOT_HISTORY_STORAGE=dynamodb
```

Trusted machine/grinder profiles use DynamoDB by default when the equipment profile table is configured. Import the reviewed JSON seed data once per environment:

```bash
terraform output equipment_profiles_table_name
DIALEDIN_PROFILE_STORAGE=dynamodb
DIALEDIN_PROFILE_TABLE=<terraform output equipment_profiles_table_name>
python scripts/profile_repository_cli.py import --type machine --input services/espresso_mcp/machine_profiles.json
python scripts/profile_repository_cli.py import --type grinder --input services/espresso_mcp/grinder_profiles.json
```

Without `DIALEDIN_PROFILE_TABLE`, profile data falls back to the checked-in JSON files. To force JSON even when a table is configured, set `DIALEDIN_PROFILE_STORAGE=json`.

The mobile app and Next.js local demo use `/media/upload-url`, upload the video with `PUT`, call `/media/register`, then send the returned `video_s3_key` to `/chat` or `/analyze-shot`.

## Run With Docker Compose

Checkpoint 24 is the local DialedIn stack. It runs the backend/web services and monitoring together; the Expo iPhone app still runs natively outside Docker.

Services included:

```text
DialChat agent API      http://localhost:8000
Espresso MCP health    http://localhost:9000/health
AI/admin web frontend  http://localhost:3000
DialedIn Django API    http://localhost:8010/api/machines/
DialedIn landing       http://localhost:3002
Prometheus             http://localhost:9090
Grafana                http://localhost:3001
```

First time only, copy the Compose env file:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
cp .env.compose.example .env.compose
```

Start Docker Desktop, then run the local stack:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
docker compose up --build
```

Then run the phone app in a second terminal:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
npm run ios
```

For the simplest local compose run, keep `DIALEDIN_MEDIA_STORAGE_MODE=local`, `DIALEDIN_PROFILE_STORAGE=json`, and `PROFILE_RESEARCH_AUTORUN=false`. Use S3/DynamoDB/Bedrock env vars only when you want the compose stack to talk to AWS.

Grafana starts with Prometheus already configured as the default data source. Default local login is `admin` / `admin`, unless changed in `.env.compose`.

### Monitoring Checks

Prometheus queries you can paste into `http://localhost:9090`:

```promql
up
up{job="dialedin-agent"}
up{job="espresso-mcp-health"}
dialedin_chat_requests_total
increase(dialedin_chat_requests_total[5m])
dialedin_shot_analysis_requests_total
dialedin_last_missing_fields_count
dialedin_espresso_mcp_tool_count
scrape_duration_seconds{job=~"dialedin-agent|espresso-mcp-health"}
```

Grafana opens at `http://localhost:3001` with `admin` / `admin` by default. Open **Dashboards -> DialedIN -> DialedIN Local Stack** to see the provisioned local dashboard.

Stop the stack with:

```bash
docker compose down
```


Important: the mobile machine/grinder pages should use the DialChat agent API on `http://localhost:8000`. The Django API on `http://localhost:8010` is the older DialedIn backend and currently has only its small SQLite seed list.

Terraform comes after this local workflow is stable. Use Terraform when you want AWS resources or deployment infrastructure: S3, DynamoDB, IAM, VPC, EC2/ECS/EKS, load balancers, and later production monitoring. Compose is for running locally; Terraform is for creating cloud infrastructure.


## Kubernetes On AWS EC2

Checkpoint 25 adds an opt-in kubeadm Kubernetes cluster adapted from PolyAIFursa. Existing S3/DynamoDB Terraform still works by default; the EC2 cluster is only created when `enable_k8s_cluster=true`.

Prepare a local Kubernetes tfvars file with your SSH key and current IP before applying the cluster:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project/infra/terraform
cp k8s-dev.example.tfvars k8s-dev.tfvars
# edit k8s-dev.tfvars with your current public IP and public SSH key
```

Then initialize and apply from the Terraform folder:

```bash
terraform init
terraform workspace select dev || terraform workspace new dev
terraform apply -var-file=dev.tfvars -var-file=k8s-dev.tfvars
```

After the control plane and workers are up, copy kubeconfig from the control-plane EC2 host. For this dev cluster, replace the private API server IP in kubeconfig with the `control_plane_public_ip` Terraform output, then use `--insecure-skip-tls-verify=true` unless the kubeadm cert is regenerated with the public IP as a SAN.

Install Calico networking before deploying app workloads:

```bash
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.32.1/manifests/tigera-operator.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -f /Users/ahmadrayan/Desktop/Fursa/PolyAIFursa/infra/k8s/calico/custom-resources.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true get nodes -o wide
```

Install ingress-nginx when public ingress is enabled. Terraform points the ALB at NodePort `30080`, so the controller service must expose that fixed port:

```bash
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.13.0/deploy/static/provider/cloud/deploy.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true -n ingress-nginx patch svc ingress-nginx-controller \
  -p '{"spec":{"type":"NodePort","ports":[{"name":"http","port":80,"targetPort":"http","protocol":"TCP","nodePort":30080},{"name":"https","port":443,"targetPort":"https","protocol":"TCP","nodePort":30443}]}}'
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true -n ingress-nginx rollout status deploy/ingress-nginx-controller --timeout=240s
```

Build and push Linux/AMD64 images for the EC2 workers. Mac builds default to ARM, so keep `--platform linux/amd64`:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
TAG=checkpoint25-$(git rev-parse --short HEAD)-amd64
REGISTRY=228281126655.dkr.ecr.us-east-1.amazonaws.com
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$REGISTRY"
docker buildx build --platform linux/amd64 -f services/agent/Dockerfile -t "$REGISTRY/dialedin-fursa-agent:$TAG" --push .
docker buildx build --platform linux/amd64 -f services/espresso_mcp/Dockerfile -t "$REGISTRY/dialedin-fursa-espresso-mcp:$TAG" --push .
docker buildx build --platform linux/amd64 -f services/frontend/Dockerfile --build-arg NEXT_PUBLIC_AGENT_API_URL=/api -t "$REGISTRY/dialedin-fursa-frontend:$TAG" --push .
docker buildx build --platform linux/amd64 -t "$REGISTRY/dialedin-backend:$TAG" --push /Users/ahmadrayan/Desktop/DialedIn/backend
docker buildx build --platform linux/amd64 -t "$REGISTRY/dialedin-landing:$TAG" --push /Users/ahmadrayan/Desktop/DialedIn/dialedin-landing
```

Create the dev ECR pull secret before applying workloads. This is a manual dev credential; later CI/CD should refresh it or configure node image credentials automatically.

```bash
ECR_PASSWORD=$(aws ecr get-login-password --region us-east-1)
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true create secret docker-registry ecr-pull-secret -n dev \
  --docker-server=228281126655.dkr.ecr.us-east-1.amazonaws.com \
  --docker-username=AWS \
  --docker-password="$ECR_PASSWORD" \
  --dry-run=client -o yaml | KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -f -
```

Apply the full Stage 1 manifests. DialChat reads trusted equipment profiles from DynamoDB; the older Django backend is still a separate legacy/mobile backend with its own smaller machine list.

```bash
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -f infra/k8s/00-namespaces.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/agent.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/espresso-mcp.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/frontend.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/dialedin-backend.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/landing.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/hpa.yaml
```

Useful smoke checks after deploy:

```bash
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true rollout status -n dev deployment/dialchat-agent
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true rollout status -n dev deployment/espresso-mcp
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true rollout status -n dev deployment/dialchat-frontend
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true rollout status -n dev deployment/dialedin-backend
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true rollout status -n dev deployment/dialedin-landing
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true get pods -n dev
```

Open the cloud services locally through port-forwarding:

```bash
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true port-forward -n dev svc/dialchat-agent-svc 8000:8000
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true port-forward -n dev svc/dialchat-frontend-svc 3000:3000
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true port-forward -n dev svc/dialedin-backend-svc 8010:8010
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true port-forward -n dev svc/dialedin-landing-svc 3002:3002
```

Then test:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/machines
curl http://127.0.0.1:9000/health
curl http://127.0.0.1:8010/api/machines/
open http://127.0.0.1:3000
open http://127.0.0.1:3002
```

## Useful Checks

Agent graph tests:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
source .venv/bin/activate
python -m unittest services.agent.tests.test_graph
```

Frontend typecheck and build:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project/services/frontend
npm run typecheck
npm run build
```

DialedIn mobile lint:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
npm run lint
```

## Current Mobile Direction

The current mobile integration opens the web AI chat as a temporary bridge. The planned product direction is:

1. Build the AI Shot Analysis chat natively inside `dialedin-mobile`.
2. Call the FastAPI `/chat` endpoint directly from Expo.
3. Upload shot videos to S3 instead of relying on local `data/raw-videos/...` paths.
4. Show timing and recommendation conclusions in a native mobile analysis screen.
