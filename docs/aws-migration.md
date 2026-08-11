# DialedIN AWS Migration Plan

This document is the planning checklist for moving DialedIN from the shared course AWS account into Ahmad's own AWS account. Do not use this as a production runbook yet; it is the map for the next implementation checkpoint.

## Current Reference Environment

The current working cloud environment is the course AWS dev deployment.

```text
AWS account: 228281126655
Region: us-east-1
Dev API: https://api-dev.fursa.click
Dev AI web: https://ai-dev.fursa.click
Dev landing: https://app-dev.fursa.click
GitHub role: arn:aws:iam::228281126655:role/DialedInGitHubActionsRole
Control-plane SG: ahmadry98-dialedin-dev-control-plane
Kubeconfig secret: DIALEDIN_DEV_KUBE_CONFIG_B64
```

Working services in the reference environment:

- GitHub Actions builds Docker images and pushes them to ECR.
- GitHub Actions manually deploys a chosen image tag to dev Kubernetes.
- FastAPI agent serves `/health`, `/chat`, `/machines`, media upload, profile admin, and metrics.
- S3 stores media uploads and reviewed machine images.
- DynamoDB stores equipment profiles and shot results.
- Bedrock supports chat extraction, image recognition, and profile research.
- Prometheus/Grafana support local observability; cloud monitoring is still minimal.

## Account-Specific Values To Replace

Search for these when creating the personal account environment.

```text
228281126655
arn:aws:iam::228281126655:role/DialedInGitHubActionsRole
228281126655.dkr.ecr.us-east-1.amazonaws.com
ahmadry98-dialedin-dev-control-plane
ahmadry98-dialedin-dev-media-...
ahmadry98-dialedin-dev-equipment-profiles
ahmadry98-dialedin-dev-shot-results
DIALEDIN_DEV_KUBE_CONFIG_B64
https://api-dev.fursa.click
https://ai-dev.fursa.click
https://app-dev.fursa.click
```

Files that currently contain environment/account-specific values:

```text
README.md
.github/workflows/build-images.yaml
.github/workflows/deploy-dev.yaml
infra/k8s/agent.yaml
infra/k8s/frontend.yaml
infra/k8s/espresso-mcp.yaml
infra/k8s/dialedin-backend.yaml
infra/k8s/landing.yaml
infra/k8s/ingress.yaml
infra/k8s/README.md
infra/terraform/dev.tfvars
infra/terraform/prod.tfvars
infra/terraform/variables.tf
docs/spec.md
docs/plan.md
```

Some `us-east-1` defaults are acceptable if the personal account also uses `us-east-1`. Test files that hardcode `us-east-1` do not need migration unless the app region changes.

Current local finding: `aws sts get-caller-identity --profile default` still points to the course account `228281126655`. Use a separate personal profile before running Terraform for personal AWS.

## Target Environment Strategy

Use three clearly separated environments:

```text
course-dev     Current course AWS account, teacher/demo environment.
personal-dev   Ahmad's AWS account, first migration target.
prod           Ahmad's AWS account, future production release target.
```

Recommended order:

1. Keep `course-dev` working.
2. Create `personal-dev` in Ahmad's AWS account.
3. Deploy and test the simulator against `personal-dev`.
4. Only then prepare `prod`.

Do not point App Store or Play Store builds at the course account.

## Personal AWS Setup Checklist

Account and access:

```text
[ ] Create or choose Ahmad's AWS account.
[ ] Enable billing alerts/budgets.
[x] Configure local AWS CLI profile for the personal account, for example `dialedin-personal`.
[ ] Confirm Bedrock model access in the target region.
[ ] Decide whether to use SES or SMTP for email notifications.
[x] Create GitHub OIDC provider/role or temporary static credentials.
```

Terraform:

```text
[x] Create personal-dev tfvars.
[x] Choose personal-dev workspace name.
[ ] Confirm owner/project naming.
[x] Apply storage resources first: S3 and DynamoDB.
[x] Create ECR repositories.
[x] Apply optional EC2 Kubernetes only after storage works.
[x] Save Terraform outputs for bucket/table names and control-plane details.
```

Data migration:

```text
[ ] Export reviewed machine profiles from course DynamoDB.
[ ] Export reviewed grinder profiles from course DynamoDB.
[x] Import reviewed profiles into personal-dev DynamoDB.
[x] Copy reviewed S3 machine images into personal-dev S3.
[x] Verify `/machines` and `/grinders` show the same trusted data.
```

GitHub Actions:

Personal repo variables for the Fursa backend/DialChat repo:

```text
AWS_ACCOUNT_ID=577208624033
AWS_REGION=us-east-1
AWS_GITHUB_ACTIONS_ROLE_ARN=arn:aws:iam::577208624033:role/DialedInGitHubActionsRole
AWS_GITHUB_ACTIONS_ROLE_NAME=DialedInGitHubActionsRole
CONTROL_PLANE_SECURITY_GROUP_NAME=ahmadry98-dialin-personal-dev-control-plane
DIALEDIN_MEDIA_UPLOAD_BUCKET=ahmadry98-dialin-personal-dev-media-6f3f2008d362efc8a006fdab2b
DIALEDIN_PROFILE_TABLE=ahmadry98-dialin-personal-dev-equipment-profiles
DIALEDIN_SHOT_RESULTS_TABLE=ahmadry98-dialin-personal-dev-shot-results
```

