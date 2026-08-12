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

For the simplest local compose run, keep `DIALEDIN_MEDIA_STORAGE_MODE=local`, `DIALEDIN_PROFILE_STORAGE=json`, and `PROFILE_RESEARCH_AUTORUN=false`, and `PROFILE_RESEARCH_SOURCE_DISCOVERY=false`. Use S3/DynamoDB/Bedrock env vars only when you want the compose stack to talk to AWS.

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
dialedin_audio_analysis_requests_total
dialedin_audio_timing_confidence_latest
dialedin_audio_analysis_duration_seconds_latest
dialedin_media_uploaded_bytes_latest
dialedin_profile_research_runs_total
dialedin_mcp_tool_errors_total
dialedin_http_requests_total
sum by (status_family) (increase(dialedin_http_requests_total[5m]))
increase(dialedin_http_5xx_total[10m])
dialedin_http_request_seconds_latest
scrape_duration_seconds{job=~"dialedin-agent|espresso-mcp-health"}
```

Alert rules live in `monitoring/alerts.yml` and are loaded by local Prometheus. Useful alert checks:

```promql
ALERTS
increase(dialedin_mcp_tool_errors_total[10m])
dialedin_audio_timing_confidence_latest < 0.7
increase(dialedin_profile_research_runs_total{status="error"}[30m])
increase(dialedin_http_5xx_total[10m])
```

For personal-dev cloud monitoring, Terraform creates SNS-backed CloudWatch alarms for ALB target 5xx responses, unhealthy ingress targets, and high control-plane CPU when public ingress is enabled. App logs are structured JSON on stdout so Kubernetes/CloudWatch log collection can parse method, path, status, and latency without exposing user media contents.

Grafana opens at `http://localhost:3001` with `admin` / `admin` by default. Open **Dashboards -> DialedIN -> DialedIN Local Stack** for the service overview, or **DialedIN Shot Analysis Observability** for chat/audio/upload/profile research metrics.

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

## Run The App From Terraform / Cloud

Use this flow when you want to test the real AWS dev environment instead of local Docker Compose.

### 1. Start Or Update The AWS Infrastructure

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project/infra/terraform
terraform init
terraform workspace select dev || terraform workspace new dev
terraform apply -var-file=dev.tfvars -var-file=k8s-dev.tfvars
```

Useful outputs:

```bash
terraform output dialchat_media_bucket
terraform output equipment_profiles_table_name
terraform output shot_results_table_name
terraform output control_plane_public_ip
terraform output application_urls
```

### 2. Check Kubernetes

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true get nodes -o wide
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true get pods -n dev -o wide
```

If nodes are not ready after recreating EC2, install Calico again, then redeploy the app manifests. This is a manual dev step for now; CI/CD should automate it later.

### 3. Deploy Or Refresh App Workloads

If you changed code, build and push new images first, then update the image tags in `infra/k8s/*.yaml`.

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -f infra/k8s/00-namespaces.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/agent.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/espresso-mcp.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/frontend.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/dialedin-backend.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/landing.yaml
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true apply -n dev -f infra/k8s/hpa.yaml
```

Wait for rollouts:

```bash
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true rollout status -n dev deployment/dialchat-agent
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true rollout status -n dev deployment/dialchat-frontend
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true rollout status -n dev deployment/espresso-mcp
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true rollout status -n dev deployment/dialedin-backend
KUBECONFIG=.kube/dialedin-dev kubectl --insecure-skip-tls-verify=true rollout status -n dev deployment/dialedin-landing
```

### 4. Open The Cloud URLs

```text
DialChat API:   http://api-dev.dialedin.me
DialChat web:   http://ai-dev.dialedin.me
Landing site:   http://app-dev.dialedin.me
```

Smoke checks:

```bash
curl http://api-dev.dialedin.me/health
curl http://api-dev.dialedin.me/machines
curl http://ai-dev.dialedin.me/api/health
```

### 5. Run The Phone App Against Cloud

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
EXPO_PUBLIC_DIALCHAT_API_URL=http://api-dev.dialedin.me \
EXPO_PUBLIC_AI_SHOT_API_URL=http://api-dev.dialedin.me \
EXPO_PUBLIC_DIALEDIN_API_URL=http://api-dev.dialedin.me \
npm run ios -- --clear
```

Use local URLs only when you are running FastAPI on your Mac. Use the cloud URLs above when the app should talk to the Terraform/Kubernetes deployment.

### 6. Enable Profile Candidate Email Notifications

The app can email you when a new unknown **machine or grinder** is captured as a profile candidate. The email goes to `support@dialedin.me` and includes the candidate name, type, latest shot context, and the admin review link. Research autorun should already queue the evidence/draft work, so the admin flow is: open admin, check score/evidence, add an image if it is a machine, then promote.

Email is disabled by default so local tests and CI do not send messages. In AWS, SES is preferred and the sender should be a verified identity such as `support@dialedin.me`.

