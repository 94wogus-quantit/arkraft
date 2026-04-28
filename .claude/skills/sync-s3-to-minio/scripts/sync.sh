#!/usr/bin/env bash
set -euo pipefail

# Sync remote S3 bucket to local MinIO via temp directory
# Usage: ./sync.sh <aws_profile> [prefixes] [bucket]
# prefixes: comma-separated list (e.g. "users/,data-query/"), empty for full bucket
# bucket: S3 bucket name (default: arkraft-production)

PROFILE="${1:-default}"
PREFIXES="${2:-}"
BUCKET="${3:-arkraft-production}"
MINIO_ENDPOINT="http://localhost:9000"

# Cleanup on exit (success or failure)
SYNC_TMPDIR=$(mktemp -d)
trap 'echo "Cleaning up ${SYNC_TMPDIR}..."; rm -rf "${SYNC_TMPDIR}"' EXIT

echo "=== S3 → MinIO Sync ==="
echo "Profile: ${PROFILE}"
echo "Bucket: ${BUCKET}"
echo "Temp dir: ${SYNC_TMPDIR}"
echo ""

if [ -z "$PREFIXES" ]; then
  # Full bucket sync
  echo "[1/2] Downloading s3://${BUCKET} → ${SYNC_TMPDIR} ..."
  aws s3 sync "s3://${BUCKET}" "${SYNC_TMPDIR}" \
    --profile "${PROFILE}" \
    --delete

  echo ""
  echo "[2/2] Uploading ${SYNC_TMPDIR} → MinIO s3://${BUCKET} ..."
  AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
    aws s3 sync "${SYNC_TMPDIR}" "s3://${BUCKET}" \
    --endpoint-url "${MINIO_ENDPOINT}" \
    --no-verify-ssl \
    --delete 2>/dev/null
else
  # Prefix-by-prefix sync
  IFS=',' read -ra PREFIX_ARRAY <<< "$PREFIXES"
  TOTAL=${#PREFIX_ARRAY[@]}
  IDX=0

  for PREFIX in "${PREFIX_ARRAY[@]}"; do
    # Trim whitespace
    PREFIX=$(echo "$PREFIX" | xargs)
    IDX=$((IDX + 1))

    echo "[${IDX}/${TOTAL}] Syncing prefix: ${PREFIX}"

    echo "  Downloading s3://${BUCKET}/${PREFIX} ..."
    aws s3 sync "s3://${BUCKET}/${PREFIX}" "${SYNC_TMPDIR}/${PREFIX}" \
      --profile "${PROFILE}" \
      --delete

    echo "  Uploading to MinIO s3://${BUCKET}/${PREFIX} ..."
    AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
      aws s3 sync "${SYNC_TMPDIR}/${PREFIX}" "s3://${BUCKET}/${PREFIX}" \
      --endpoint-url "${MINIO_ENDPOINT}" \
      --no-verify-ssl \
      --delete 2>/dev/null

    echo ""
  done
fi

echo "=== Sync complete ==="
