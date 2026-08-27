#!/bin/bash
set -e

# VocabTrainer Deployment Script
# Usage: ./deploy.sh [dev|prod]

ENVIRONMENT="${1:-dev}"
REGION="eu-central-1"
STACK_NAME="vocabtrainer-${ENVIRONMENT}"

# Optional: custom domain config (set these env vars or create backend/.env.deploy)
DEPLOY_ENV_FILE="$(dirname "$0")/backend/.env.deploy"
if [ -f "${DEPLOY_ENV_FILE}" ]; then
  source "${DEPLOY_ENV_FILE}"
fi
CERTIFICATE_ARN="${CERTIFICATE_ARN:-}"
HOSTED_ZONE_ID="${HOSTED_ZONE_ID:-}"

echo "🚀 Deploying VocabTrainer (${ENVIRONMENT}) to ${REGION}"
echo "=================================================="

# ─── Backend ───────────────────────────────────────────────

echo ""
echo "📦 Building backend..."
cd "$(dirname "$0")/backend"

# Use container build for arm64 native dependencies (python-Levenshtein etc.)
sam build --use-container

echo ""
echo "☁️  Deploying backend stack..."
# Build parameter overrides (only include non-empty values)
PARAM_OVERRIDES="Environment=${ENVIRONMENT}"
if [ -n "${CERTIFICATE_ARN}" ]; then
  PARAM_OVERRIDES="${PARAM_OVERRIDES} CertificateArn=${CERTIFICATE_ARN}"
fi
if [ -n "${HOSTED_ZONE_ID}" ]; then
  PARAM_OVERRIDES="${PARAM_OVERRIDES} HostedZoneId=${HOSTED_ZONE_ID}"
fi

sam deploy \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --parameter-overrides ${PARAM_OVERRIDES} \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --tags "Project=VocabTrainer" "Environment=${ENVIRONMENT}"

# ─── Get Stack Outputs ─────────────────────────────────────

echo ""
echo "📋 Reading stack outputs..."

get_output() {
  aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
    --output text
}

API_ENDPOINT=$(get_output "ApiEndpoint")
USER_POOL_ID=$(get_output "UserPoolId")
CLIENT_ID=$(get_output "UserPoolClientId")
USER_POOL_DOMAIN=$(get_output "UserPoolDomain")
FRONTEND_BUCKET=$(get_output "FrontendBucketName")
FRONTEND_URL=$(get_output "FrontendUrl")
CLOUDFRONT_ID=$(get_output "CloudFrontDistributionId")

echo "  API:        ${API_ENDPOINT}"
echo "  Frontend:   ${FRONTEND_URL}"
echo "  Cognito:    ${USER_POOL_DOMAIN}"
echo "  Bucket:     ${FRONTEND_BUCKET}"
echo "  CF Dist:    ${CLOUDFRONT_ID}"

# ─── Frontend ──────────────────────────────────────────────

echo ""
echo "📦 Building frontend..."
cd "$(dirname "$0")/../frontend"

# Write .env for this build
cat > .env.production.local <<EOF
VITE_API_BASE_URL=${API_ENDPOINT}
VITE_COGNITO_DOMAIN=${USER_POOL_DOMAIN}
VITE_COGNITO_CLIENT_ID=${CLIENT_ID}
VITE_COGNITO_REDIRECT_URI=${FRONTEND_URL}/callback
VITE_COGNITO_LOGOUT_URI=${FRONTEND_URL}
VITE_AWS_REGION=${REGION}
VITE_COGNITO_USER_POOL_ID=${USER_POOL_ID}
VITE_APP_VERSION=${VITE_APP_VERSION:-$(git describe --tags --always 2>/dev/null || git rev-parse --short HEAD)}
EOF

npm ci --silent
npm run build

echo ""
echo "☁️  Uploading frontend to S3..."
aws s3 sync dist/ "s3://${FRONTEND_BUCKET}" \
  --delete \
  --region "${REGION}"

echo ""
echo "🔄 Invalidating CloudFront cache..."
aws cloudfront create-invalidation \
  --distribution-id "${CLOUDFRONT_ID}" \
  --paths "/*" \
  --region "${REGION}" \
  --output text --query 'Invalidation.Id'

# ─── Done ──────────────────────────────────────────────────

echo ""
echo "✅ Deployment complete!"
echo ""
echo "   Frontend: ${FRONTEND_URL}"
echo "   API:      ${API_ENDPOINT}"
if [ -n "${CERTIFICATE_ARN}" ] && [ -n "${HOSTED_ZONE_ID}" ]; then
  CUSTOM_DOMAIN=$(get_output "CustomDomain")
  echo "   Domain:   https://${CUSTOM_DOMAIN}"
fi
echo ""