```bash
PROFILE_CANDIDATE_EMAIL_ENABLED=true
PROFILE_CANDIDATE_EMAIL_PROVIDER=ses
PROFILE_CANDIDATE_EMAIL_FROM=support@dialedin.me
PROFILE_CANDIDATE_EMAIL_TO=support@dialedin.me
PROFILE_CANDIDATE_ADMIN_URL=http://ai-dev.dialedin.me/admin
```

SES setup notes: verify `support@dialedin.me` or the `dialedin.me` domain in SES, keep the worker IAM permission for `ses:SendEmail`, and restart the agent deployment after changing the environment. SMTP is still supported locally by setting `PROFILE_CANDIDATE_EMAIL_PROVIDER=smtp` plus `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, and `SMTP_USE_TLS`.

## GitHub Actions CI/CD Setup

Checkpoint 27 adds GitHub Actions for tests, Docker image builds, and manual dev deployment. Configure these repository variables and secrets before using the build/deploy workflows.

For the AWS account migration plan, see [docs/aws-migration.md](docs/aws-migration.md). The current course AWS account is a working dev/demo environment; production should move to Ahmad's own AWS account before public release.

Repository variables:

```text
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=228281126655
AWS_GITHUB_ACTIONS_ROLE_ARN=arn:aws:iam::228281126655:role/DialedInGitHubActionsRole
CONTROL_PLANE_SECURITY_GROUP_NAME=ahmadry98-dialedin-dev-control-plane
```

If `AWS_GITHUB_ACTIONS_ROLE_ARN` is empty, the workflows fall back to static AWS access key secrets. Prefer OIDC for the course account and for your personal AWS account later.

Repository secrets:

```text
# Only needed if you are not using the OIDC role variable above.
AWS_ACCESS_KEY_ID=<github-actions-aws-key>
AWS_SECRET_ACCESS_KEY=<github-actions-aws-secret>

# Required by Deploy Dev.
DIALEDIN_DEV_KUBE_CONFIG_B64=<base64 encoded .kube/dialedin-dev>
```

Create the kubeconfig secret from your machine with:

```bash
base64 -i /Users/ahmadrayan/Desktop/DialedIn/Fursa-project/.kube/dialedin-dev | pbcopy
```

Then paste it into the `DIALEDIN_DEV_KUBE_CONFIG_B64` GitHub secret. If the cluster is recreated, regenerate and replace this secret because the API server IP or certificate data can change.

The GitHub OIDC role currently needs these permission groups:

```text
ECR push/pull for DialedIn image repositories
EC2 DescribeSecurityGroups
EC2 AuthorizeSecurityGroupIngress/RevokeSecurityGroupIngress only for the dev control-plane security group
```

`deploy-dev.yaml` temporarily opens Kubernetes API port `6443` for the current GitHub runner IP, deploys, then revokes that rule in an `always()` cleanup step.

Workflow roles:

```text
.github/workflows/ci.yml              PR/unit/frontend/monitoring checks
.github/workflows/build-images.yaml    Build and push DialChat agent/MCP/frontend images
.github/workflows/deploy-dev.yaml      Manually deploy a chosen image tag to dev Kubernetes
.github/workflows/deploy-prod.yaml     Guarded production placeholder
```

Mobile and landing have their own repo-level workflows in their repositories.

### Exact Dev Deploy Workflow

Use this flow after code is merged to `dev` and the simulator/local smoke test passes:

1. Open **Actions -> Build Images** in GitHub.
2. Run it on the `dev` branch, or push to `dev` and let it run automatically.
3. Copy the image tag from the workflow output. By default it is `<short-sha>-amd64`.
4. Open **Actions -> Deploy Dev**.
5. Run it on the `dev` branch with that exact image tag.
6. Wait for the rollout checks to pass for `dialchat-agent`, `espresso-mcp`, and `dialchat-frontend`.
7. Test the cloud API and app:

```bash
curl http://api-dev.dialedin.me/health
curl http://api-dev.dialedin.me/machines
```

Then run the mobile app against cloud:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
EXPO_PUBLIC_DIALCHAT_API_URL=http://api-dev.dialedin.me \
EXPO_PUBLIC_AI_SHOT_API_URL=http://api-dev.dialedin.me \
EXPO_PUBLIC_DIALEDIN_API_URL=http://api-dev.dialedin.me \
npm run ios -- --clear
```

If `Deploy Dev` cannot reach Kubernetes, check these first:

```text
DIALEDIN_DEV_KUBE_CONFIG_B64 exists and was generated from the current cluster
CONTROL_PLANE_SECURITY_GROUP_NAME matches the Terraform control-plane security group tag
The EC2 control-plane instance is running
The GitHub role has the narrow temporary 6443 ingress permissions
```

### Personal AWS Dev Bootstrap

Your current local `default` AWS profile points to the course account. Before running Terraform for your own account, create a separate personal profile and confirm the account ID:

