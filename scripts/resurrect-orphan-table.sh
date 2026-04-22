#!/usr/bin/env bash
# Re-adopt an orphaned DynamoDB products-<stage> table into its CDK stack.
#
# When the database stack is deleted and recreated but the table survives
# via removalPolicy: RETAIN (prod default), `cdk deploy` trips over
# CREATE_FAILED — the logical resource can't be created because a table
# with that name already exists. This script runs `cdk import` to bring
# the live table under the new stack's management, after which a normal
# deploy picks up from there.
#
# Usage: scripts/resurrect-orphan-table.sh [--stage STAGE] [--dry-run]

set -euo pipefail

STAGE="prod"
DRY_RUN=0
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--stage dev|staging|prod] [--dry-run]

Re-adopts DynamoDB table 'products-<stage>' into
'DatasheetMiner-<Stage>-Database' via 'cdk import'. Use after the
database stack was deleted/recreated while the table survived (prod
removalPolicy: RETAIN).

Options:
  --stage STAGE   dev | staging | prod (default: prod)
  --dry-run       Print plan + import mapping; skip 'cdk import'.
  -h, --help      Show this help.

Stage env is loaded from app/.env.<stage> (same as './Quickstart deploy').
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage)   STAGE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$STAGE" in dev|staging|prod) ;; *)
  echo "ERROR: --stage must be dev, staging, or prod (got: $STAGE)" >&2; exit 2 ;;
esac

ENV_FILE="$REPO_ROOT/app/.env.$STAGE"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
fi

if [[ -z "${AWS_ACCOUNT_ID:-}${CDK_DEFAULT_ACCOUNT:-}" ]]; then
  echo "ERROR: AWS_ACCOUNT_ID / CDK_DEFAULT_ACCOUNT not set." >&2
  echo "Create $ENV_FILE from app/.env.example, or export them manually." >&2
  exit 1
fi

STAGE_CAP="$(printf '%s' "${STAGE:0:1}" | tr '[:lower:]' '[:upper:]')${STAGE:1}"
STACK_NAME="DatasheetMiner-${STAGE_CAP}-Database"
TABLE_NAME="${DYNAMODB_TABLE_NAME:-products-$STAGE}"
REGION="${AWS_REGION:-us-east-1}"

printf 'Stage:  %s\nStack:  %s\nTable:  %s\nRegion: %s\n\n' \
  "$STAGE" "$STACK_NAME" "$TABLE_NAME" "$REGION"

# 1. Table must exist in AWS — nothing to resurrect otherwise.
if ! aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "ERROR: DynamoDB table '$TABLE_NAME' not found in $REGION." >&2
  exit 1
fi

# 2. If the stack already manages the table, bail — import would no-op
#    and then error out.
MANAGED=$(aws cloudformation list-stack-resources \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query "StackResourceSummaries[?PhysicalResourceId=='$TABLE_NAME'].LogicalResourceId" \
  --output text 2>/dev/null || true)
if [[ -n "$MANAGED" ]]; then
  echo "$STACK_NAME already manages $TABLE_NAME (logical id: $MANAGED). Nothing to do."
  exit 0
fi

# 3. Synthesize to discover the logical ID CDK generates for the table.
cd "$REPO_ROOT/app/infrastructure"
export STAGE AWS_REGION="$REGION"
npx cdk synth "$STACK_NAME" --quiet >/dev/null

TEMPLATE="cdk.out/$STACK_NAME.template.json"
if [[ ! -f "$TEMPLATE" ]]; then
  echo "ERROR: synthesized template missing at $TEMPLATE" >&2
  exit 1
fi

LOGICAL_ID=$(python3 -c "
import json, sys
with open('$TEMPLATE') as f:
    tpl = json.load(f)
for name, res in tpl.get('Resources', {}).items():
    if res.get('Type') == 'AWS::DynamoDB::Table':
        print(name); sys.exit(0)
sys.exit(1)
") || { echo "ERROR: no AWS::DynamoDB::Table found in $TEMPLATE" >&2; exit 1; }

echo "CDK logical id for the table: $LOGICAL_ID"

# 4. Write the resource-mapping file cdk import will consume.
MAP_FILE="$(mktemp "${TMPDIR:-/tmp}/cdk-import-map.XXXXXX")"
trap 'rm -f "$MAP_FILE"' EXIT

cat >"$MAP_FILE" <<JSON
{
  "$LOGICAL_ID": { "TableName": "$TABLE_NAME" }
}
JSON

echo "Resource mapping:"
cat "$MAP_FILE"
echo

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Dry-run: not calling 'cdk import'."
  exit 0
fi

# 5. Confirm, then import.
printf 'Proceed with cdk import %s? [y/N] ' "$STACK_NAME"
read -r ans
case "${ans:-n}" in
  y|Y|yes|YES) ;;
  *) echo "Aborted."; exit 1 ;;
esac

npx cdk import "$STACK_NAME" --resource-mapping "$MAP_FILE"

cat <<DONE

Import complete. Review drift, then redeploy:
  (cd app/infrastructure && npx cdk diff $STACK_NAME)
  ./Quickstart deploy --stage $STAGE
DONE
