#!/usr/bin/env bash
#
# Deploy DatasheetMiner to AWS
# Stacks: DynamoDB + API Gateway/Lambda + S3/CloudFront
#
# Prerequisites:
#   - AWS CLI configured (aws configure)
#   - Node.js 18+
#   - CDK bootstrapped in target account (npx cdk bootstrap)
#
# Required env vars:
#   AWS_ACCOUNT_ID  - Your AWS account ID
#   AWS_REGION      - Target region (default: us-east-1)
#
# Optional env vars:
#   DYNAMODB_TABLE_NAME - DynamoDB table name (default: products)
#   DOMAIN_NAME         - Custom domain (requires CERTIFICATE_ARN, HOSTED_ZONE_ID)
#
# Usage:
#   export AWS_ACCOUNT_ID=123456789012
#   ./deploy-aws.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[deploy]${NC} $*"; }
ok()   { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[deploy]${NC} $*"; }
err()  { echo -e "${RED}[deploy]${NC} $*" >&2; }

# Validate prerequisites
check_prereqs() {
  log "Checking prerequisites..."

  if ! command -v node &>/dev/null; then
    err "Node.js not found. Install Node.js 18+."
    exit 1
  fi

  if ! command -v aws &>/dev/null; then
    err "AWS CLI not found. Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
  fi

  if ! aws sts get-caller-identity &>/dev/null; then
    err "AWS credentials not configured. Run: aws configure"
    exit 1
  fi

  if [ -z "${AWS_ACCOUNT_ID:-}" ]; then
    # Try to get from AWS CLI
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)
    if [ -z "$AWS_ACCOUNT_ID" ]; then
      err "AWS_ACCOUNT_ID not set. Export it or configure AWS CLI."
      exit 1
    fi
    export AWS_ACCOUNT_ID
    log "Auto-detected AWS_ACCOUNT_ID: $AWS_ACCOUNT_ID"
  fi

  export AWS_REGION="${AWS_REGION:-us-east-1}"
  export CDK_DEFAULT_ACCOUNT="$AWS_ACCOUNT_ID"
  export CDK_DEFAULT_REGION="$AWS_REGION"

  # Stage controls resource naming (dev/staging/prod)
  export STAGE="${STAGE:-dev}"
  if [[ "$STAGE" == "dev" ]]; then
    warn "STAGE=dev (default). Set STAGE=prod for production deployments."
  fi

  ok "Prerequisites OK (Account: $AWS_ACCOUNT_ID, Region: $AWS_REGION, Stage: $STAGE)"
}

# Install all workspace dependencies (hoists to app/node_modules)
install_deps() {
  log "Installing all workspace dependencies..."
  cd "$SCRIPT_DIR"
  npm install --silent
  ok "Dependencies installed"
}

# Build frontend
build_frontend() {
  log "Building frontend (public mode — admin UI excluded)..."
  cd "$SCRIPT_DIR/frontend"
  VITE_API_URL="" VITE_APP_MODE=public npm run build
  ok "Frontend built -> frontend/dist/"
  cd "$SCRIPT_DIR"
}

# Deploy CDK stacks
deploy_stacks() {
  log "Bootstrapping CDK (if needed)..."
  cd "$SCRIPT_DIR/infrastructure"
  npx cdk bootstrap "aws://$AWS_ACCOUNT_ID/$AWS_REGION" 2>&1 | grep -v "^$" || true

  log "Deploying all stacks..."
  npx cdk deploy --all --require-approval never --outputs-file cdk-outputs.json 2>&1

  ok "CDK stacks deployed"
  cd "$SCRIPT_DIR"
}

# Invalidate CloudFront cache explicitly — belt-and-suspenders alongside
# the CDK BucketDeployment invalidation. Waits for completion so the
# deploy script doesn't report success while stale content is still served.
invalidate_cache() {
  local outputs_file="$SCRIPT_DIR/infrastructure/cdk-outputs.json"
  if [ ! -f "$outputs_file" ]; then
    warn "No cdk-outputs.json — skipping cache invalidation"
    return
  fi

  local dist_id
  dist_id=$(python3 -c "
import json
with open('$outputs_file') as f:
    data = json.load(f)
for stack in data.values():
    for key, val in stack.items():
        if 'DistributionId' in key:
            print(val)
            break
" 2>/dev/null || echo "")

  if [ -z "$dist_id" ]; then
    warn "Could not find CloudFront Distribution ID — skipping invalidation"
    return
  fi

  log "Invalidating CloudFront cache (distribution: $dist_id)..."
  local inv_id
  inv_id=$(aws cloudfront create-invalidation \
    --distribution-id "$dist_id" \
    --paths "/*" \
    --query 'Invalidation.Id' \
    --output text 2>&1)

  if [ $? -ne 0 ]; then
    warn "Cache invalidation request failed: $inv_id"
    return
  fi

  log "Waiting for invalidation $inv_id to complete..."
  aws cloudfront wait invalidation-completed \
    --distribution-id "$dist_id" \
    --id "$inv_id" 2>&1

  ok "CloudFront cache invalidated"
}

# Print access info
print_info() {
  local outputs_file="$SCRIPT_DIR/infrastructure/cdk-outputs.json"
  if [ -f "$outputs_file" ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  DatasheetMiner deployed successfully  ${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    # Extract CloudFront URL
    local cf_url
    cf_url=$(python3 -c "
import json
with open('$outputs_file') as f:
    data = json.load(f)
for stack in data.values():
    for key, val in stack.items():
        if 'CloudFrontUrl' in key:
            print(val)
            break
" 2>/dev/null || echo "")

    local api_url
    api_url=$(python3 -c "
import json
with open('$outputs_file') as f:
    data = json.load(f)
for stack in data.values():
    for key, val in stack.items():
        if 'ApiEndpoint' in key:
            print(val)
            break
" 2>/dev/null || echo "")

    local site_url
    site_url=$(python3 -c "
import json
with open('$outputs_file') as f:
    data = json.load(f)
for stack in data.values():
    for key, val in stack.items():
        if 'SiteUrl' in key:
            print(val)
            break
" 2>/dev/null || echo "")

    if [ -n "$site_url" ]; then
      echo -e "  App URL:      ${GREEN}$site_url${NC}"
      echo -e "  CloudFront:   ${BLUE}$cf_url${NC}"
    elif [ -n "$cf_url" ]; then
      echo -e "  App URL:      ${GREEN}$cf_url${NC}"
    fi
    if [ -n "$api_url" ]; then
      echo -e "  API URL:      ${BLUE}$api_url${NC}"
    fi
    echo -e "  Region:       $AWS_REGION"
    echo -e "  Account:      $AWS_ACCOUNT_ID"
    echo ""
    local health_base="${site_url:-$cf_url}"
    echo -e "  Health check: ${BLUE}${health_base}/health${NC}"
    echo ""
  fi
}

# Main
main() {
  echo ""
  log "Starting DatasheetMiner AWS deployment"
  echo ""

  check_prereqs
  install_deps
  build_frontend
  deploy_stacks
  invalidate_cache
  print_info
}

main "$@"
