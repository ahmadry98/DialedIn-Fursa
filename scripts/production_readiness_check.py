#!/usr/bin/env python3
"""Static production-readiness checks for DialedIN infrastructure and CI/CD.

This intentionally does not call AWS. It catches repo-level drift before a prod
checkpoint: missing guarded workflows, missing storage/profile settings, and
accidental dev/prod mixing in the committed config.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    warning: bool = False


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def has_all(text: str, values: list[str]) -> bool:
    return all(value in text for value in values)


def check_required_files() -> list[Check]:
    files = [
        ".github/workflows/ci.yml",
        ".github/workflows/build-images.yaml",
        ".github/workflows/deploy-dev.yaml",
        ".github/workflows/deploy-prod.yaml",
        "infra/k8s/agent.yaml",
        "infra/k8s/espresso-mcp.yaml",
        "infra/k8s/frontend.yaml",
        "infra/k8s/ingress.yaml",
        "infra/terraform/prod.tfvars",
        "docs/production-readiness.md",
    ]
    return [Check(f"required file: {path}", exists(path), path) for path in files]


def check_ci() -> list[Check]:
    ci = read(".github/workflows/ci.yml")
    build = read(".github/workflows/build-images.yaml")
    deploy_dev = read(".github/workflows/deploy-dev.yaml")
    deploy_prod = read(".github/workflows/deploy-prod.yaml")
    return [
        Check("CI runs on PRs to main", "pull_request:" in ci and "- main" in ci, ".github/workflows/ci.yml"),
        Check("CI does not request AWS credentials", "configure-aws-credentials" not in ci, "PR checks should not need cloud credentials"),
        Check("Docker build workflow is path-filtered", "paths:" in build and "dorny/paths-filter" in build, "build-images.yaml"),
        Check("Docker build workflow has manual rebuild", "workflow_dispatch:" in build, "build-images.yaml"),
        Check("Docker build workflow is not PR-triggered", "pull_request:" not in build, "build-images.yaml"),
        Check("Dev deploy is manual", "workflow_dispatch:" in deploy_dev and "Deploy DialChat to dev Kubernetes" in deploy_dev, "deploy-dev.yaml"),
        Check("Dev deploy requires runtime storage vars", has_all(deploy_dev, ["DIALEDIN_MEDIA_UPLOAD_BUCKET", "DIALEDIN_PROFILE_TABLE", "DIALEDIN_SHOT_RESULTS_TABLE"]), "deploy-dev.yaml"),
        Check(
            "Prod deploy is manually guarded",
            has_all(
                deploy_prod,
                [
                    "workflow_dispatch:",
                    "environment: production",
                    "inputs.confirm",
                    "deploy-prod",
                    "Confirm production deployment",
                ],
            ),
            "deploy-prod.yaml",
        ),
        Check(
            "Prod deploy applies production manifests only after confirmation",
            has_all(
                deploy_prod,
                [
                    "Apply production manifests",
                    "infra/k8s/ingress-prod.yaml",
                    "DIALEDIN_PROD_KUBE_CONFIG_B64",
                ],
            ),
            "deploy-prod.yaml",
        ),
    ]


def check_k8s() -> list[Check]:
    agent = read("infra/k8s/agent.yaml")
    ingress = read("infra/k8s/ingress.yaml")
    frontend = read("infra/k8s/frontend.yaml")
    espresso = read("infra/k8s/espresso-mcp.yaml")
    return [
        Check("Agent uses S3 media storage", "DIALEDIN_MEDIA_STORAGE_MODE: s3" in agent, "agent.yaml"),
        Check("Agent uses DynamoDB profile storage", "DIALEDIN_PROFILE_STORAGE: dynamodb" in agent, "agent.yaml"),
        Check("Agent uses DynamoDB shot history", "DIALEDIN_SHOT_HISTORY_STORAGE: dynamodb" in agent, "agent.yaml"),
        Check("Profile candidate email is enabled in cloud manifest", has_all(agent, ["PROFILE_CANDIDATE_EMAIL_ENABLED: \"true\"", "PROFILE_CANDIDATE_EMAIL_PROVIDER: ses", "support@dialedin.me"]), "agent.yaml"),
        Check("Agent has probes and resource limits", has_all(agent, ["readinessProbe:", "livenessProbe:", "resources:", "limits:"]), "agent.yaml"),
        Check("Frontend has probes and resource limits", has_all(frontend, ["readinessProbe:", "livenessProbe:", "resources:", "limits:"]), "frontend.yaml"),
        Check("Espresso MCP has probes and resource limits", has_all(espresso, ["readinessProbe:", "livenessProbe:", "resources:", "limits:"]), "espresso-mcp.yaml"),
        Check("Personal dev ingress hosts exist", has_all(ingress, ["api-dev.dialedin.me", "ai-dev.dialedin.me", "app-dev.dialedin.me"]), "ingress.yaml"),
        Check("Dev ingress is still HTTP-only", True, "HTTPS/ACM remains before production release", warning=True),
    ]


def uncommented(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        lines.append(line.split("#", 1)[0])
    return "\n".join(lines)


def check_terraform() -> list[Check]:
    variables = read("infra/terraform/variables.tf")
    prod = read("infra/terraform/prod.tfvars")
    prod_active = uncommented(prod)
    return [
        Check("Terraform has prod-safe bucket destroy default", "force_destroy_media_bucket" in variables and "default     = false" in variables, "variables.tf"),
        Check("Prod tfvars does not force-destroy media", re.search(r"force_destroy_media_bucket\s*=\s*false", prod) is not None, "prod.tfvars"),
        Check("Prod tfvars does not force-delete ECR", "force_delete_ecr_repositories = true" not in prod_active, "prod.tfvars"),
        Check(
            "Prod infrastructure is explicitly enabled",
            re.search(r"enable_k8s_cluster\s*=\s*true", prod_active) is not None
            and re.search(r"enable_public_ingress\s*=\s*true", prod_active) is not None,
            "prod.tfvars",
        ),
        Check("Terraform supports public ingress host override", "public_hostnames_override" in variables, "variables.tf"),
    ]


def check_docs() -> list[Check]:
    readme = read("README.md")
    plan = read("docs/plan.md")
    prod_doc = read("docs/production-readiness.md")
    return [
        Check("README has prod readiness checklist", "### Prod Readiness Checklist" in readme, "README.md"),
        Check("Dedicated production readiness doc exists", "# DialedIN Production Readiness" in prod_doc, "docs/production-readiness.md"),
        Check("Plan tracks Checkpoint 32", "## Checkpoint 32: Production Infrastructure Preparation" in plan, "docs/plan.md"),
        Check("Prod doc includes rollback", "Rollback" in prod_doc and "rollout undo" in prod_doc, "docs/production-readiness.md"),
        Check("Prod doc includes smoke tests", "Smoke" in prod_doc and "/health" in prod_doc, "docs/production-readiness.md"),
        Check("README has no older fursa.click examples", "fursa.click" not in readme, "README should prefer dialedin.me for personal-dev"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run static DialedIN production-readiness checks.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    args = parser.parse_args()

    checks = []
    checks.extend(check_required_files())
    checks.extend(check_ci())
    checks.extend(check_k8s())
    checks.extend(check_terraform())
    checks.extend(check_docs())

    failures = [check for check in checks if not check.ok and not check.warning]
    warnings = [check for check in checks if check.warning or (not check.ok and check.warning)]

    for check in checks:
        if check.warning:
            prefix = "WARN"
        else:
            prefix = "OK" if check.ok else "FAIL"
        print(f"[{prefix}] {check.name}: {check.detail}")

    if failures or (args.strict and warnings):
        print(f"\nProduction readiness check failed: {len(failures)} failure(s), {len(warnings)} warning(s).", file=sys.stderr)
        return 1

    print(f"\nProduction readiness check passed with {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
