# AWS OIDC Setup for GitHub Actions

Last updated: 2026-02-21
Purpose: Enable GitHub Actions to deploy to AWS without long-lived credentials

---

## Why OIDC?

**Problem**: Long-lived AWS access keys in GitHub secrets are a security risk.

**Solution**: GitHub Actions uses OIDC to assume an IAM role temporarily, no static credentials stored.

**Benefits**:
- No long-lived credentials to rotate
- Fine-grained permissions per workflow
- Audit trail via CloudTrail
- Automatic credential expiration

---

## Setup Steps

### Step 1 — Create OIDC Identity Provider in AWS

**Only needs to be done once per AWS account.**

```bash
# Set AWS profile
export AWS_PROFILE=navra-staging  # or navra-prod

# Create OIDC provider for GitHub Actions
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  --tags Key=Name,Value=GitHubActionsOIDC
```

**Verify**:
```bash
aws iam list-open-id-connect-providers
# Should show: arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com
```

---

### Step 2 — Create IAM Role for GitHub Actions

This role will be assumed by GitHub Actions to deploy to ECS.

**Trust Policy** (`github-actions-trust-policy.json`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::625847798833:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_ORG/autonomous-engineering-platform:environment:staging"
        }
      }
    }
  ]
}
```

**IMPORTANT**: Replace `YOUR_GITHUB_ORG` with your actual GitHub org/user (e.g., `NNDSrinivas` or `mounikakapa`).

**Create the role**:

```bash
# Create role
aws iam create-role \
  --role-name GitHubActionsDeployerStaging \
  --assume-role-policy-document file://github-actions-trust-policy.json \
  --description "Role for GitHub Actions to deploy to ECS staging" \
  --tags Key=Environment,Value=staging
```

**Record the ARN**:
```bash
aws iam get-role \
  --role-name GitHubActionsDeployerStaging \
  --query 'Role.Arn' \
  --output text

# Example output: arn:aws:iam::625847798833:role/GitHubActionsDeployerStaging
```

---

### Step 3 — Attach Permissions to Role

The role needs permissions to:
- Push images to ECR
- Register ECS task definitions
- Update ECS services
- Describe ECS services (for health checks)
- Describe ALB target groups (for health checks)
- Read CloudWatch logs (optional, for debugging)

**Permissions Policy** (`github-actions-permissions.json`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRPushAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:DescribeImages"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECSDeployAccess",
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeTaskDefinition",
        "ecs:RegisterTaskDefinition",
        "ecs:DescribeServices",
        "ecs:UpdateService",
        "ecs:ListTasks",
        "ecs:DescribeTasks"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "ecs:cluster": "arn:aws:ecs:us-east-1:625847798833:cluster/aep-staging"
        }
      }
    },
    {
      "Sid": "PassRoleToECS",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "arn:aws:iam::625847798833:role/ecsTaskExecutionRole",
        "arn:aws:iam::625847798833:role/aep-backend-task-role"
      ]
    },
    {
      "Sid": "ALBHealthCheckAccess",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogsAccess",
      "Effect": "Allow",
      "Action": [
        "logs:GetLogEvents",
        "logs:FilterLogEvents",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:aws:logs:us-east-1:625847798833:log-group:/ecs/aep-*:*"
    }
  ]
}
```

**Attach the policy**:

```bash
# Create policy
aws iam create-policy \
  --policy-name GitHubActionsDeployerStagingPolicy \
  --policy-document file://github-actions-permissions.json \
  --description "Permissions for GitHub Actions to deploy to ECS staging"

# Get policy ARN
POLICY_ARN=$(aws iam list-policies \
  --query 'Policies[?PolicyName==`GitHubActionsDeployerStagingPolicy`].Arn' \
  --output text)

# Attach policy to role
aws iam attach-role-policy \
  --role-name GitHubActionsDeployerStaging \
  --policy-arn $POLICY_ARN
```

---

### Step 4 — Configure GitHub Secrets

In your GitHub repository:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Create a new **environment** called `staging`
3. Add the following **environment secret**:

| Name | Value |
|------|-------|
| `AWS_ROLE_ARN_STAGING` | `arn:aws:iam::625847798833:role/GitHubActionsDeployerStaging` |

