# DialedIN Production Readiness

This document is the release gate before DialedIN is pointed at real users. Personal-dev can stay fast and flexible; production should be boring, separate, and recoverable.

## Current Status

Production is deployed separately from personal-dev and is protected by the GitHub `production` environment. Personal-dev remains the integration environment:

```text
DialChat API:   http://api-dev.dialedin.me
DialChat admin: http://ai-dev.dialedin.me
Landing site:   http://app-dev.dialedin.me
```

`deploy-prod.yaml` is a guarded application deploy. It requires manual confirmation and the GitHub `production` environment, then applies the production manifests using a deploy-only Kubernetes service account. Cluster bootstrap operations such as Calico and ingress installation are intentionally admin-only.

## Hard Rules Before Production

- Do not reuse dev S3 buckets, DynamoDB tables, kubeconfig, security groups, or EC2 instances.
- Do not point App Store or Play Store builds at production until production smoke tests pass.
- Do not enable production deploy automation until rollback is tested.
- Keep recommendation logic deterministic; do not let an LLM invent shot timing or exact grind math.
- Keep unknown equipment promotion human-reviewed.

## Required Production Resources

Create these in Ahmad's personal AWS account, separate from personal-dev:

```text
S3 media bucket
DynamoDB equipment profile table
DynamoDB shot results table
ECR repositories
Kubernetes/hosting target
GitHub OIDC deploy role
Production kubeconfig secret, if Kubernetes is used
SES identity for support@dialedin.me or the dialedin.me domain
Bedrock model access and IAM permissions
Public domain records and HTTPS certificate
```

Recommended hostnames:

```text
api.dialedin.me     DialChat API
ai.dialedin.me      AI/admin web UI if exposed
app.dialedin.me     Landing/app web entry if hosted separately
```

## GitHub Environment Setup

Create a protected GitHub environment named `production`. Add reviewers before any real prod deploy job is allowed to run.

Production variables should be separate from dev variables:

```text
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=<personal account id>
AWS_GITHUB_ACTIONS_ROLE_NAME=DialedInGitHubActionsRole
AWS_GITHUB_ACTIONS_ROLE_ARN=<prod-capable role arn>
DIALEDIN_MEDIA_UPLOAD_BUCKET=<prod media bucket>
DIALEDIN_PROFILE_TABLE=<prod equipment profile table>
DIALEDIN_SHOT_RESULTS_TABLE=<prod shot results table>
CONTROL_PLANE_SECURITY_GROUP_NAME=<prod control plane SG tag, if Kubernetes>
```

Production secrets should be separate from dev secrets:

```text
DIALEDIN_PROD_KUBE_CONFIG_B64=<base64 kubeconfig for prod, if Kubernetes>
```

Do not reuse `DIALEDIN_DEV_KUBE_CONFIG_B64` for production.

## Data Promotion

Before first production launch:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
source .venv/bin/activate

# Export from the reviewed source environment.
DIALEDIN_PROFILE_STORAGE=dynamodb \
DIALEDIN_PROFILE_TABLE=<dev equipment profile table> \
python scripts/profile_repository_cli.py export --type machine --output /tmp/dialedin-machines.json

DIALEDIN_PROFILE_STORAGE=dynamodb \
DIALEDIN_PROFILE_TABLE=<dev equipment profile table> \
python scripts/profile_repository_cli.py export --type grinder --output /tmp/dialedin-grinders.json

# Import into prod after reviewing the JSON files.
DIALEDIN_PROFILE_STORAGE=dynamodb \
DIALEDIN_PROFILE_TABLE=<prod equipment profile table> \
python scripts/profile_repository_cli.py import --type machine --input /tmp/dialedin-machines.json

DIALEDIN_PROFILE_STORAGE=dynamodb \
DIALEDIN_PROFILE_TABLE=<prod equipment profile table> \
python scripts/profile_repository_cli.py import --type grinder --input /tmp/dialedin-grinders.json
```

Copy only reviewed machine images into the production media bucket. Do not copy raw user test videos unless they are intentionally part of a test dataset.

## Pre-Deploy Checks

Run static readiness checks:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/Fursa-project
.venv/bin/python scripts/production_readiness_check.py
```

