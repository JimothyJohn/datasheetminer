#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$ROOT_DIR/.logs"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

fail() { echo -e "${RED}ERROR: $*${NC}" >&2; exit 1; }
info() { echo -e "${GREEN}==> $*${NC}"; }
warn() { echo -e "${YELLOW}    $*${NC}"; }

mkdir -p "$LOG_DIR"

# ── Load config ──────────────────────────────────────────────────

if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

REGION="${AWS_REGION:-us-east-1}"
ECR_REPO="datasheetminer"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# ── Validate prerequisites ───────────────────────────────────────

info "Validating prerequisites"

command -v docker >/dev/null 2>&1 || fail "docker not found"
command -v aws >/dev/null 2>&1    || fail "aws CLI not found"

# Verify AWS credentials
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) \
  || fail "AWS credentials not configured. Run: aws configure"

ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"
GIT_SHA=$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo "  Account:  $ACCOUNT_ID"
echo "  Region:   $REGION"
echo "  Repo:     $ECR_REPO"
echo "  Commit:   $GIT_SHA"

# ── Create ECR repository if needed ──────────────────────────────

info "Checking ECR repository"

if ! aws ecr describe-repositories \
    --repository-names "$ECR_REPO" \
    --region "$REGION" >/dev/null 2>&1; then
  info "Creating ECR repository: $ECR_REPO"
  aws ecr create-repository \
    --repository-name "$ECR_REPO" \
    --region "$REGION" \
    --image-scanning-configuration scanOnPush=true \
    --image-tag-mutability MUTABLE \
    > "$LOG_DIR/ecr-create.log" 2>&1
fi

# ── Authenticate Docker to ECR ───────────────────────────────────

info "Authenticating Docker to ECR"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin \
    "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com" \
  > "$LOG_DIR/ecr-login.log" 2>&1

# ── Build Docker image ───────────────────────────────────────────

info "Building Docker image"

docker build \
  -t "${ECR_REPO}:latest" \
  -t "${ECR_REPO}:${GIT_SHA}" \
  -f "$SCRIPT_DIR/Dockerfile" \
  "$SCRIPT_DIR" \
  2>&1 | tee "$LOG_DIR/docker-build.log"

# ── Tag and push ─────────────────────────────────────────────────

info "Pushing to ECR"

docker tag "${ECR_REPO}:latest" "${ECR_URI}:latest"
docker tag "${ECR_REPO}:${GIT_SHA}" "${ECR_URI}:${GIT_SHA}"

docker push "${ECR_URI}:latest" 2>&1 | tee "$LOG_DIR/docker-push.log"
docker push "${ECR_URI}:${GIT_SHA}" 2>&1 | tee -a "$LOG_DIR/docker-push.log"

# ── Done ─────────────────────────────────────────────────────────

echo ""
info "Image pushed successfully"
echo "  URI:      ${ECR_URI}:latest"
echo "  SHA tag:  ${ECR_URI}:${GIT_SHA}"
echo "  Logs:     $LOG_DIR/"
echo ""
info "Deploy with AWS App Runner:"
echo "  aws apprunner create-service \\"
echo "    --service-name datasheetminer \\"
echo "    --source-configuration '{\"ImageRepository\":{\"ImageIdentifier\":\"${ECR_URI}:latest\",\"ImageRepositoryType\":\"ECR\",\"ImageConfiguration\":{\"Port\":\"3001\",\"RuntimeEnvironmentVariables\":{\"AWS_REGION\":\"${REGION}\",\"DYNAMODB_TABLE_NAME\":\"${DYNAMODB_TABLE_NAME:-products}\",\"NODE_ENV\":\"production\"}}}}' \\"
echo "    --instance-configuration '{\"Cpu\":\"1024\",\"Memory\":\"2048\"}' \\"
echo "    --region $REGION"
echo ""
info "Or run locally:"
echo "  docker run -p 3001:3001 \\"
echo "    -e AWS_REGION=$REGION \\"
echo "    -e DYNAMODB_TABLE_NAME=${DYNAMODB_TABLE_NAME:-products} \\"
echo "    -e AWS_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID \\"
echo "    -e AWS_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY \\"
echo "    ${ECR_REPO}:latest"
echo ""