```bash
aws configure --profile dialedin-personal
aws sts get-caller-identity --profile dialedin-personal
```

Prepare the personal dev tfvars file:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project/infra/terraform
cp personal-dev.example.tfvars personal-dev.tfvars
# edit personal-dev.tfvars if you want a different owner, region, domain, or CORS origins
```

Start with storage and ECR only. This keeps cost/risk lower than creating EC2 Kubernetes immediately:

```bash
terraform init
terraform workspace new personal-dev || terraform workspace select personal-dev
AWS_PROFILE=dialedin-personal terraform plan -var-file=personal-dev.tfvars
```

Only run `terraform apply` after the plan shows the expected personal AWS account and resources. The current default profile is the course account, so do not run personal-account Terraform without `AWS_PROFILE=dialedin-personal` or equivalent credentials.

After storage/ECR works, the next implementation step is data migration: export reviewed profiles and reviewed machine images from the course account, then import/copy them into the personal account.


### Personal Dev Public Ingress

Personal-dev now has an AWS Application Load Balancer in front of `ingress-nginx`. Because `dialedin.me` is currently managed outside Route 53, Terraform creates the ALB but does not create DNS records automatically. Add these CNAME records in the DNS provider for `dialedin.me`:

```text
api-dev  CNAME  ahmadry98-dialin-personal-dev-al-187028928.us-east-1.elb.amazonaws.com
ai-dev   CNAME  ahmadry98-dialin-personal-dev-al-187028928.us-east-1.elb.amazonaws.com
app-dev  CNAME  ahmadry98-dialin-personal-dev-al-187028928.us-east-1.elb.amazonaws.com
```

Current personal-dev ingress is HTTP-only while DNS is external:

```text
DialChat API:   http://api-dev.dialedin.me
DialChat web:   http://ai-dev.dialedin.me
Landing site:   http://app-dev.dialedin.me
```

Before DNS propagates, smoke test the ALB with a Host header:

```bash
ALB=ahmadry98-dialin-personal-dev-al-187028928.us-east-1.elb.amazonaws.com
curl -H 'Host: api-dev.dialedin.me' http://$ALB/health
curl -H 'Host: api-dev.dialedin.me' http://$ALB/machines
```

After the CNAME records resolve, run the mobile app against the public dev API:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
EXPO_PUBLIC_DIALCHAT_API_URL=http://api-dev.dialedin.me \
EXPO_PUBLIC_AI_SHOT_API_URL=http://api-dev.dialedin.me \
EXPO_PUBLIC_DIALEDIN_API_URL=http://api-dev.dialedin.me \
npm run ios -- --clear
```

Next production-quality step: move `dialedin.me` DNS to Route 53 or add DNS validation records manually, then enable ACM/HTTPS so the app can use `https://api-dev.dialedin.me`.

### Prod Readiness Checklist

For the full release gate, use [docs/production-readiness.md](docs/production-readiness.md). It contains the prod separation rules, GitHub environment setup, data promotion flow, smoke tests, monitoring checks, and rollback commands.

Run the static readiness gate before a production checkpoint or release PR:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
.venv/bin/python scripts/production_readiness_check.py
```

Do not run production deployment until these are done:

```text
[ ] Create separate prod Terraform workspace/resources, not reused dev tables/buckets.
[ ] Create prod S3 bucket for media and machine photos.
[ ] Create prod DynamoDB tables for equipment profiles and shot results.
[ ] Import reviewed machine/grinder seed profiles into prod DynamoDB.
[ ] Create prod ECR image tags from a main release commit.
[ ] Create prod Kubernetes cluster or final hosting target.
[ ] Create prod kubeconfig secret, separate from DIALEDIN_DEV_KUBE_CONFIG_B64.
[ ] Configure production GitHub environment secrets and vars.
[ ] Configure production domain/API URLs.
[ ] Configure production Bedrock/IAM access in your own AWS account.
[ ] Configure email/SES or SMTP for candidate notifications.
[ ] Add rollback steps and verify health checks before exposing users.
```

`deploy-prod.yaml` is intentionally guarded. It requires typing `deploy-prod`, but it does not apply real production manifests yet. Treat it as a placeholder until the prod infrastructure checkpoint is complete.

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

## CI/CD Image Builds

Pull requests to `main` run checks only: Python tests, frontend typecheck/build, monitoring validation, and Docker Compose validation. They do not push Docker images.

Docker image publishing is intentionally limited:

- Pushes to `dev` or `main` build images only when relevant source paths changed.
- `agent` builds when `services/agent`, shared espresso code, modeling code, labels, or the image workflow changed.
- `espresso-mcp` builds when `services/espresso_mcp`, modeling code, labels, or the image workflow changed.
- `frontend` builds when `services/frontend`, copied espresso profile data, or the image workflow changed.
- `workflow_dispatch` still builds all images manually when you explicitly choose to rebuild a tag.

Docs-only, Terraform-only, and mobile-only changes should not publish new DialChat Docker images.