Run application checks:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest modeling/tests services/espresso_mcp/tests services/agent/tests -q
cd services/frontend && npm run typecheck && npm run build
```

Confirm AWS target account before any Terraform apply:

```bash
aws sts get-caller-identity --profile dialedin-personal
```

## Production Smoke Tests

After production deploy, verify these before sending users to the app:

```bash
curl https://api.dialedin.me/health
curl https://api.dialedin.me/machines
curl https://api.dialedin.me/grinders
curl https://ai.dialedin.me/api/health
```

Then run the mobile app against production only for final verification:

```bash
cd /Users/ahmadrayan/Desktop/DialedIn/dialedin-mobile
EXPO_PUBLIC_DIALCHAT_API_URL=https://api.dialedin.me \
EXPO_PUBLIC_AI_SHOT_API_URL=https://api.dialedin.me \
EXPO_PUBLIC_DIALEDIN_API_URL=https://api.dialedin.me \
npm run ios -- --clear
```

Manual product smoke:

```text
Open machine list and verify images load.
Open a machine detail page.
Run AI Shot Analysis with a known machine and grinder.
Upload a short shot video and confirm S3 upload succeeds.
Confirm low-confidence timing asks for confirmation.
Enter an unknown machine and verify profile candidate capture.
Confirm profile-candidate email is delivered to support@dialedin.me.
Open admin and verify the candidate appears.
```

## Monitoring Checks

For Prometheus/Grafana, verify:

```promql
up
up{job="dialedin-agent"}
increase(dialedin_chat_requests_total[5m])
increase(dialedin_mcp_tool_errors_total[10m])
dialedin_audio_timing_confidence_latest < 0.7
increase(dialedin_profile_research_runs_total{status="error"}[30m])
sum by (status_family) (increase(dialedin_http_requests_total[5m]))
increase(dialedin_http_5xx_total[10m])
```

For personal-dev CloudWatch, verify these alarms exist and send to the Terraform `alert_email` SNS subscription:

```text
*-ingress-target-5xx
*-ingress-unhealthy-hosts
*-control-plane-cpu-high
```

The backend emits structured JSON request logs on stdout. The mobile app emits scrubbed observability events for API failures, media upload failures, permission denial, oversized videos, and session persistence failures. Do not log image base64, media keys, presigned URLs, or message contents.

Production alerts should cover:

```text
Agent down
Espresso MCP down
High MCP tool errors
Profile research failures
Repeated media upload failures
Low timing confidence spikes
High 5xx rate at the ingress/load balancer
```

## Rollback

For Kubernetes, rollback a bad deployment:

```bash
kubectl rollout history -n prod deployment/dialchat-agent
kubectl rollout undo -n prod deployment/dialchat-agent
kubectl rollout status -n prod deployment/dialchat-agent --timeout=240s
```

Repeat for affected deployments:

```text
dialchat-agent
espresso-mcp
dialchat-frontend
dialedin-backend
dialedin-landing
```

If the bad release changed data or profiles:

```text
Disable profile promotion temporarily.
Export current prod profiles for backup.
Re-import the previous reviewed profile JSON.
Verify /machines and /grinders before reopening admin promotion.
```

If the bad release changed DNS or HTTPS:

```text
Restore the previous DNS record or listener rule.
Wait for health checks to pass.
Keep the old target group/listener available until the new one is stable.
```

## Production Go/No-Go

Go only when all are true:

```text
[ ] Production resources are separate from dev.
[ ] HTTPS works on production API and app domains.
[ ] Bedrock image/text calls work in production IAM.
[ ] SES email sends from support@dialedin.me.
[ ] Reviewed profiles and machine images are loaded.
[ ] Smoke tests pass from a real phone or simulator.
[ ] Monitoring dashboard and alerts are visible.
[ ] Rollback command/path is tested.
[ ] Mobile release config points to the intended API URL.
```