**Why environment-level?**
- Allows different roles for staging vs production
- Better security isolation
- Required approval workflows (optional)

---

### Step 5 — Test the Setup

**Create a test workflow** (`.github/workflows/test-oidc.yml`):

```yaml
name: Test AWS OIDC

on:
  workflow_dispatch:  # Manual trigger only

permissions:
  id-token: write
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN_STAGING }}
          aws-region: us-east-1

      - name: Test AWS access
        run: |
          echo "Testing AWS access..."
          aws sts get-caller-identity
          aws ecr describe-repositories --repository-names navralabs/aep-backend
          aws ecs describe-clusters --clusters aep-staging
          echo "✅ OIDC setup successful!"
```

**Run the test**:
1. Go to **Actions** tab in GitHub
2. Select **Test AWS OIDC** workflow
3. Click **Run workflow**
4. Verify output shows correct AWS account and permissions

---

## Troubleshooting

### Error: "Not authorized to perform sts:AssumeRoleWithWebIdentity"

**Cause**: Trust policy doesn't match GitHub repo.

**Fix**: Update trust policy to include correct repo:
```bash
# Get current trust policy
aws iam get-role --role-name GitHubActionsDeployerStaging --query 'Role.AssumeRolePolicyDocument'

# Update the StringLike condition:
"token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/autonomous-engineering-platform:*"
```

### Error: "An error occurred (AccessDenied) when calling the UpdateService operation"

**Cause**: IAM policy too restrictive or missing PassRole.

**Fix**: Ensure policy includes:
- `ecs:UpdateService`
- `iam:PassRole` for task execution role and task role

### Error: "OIDC provider not found"

**Cause**: OIDC provider not created in AWS.

**Fix**: Run Step 1 again to create OIDC provider.

---

## Security Best Practices

1. **Restrict by branch**:
   ```json
   "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/autonomous-engineering-platform:ref:refs/heads/main"
   ```
   This only allows deploys from `main` branch.

2. **Restrict by environment**:
   ```json
   "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/autonomous-engineering-platform:environment:staging"
   ```
   This requires GitHub environment protection rules.

3. **Separate roles per environment**:
   - `GitHubActionsDeployerStaging` → staging cluster only
   - `GitHubActionsDeployerProduction` → production cluster only

4. **Monitor CloudTrail**:
   ```bash
   aws cloudtrail lookup-events \
     --lookup-attributes AttributeKey=Username,AttributeValue=GitHubActionsDeployerStaging
   ```

---

## Production Setup (When Ready)

When setting up production:

1. Create production OIDC role:
   ```bash
   aws iam create-role \
     --role-name GitHubActionsDeployerProduction \
     --assume-role-policy-document file://github-actions-trust-policy-prod.json \
     --profile navra-prod
   ```

2. Attach production-scoped policy (replace `aep-staging` with `aep-prod`)

3. Add GitHub environment secret:
   - Environment: `production`
   - Secret: `AWS_ROLE_ARN_PRODUCTION`
   - Value: `arn:aws:iam::<prod-account-id>:role/GitHubActionsDeployerProduction`

4. Duplicate workflows with `environment: production`

---

## Quick Reference

```bash
# View role
aws iam get-role --role-name GitHubActionsDeployerStaging

# View attached policies
aws iam list-attached-role-policies --role-name GitHubActionsDeployerStaging

# View OIDC providers
aws iam list-open-id-connect-providers

# Test assume role (from local)
aws sts assume-role-with-web-identity \
  --role-arn arn:aws:iam::625847798833:role/GitHubActionsDeployerStaging \
  --role-session-name test \
  --web-identity-token <token>
```

---

## Exit Criteria

OIDC setup is complete when:

- [ ] OIDC provider created in AWS
- [ ] IAM role `GitHubActionsDeployerStaging` exists
- [ ] Trust policy allows your GitHub repo
- [ ] Permissions policy attached to role
- [ ] GitHub secret `AWS_ROLE_ARN_STAGING` configured
- [ ] Test workflow runs successfully
- [ ] `aws sts get-caller-identity` returns expected role ARN in workflow logs

Once complete, your GitHub Actions workflows can deploy to AWS without storing any credentials.