After personal-dev Kubernetes exists, add this repo/environment secret:

```text
DIALEDIN_DEV_KUBE_CONFIG_B64=<base64 kubeconfig>
```

```text
[x] Add personal-dev GitHub environment or repo variables.
[x] Add personal AWS account ID.
[x] Add personal GitHub Actions role ARN.
[x] Add personal control-plane security group name after Terraform creates it.
[x] Add personal-dev kubeconfig secret after Kubernetes is created.
[x] Build and push images to personal ECR.
[x] Deploy personal-dev manually with a selected image tag.
```

Mobile/web:

```text
[ ] Point Expo development env vars to the personal-dev API URL.
[ ] Confirm photo upload and video upload from the mobile app against the personal-dev API.
[x] Confirm machine images load from the personal-dev API/S3 flow.
[ ] Confirm Bedrock image recognition works in the personal account.
[ ] Confirm unknown machine candidate capture works in the personal account.
[ ] Confirm admin review/promote writes personal-dev DynamoDB/S3/JSON sync as expected.
```

## Personal Dev Terraform Outputs

Created in Ahmad's personal AWS account `577208624033` on workspace `personal-dev`:

```text
dialchat_media_bucket = ahmadry98-dialin-personal-dev-media-6f3f2008d362efc8a006fdab2b
equipment_profiles_table_name = ahmadry98-dialin-personal-dev-equipment-profiles
shot_results_table_name = ahmadry98-dialin-personal-dev-shot-results
github_actions_role_arn = arn:aws:iam::577208624033:role/DialedInGitHubActionsRole

ECR repositories:
577208624033.dkr.ecr.us-east-1.amazonaws.com/dialedin-backend
577208624033.dkr.ecr.us-east-1.amazonaws.com/dialedin-fursa-agent
577208624033.dkr.ecr.us-east-1.amazonaws.com/dialedin-fursa-espresso-mcp
577208624033.dkr.ecr.us-east-1.amazonaws.com/dialedin-fursa-frontend
577208624033.dkr.ecr.us-east-1.amazonaws.com/dialedin-landing

Personal dev image tags pushed:
dialedin-backend:174a174-amd64
dialedin-fursa-agent:174a174-amd64
dialedin-fursa-espresso-mcp:174a174-amd64
dialedin-fursa-frontend:174a174-amd64
dialedin-landing:011ac66-amd64

Kubernetes:
control_plane_public_ip = 100.62.90.213
control_plane_private_ip = 10.20.1.6
control_plane_security_group = sg-01413a223bf2ac7ad
control_plane_security_group_name = ahmadry98-dialin-personal-dev-control-plane
worker_asg_name = ahmadry98-dialin-personal-dev-workers
```

Kubernetes/EC2 is created for personal-dev. Local `personal-dev.tfvars` uses `enable_k8s_cluster=true` and `enable_public_ingress=false`; this keeps the first personal cloud smoke test on port-forwarding instead of public ingress/API Gateway. Calico was applied once after bootstrap, the stale replaced worker node was removed, and all five services rolled out in the `dev` namespace.

Manual smoke test results:

```text
agent /health: OK
espresso MCP /health: OK
frontend: HTTP 200 through port-forward
DialedIn backend: HTTP 200 through port-forward
landing app: HTTP 200 through port-forward
/machines: 26 machines from personal DynamoDB
media upload URL: personal S3 presigned URL returned
machine image endpoints: S3-backed images return HTTP 200
chat endpoint: OK with ChatRequest schema
```

## Production Readiness Checklist

Production is a separate checkpoint. Do not run production from dev resources.

```text
[ ] Separate prod S3 bucket.
[ ] Separate prod DynamoDB tables.
[ ] Separate prod kubeconfig or hosting target.
[ ] Separate prod GitHub environment secrets/vars.
[ ] Production domain and API URL.
[ ] Production Bedrock/IAM permissions.
[ ] Production SES/SMTP email sending.
[ ] Monitoring and alerts.
[ ] Rollback instructions.
[ ] Privacy notes for uploaded photos/videos.
[ ] Real-device smoke test.
[ ] Manual approval before deploy-prod.
```

## Verification Commands

After a personal-dev deployment exists:

```bash
curl -k https://<personal-dev-api>/health
curl -k https://<personal-dev-api>/machines
curl -k https://<personal-dev-api>/grinders
```

Run the Expo app against the personal-dev API:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
EXPO_PUBLIC_AI_SHOT_API_URL=https://<personal-dev-api> \
EXPO_PUBLIC_DIALEDIN_API_URL=https://<personal-dev-api> \
npm run ios
```

## Decision For Now

For the course final demo, the current `course-dev` deployment is enough. The personal AWS migration should happen before public release, TestFlight distribution, Play Store testing, or real users.
