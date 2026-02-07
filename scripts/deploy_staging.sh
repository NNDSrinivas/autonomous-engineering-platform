#!/bin/bash
# NAVI Staging Deployment Script
# Deploys NAVI to staging Kubernetes environment with validation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   NAVI Staging Deployment                 ║${NC}"
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo ""

# Configuration
NAMESPACE="navi-staging"
KUBECTL_CONTEXT="${KUBECTL_CONTEXT:-staging}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-your-registry}"

# Step 1: Validate prerequisites
echo -e "${YELLOW}Step 1: Validating prerequisites...${NC}"

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}ERROR: kubectl is not installed${NC}"
    exit 1
fi

# Check if we can connect to the cluster
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}ERROR: Cannot connect to Kubernetes cluster${NC}"
    echo "Please ensure your kubeconfig is configured correctly"
    exit 1
fi

# Switch to staging context
echo "Switching to staging context: $KUBECTL_CONTEXT"
kubectl config use-context "$KUBECTL_CONTEXT" || {
    echo -e "${RED}ERROR: Failed to switch to staging context${NC}"
    exit 1
}

echo -e "${GREEN}✓ Prerequisites validated${NC}"
echo ""

# Step 2: Create namespace if it doesn't exist
echo -e "${YELLOW}Step 2: Ensuring namespace exists...${NC}"
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo "Creating namespace: $NAMESPACE"
    kubectl create namespace "$NAMESPACE"
    kubectl label namespace "$NAMESPACE" environment=staging
else
    echo "Namespace already exists: $NAMESPACE"
fi
echo -e "${GREEN}✓ Namespace ready${NC}"
echo ""

# Step 3: Validate required secrets
echo -e "${YELLOW}Step 3: Validating required secrets...${NC}"

REQUIRED_SECRETS=(
    "navi-database-staging"
    "navi-backend-secrets"
)

MISSING_SECRETS=()
for secret in "${REQUIRED_SECRETS[@]}"; do
    if ! kubectl get secret "$secret" -n "$NAMESPACE" &> /dev/null; then
        MISSING_SECRETS+=("$secret")
    fi
done

if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
    echo -e "${RED}ERROR: The following required secrets are missing:${NC}"
    for secret in "${MISSING_SECRETS[@]}"; do
        echo "  - $secret"
    done
    echo ""
    echo "Please create the secrets before deploying:"
    echo ""
    echo "For database credentials:"
    echo "  kubectl create secret generic navi-database-staging \\"
    echo "    --from-literal=DATABASE_URL='postgresql+psycopg2://user:password@host:5432/dbname' \\"
    echo "    --namespace $NAMESPACE"
    echo ""
    echo "For backend secrets (including AUDIT_ENCRYPTION_KEY):"
    echo "  # First, generate encryption key:"
    echo "  python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    echo ""
    echo "  # Then create the secret:"
    echo "  kubectl create secret generic navi-backend-secrets \\"
    echo "    --from-literal=AUDIT_ENCRYPTION_KEY='<generated-key>' \\"
    echo "    --from-literal=JWT_SECRET='<jwt-secret>' \\"
    echo "    --from-literal=OPENAI_API_KEY='<openai-key>' \\"
    echo "    --namespace $NAMESPACE"
    echo ""
    echo "Or apply from template files:"
    echo "  kubectl apply -f kubernetes/secrets/database-staging.yaml"
    echo "  kubectl apply -f kubernetes/secrets/backend-secrets-staging.yaml"
    exit 1
fi

# Validate AUDIT_ENCRYPTION_KEY exists in secret
echo "Validating AUDIT_ENCRYPTION_KEY..."
if ! kubectl get secret navi-backend-secrets -n "$NAMESPACE" -o jsonpath='{.data.AUDIT_ENCRYPTION_KEY}' | base64 -d | grep -q .; then
    echo -e "${RED}ERROR: AUDIT_ENCRYPTION_KEY is missing or empty in navi-backend-secrets${NC}"
    echo "This is MANDATORY for staging/production environments."
    echo ""
    echo "To fix:"
    echo "  1. Generate a key: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    echo "  2. Update the secret:"
    echo "     kubectl patch secret navi-backend-secrets -n $NAMESPACE \\"
    echo "       --type='json' -p='[{\"op\":\"add\",\"path\":\"/data/AUDIT_ENCRYPTION_KEY\",\"value\":\"<base64-encoded-key>\"}]'"
    exit 1
fi

echo -e "${GREEN}✓ All required secrets validated${NC}"
echo ""

# Step 4: Apply ConfigMaps
echo -e "${YELLOW}Step 4: Applying ConfigMaps...${NC}"
kubectl apply -f kubernetes/secrets/database-staging.yaml
kubectl apply -f kubernetes/secrets/backend-secrets-staging.yaml
echo -e "${GREEN}✓ ConfigMaps applied${NC}"
echo ""

