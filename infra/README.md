# Infra Automation (Local/K8s/Cloud)

This folder provides deployment parity across local, Kubernetes, and cloud.

## Local (Docker Compose)
- Deploy: `./scripts/infra/deploy_local.sh`
- Verify: `./scripts/infra/verify_local.sh http://localhost:8000/health`
- Rollback: `./scripts/infra/rollback_local.sh`

## Kubernetes (manifests)
- Manifests in `k8s/`
- Deploy: `./scripts/infra/deploy_k8s.sh`
- Verify: `./scripts/infra/verify_k8s.sh`
- Rollback: `./scripts/infra/rollback_k8s.sh`

## AWS (Terraform + ECS Fargate)
- Terraform in `infra/terraform/aws`
- Deploy: `./scripts/infra/deploy_aws_terraform.sh`
- Verify: `./scripts/infra/verify_aws.sh` (uses ALB DNS output)
- Rollback: `./scripts/infra/rollback_aws_terraform.sh`

Notes:
- RDS/Redis provisioning is optional in Terraform (`enable_rds`, `enable_redis`).
- For production, move databases to private subnets and disable public access.
