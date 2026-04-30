#!/usr/bin/env bash
# Promote a Cognito user to the 'admin' group on a given stage.
#
# Usage:
#   ./scripts/promote-admin.sh <stage> <email>
#
# <stage> is one of dev|staging|prod (matches the SSM parameter prefix).
# <email> is the user's email (Cognito uses email as username).
#
# Prerequisite: the user has already registered + confirmed their email
# via the frontend AuthModal on this stage. This script only adds them
# to the 'admin' group; it does not create the user.
#
# Idempotent: re-running on an already-admin user is a no-op.
#
# Reads the user pool ID from SSM:
#   /datasheetminer/<stage>/cognito/user-pool-id
# (set by AuthStack at deploy time). If you renamed the SSM prefix,
# update SSM_PREFIX below.

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <stage> <email>" >&2
  echo "  stage: dev|staging|prod" >&2
  exit 64
fi

STAGE="$1"
EMAIL="$2"

case "$STAGE" in
  dev|staging|prod) ;;
  *)
    echo "error: stage must be one of dev|staging|prod (got '$STAGE')" >&2
    exit 64
    ;;
esac

SSM_PREFIX="/datasheetminer/${STAGE}"
POOL_PARAM="${SSM_PREFIX}/cognito/user-pool-id"

echo "[promote-admin] stage=$STAGE email=$EMAIL"
echo "[promote-admin] looking up pool ID at $POOL_PARAM"

POOL_ID=$(aws ssm get-parameter \
  --name "$POOL_PARAM" \
  --query 'Parameter.Value' \
  --output text)

if [[ -z "$POOL_ID" ]]; then
  echo "error: empty pool ID returned from SSM. Did AuthStack deploy on $STAGE?" >&2
  exit 1
fi

echo "[promote-admin] pool=$POOL_ID"
echo "[promote-admin] adding $EMAIL to 'admin' group"

aws cognito-idp admin-add-user-to-group \
  --user-pool-id "$POOL_ID" \
  --username "$EMAIL" \
  --group-name admin

echo "[promote-admin] verifying group membership"
aws cognito-idp admin-list-groups-for-user \
  --user-pool-id "$POOL_ID" \
  --username "$EMAIL" \
  --query 'Groups[].GroupName' \
  --output text

echo "[promote-admin] done. $EMAIL must log out + back in for the new"
echo "                 group to appear in their token (existing tokens"
echo "                 don't reflect group membership until refresh)."
