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
[ ] Configure local AWS CLI profile for the personal account.
[ ] Confirm Bedrock model access in the target region.
[ ] Decide whether to use SES or SMTP for email notifications.
[ ] Create GitHub OIDC provider/role or temporary static credentials.
```

Terraform:

```text
[ ] Create personal-dev tfvars.
[ ] Choose personal-dev workspace name.
[ ] Confirm owner/project naming.
[ ] Apply storage resources first: S3 and DynamoDB.
[ ] Create ECR repositories.
[ ] Apply optional EC2 Kubernetes only after storage works.
[ ] Save Terraform outputs for bucket/table names and control-plane details.
```

Data migration:

```text
[ ] Export reviewed machine profiles from course DynamoDB.
[ ] Export reviewed grinder profiles from course DynamoDB.
[ ] Import reviewed profiles into personal-dev DynamoDB.
[ ] Copy reviewed S3 machine images into personal-dev S3.
[ ] Verify `/machines` and `/grinders` show the same trusted data.
```

GitHub Actions:

```text
[ ] Add personal-dev GitHub environment or repo variables.
[ ] Add personal AWS account ID.
[ ] Add personal GitHub Actions role ARN.
[ ] Add personal control-plane security group name after Terraform creates it.
[ ] Add personal-dev kubeconfig secret after Kubernetes is created.
[ ] Build and push images to personal ECR.
[ ] Deploy personal-dev manually with a selected image tag.
```

Mobile/web:

```text
[ ] Point Expo development env vars to the personal-dev API URL.
[ ] Confirm photo upload and video upload.
[ ] Confirm machine images load from the personal-dev API/S3 flow.
[ ] Confirm Bedrock image recognition works.
[ ] Confirm unknown machine candidate capture works.
[ ] Confirm admin review/promote writes personal-dev DynamoDB/S3/JSON sync as expected.
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