# Step 5: Deploy backend
echo -e "${YELLOW}Step 5: Deploying backend...${NC}"

# Update image tag in deployment
sed "s|image: your-registry/navi-backend:staging|image: $REGISTRY/navi-backend:$IMAGE_TAG|g" \
    kubernetes/deployments/backend-staging.yaml | kubectl apply -f -

echo -e "${GREEN}✓ Backend deployment created/updated${NC}"
echo ""

# Step 6: Wait for deployment to be ready
echo -e "${YELLOW}Step 6: Waiting for deployment to be ready...${NC}"
echo "This may take a few minutes for database migrations to complete..."

if kubectl rollout status deployment/navi-backend -n "$NAMESPACE" --timeout=300s; then
    echo -e "${GREEN}✓ Deployment is ready${NC}"
else
    echo -e "${RED}ERROR: Deployment failed to become ready${NC}"
    echo ""
    echo "Checking pod logs for errors..."
    kubectl logs -n "$NAMESPACE" -l app=navi,component=backend --tail=50
    exit 1
fi
echo ""

# Step 7: Validate deployment
echo -e "${YELLOW}Step 7: Validating deployment...${NC}"

# Check if pods are running
RUNNING_PODS=$(kubectl get pods -n "$NAMESPACE" -l app=navi,component=backend -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}' | wc -w)
DESIRED_REPLICAS=$(kubectl get deployment navi-backend -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')

if [ "$RUNNING_PODS" -lt "$DESIRED_REPLICAS" ]; then
    echo -e "${RED}ERROR: Not all pods are running${NC}"
    echo "Running: $RUNNING_PODS / Desired: $DESIRED_REPLICAS"
    kubectl get pods -n "$NAMESPACE" -l app=navi,component=backend
    exit 1
fi

# Check health endpoint
echo "Checking health endpoint..."
kubectl port-forward -n "$NAMESPACE" deployment/navi-backend 8787:8787 &
PORT_FORWARD_PID=$!
sleep 3

if curl -f -s http://localhost:8787/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}ERROR: Health check failed${NC}"
    kill $PORT_FORWARD_PID 2>/dev/null || true
    exit 1
fi

# Check for audit encryption validation errors
echo "Checking for audit encryption errors in logs..."
if kubectl logs -n "$NAMESPACE" -l app=navi,component=backend --tail=100 | grep -i "AUDIT_ENCRYPTION_KEY is REQUIRED"; then
    echo -e "${RED}ERROR: Audit encryption validation failed${NC}"
    echo "Backend is failing because AUDIT_ENCRYPTION_KEY is not set properly"
    kill $PORT_FORWARD_PID 2>/dev/null || true
    exit 1
fi

kill $PORT_FORWARD_PID 2>/dev/null || true

echo -e "${GREEN}✓ Deployment validated successfully${NC}"
echo ""

# Step 8: Display deployment info
echo -e "${YELLOW}Step 8: Deployment Summary${NC}"
echo ""
echo "Namespace:  $NAMESPACE"
echo "Context:    $KUBECTL_CONTEXT"
echo "Image:      $REGISTRY/navi-backend:$IMAGE_TAG"
echo "Replicas:   $RUNNING_PODS / $DESIRED_REPLICAS"
echo ""
echo "Pods:"
kubectl get pods -n "$NAMESPACE" -l app=navi,component=backend
echo ""
echo "Services:"
kubectl get svc -n "$NAMESPACE" -l app=navi,component=backend
echo ""

# Step 9: Post-deployment validation checklist
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Post-Deployment Validation Checklist    ║${NC}"
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo ""
echo "Run the following commands to validate the deployment:"
echo ""
echo "1. Check pod logs:"
echo "   kubectl logs -n $NAMESPACE -l app=navi,component=backend --tail=100"
echo ""
echo "2. Check health endpoints:"
echo "   kubectl port-forward -n $NAMESPACE deployment/navi-backend 8787:8787"
echo "   curl http://localhost:8787/health"
echo "   curl http://localhost:8787/health/ready"
echo "   curl http://localhost:8787/health/live"
echo ""
echo "3. Check database migrations:"
echo "   kubectl exec -n $NAMESPACE deployment/navi-backend -- alembic current"
echo ""
echo "4. Test NAVI chat endpoint:"
echo "   curl -X POST http://localhost:8787/api/navi/chat/stream \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"message\":\"Hello NAVI\",\"mode\":\"agent\",\"workspace_root\":\"/tmp\"}'"
echo ""
echo "5. Check audit encryption:"
echo "   kubectl exec -n $NAMESPACE deployment/navi-backend -- \\"
echo "     python -c 'import os; print(\"AUDIT_ENCRYPTION_KEY:\", \"SET\" if os.getenv(\"AUDIT_ENCRYPTION_KEY\") else \"MISSING\")'"
echo ""

echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Deployment Completed Successfully! 🎉   ║${NC}"
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
