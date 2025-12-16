#!/usr/bin/env bash
set -euo pipefail

########################################
# CONFIG – EDIT THESE 4 VALUES
########################################

# Your AWS account + region
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="746955692116"

# Name of ECR repo & App Runner service
ECR_REPO_NAME="aep-backend"
APP_RUNNER_SERVICE_ARN="arn:aws:apprunner:us-east-1:746955692116:service/aep-backend/xxxxxxxxxxxx"

########################################
# Derived values – usually no need to edit
########################################

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
IMAGE_TAG="$TIMESTAMP"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${IMAGE_TAG}"

echo "=== AEP Deploy Script ==="
echo "Region:      ${AWS_REGION}"
echo "Account:     ${AWS_ACCOUNT_ID}"
echo "ECR repo:    ${ECR_REPO_NAME}"
echo "Image tag:   ${IMAGE_TAG}"
echo "Image URI:   ${ECR_URI}"
echo "App Runner:  ${APP_RUNNER_SERVICE_ARN}"
echo

########################################
# 1. Ensure ECR repo exists
########################################

echo "[1/5] Ensuring ECR repository exists..."
if ! aws ecr describe-repositories --repository-names "${ECR_REPO_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  echo "ECR repo not found, creating..."
  aws ecr create-repository \
    --repository-name "${ECR_REPO_NAME}" \
    --image-scanning-configuration scanOnPush=true \
    --region "${AWS_REGION}" >/dev/null
else
  echo "ECR repo already exists."
fi
echo

########################################
# 2. Login to ECR
########################################

echo "[2/5] Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login \
      --username AWS \
      --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
echo

########################################
# 3. Build Docker image
########################################

echo "[3/5] Building Docker image..."
docker build -t "${ECR_REPO_NAME}:${IMAGE_TAG}" .

# Tag with full ECR URI
docker tag "${ECR_REPO_NAME}:${IMAGE_TAG}" "${ECR_URI}"
echo

########################################
# 4. Push to ECR
########################################

echo "[4/5] Pushing image to ECR..."
docker push "${ECR_URI}"
echo

########################################
# 5. Update App Runner service
########################################

echo "[5/5] Updating App Runner service to new image..."

aws apprunner update-service \
  --service-arn "${APP_RUNNER_SERVICE_ARN}" \
  --source-configuration "ImageRepository={
    ImageIdentifier=\"${ECR_URI}\",
    ImageRepositoryType=\"ECR\"
  }" \
  --region "${AWS_REGION}" >/dev/null

echo
echo "✅ Deployment triggered. App Runner will pull the new image in ~1–2 minutes."
echo "   New image: ${ECR_URI}"
echo
echo "You can check status in the AWS Console → App Runner → aep-backend."
echo "Or check deployment status with:"
echo "  aws apprunner list-services --region ${AWS_REGION}"
echo "  aws apprunner describe-service --service-arn ${APP_RUNNER_SERVICE_ARN} --region ${AWS_REGION}"