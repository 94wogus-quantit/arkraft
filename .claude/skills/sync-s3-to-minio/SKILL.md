---
name: sync-s3-to-minio
description: This skill should be used when the user asks to "sync s3", "s3 동기화", "sync s3 to minio", "S3 로컬 동기화", "minio sync", "미니오 싱크", "s3 to local", "s3 데이터 복사", or needs to synchronize remote AWS S3 bucket data to local MinIO.
allowed-tools: "Bash, AskUserQuestion"
---

# Sync Remote S3 to Local MinIO

Synchronize remote AWS S3 bucket data to local MinIO.

## Parameters

Use defaults or confirm with the user:

| Parameter | Default   | Description      |
| --------- | --------- | ---------------- |
| PROFILE   | `default` | AWS profile name |

## Environments

| Environment | S3 Bucket |
| ----------- | --------- |
| Production  | `arkraft-production` |
| Staging     | `arkraft-staging` |

## Step 1: Select Environment

Use `AskUserQuestion` to ask which environment:

- header: `"Environment"`
- options: `"Production (arkraft-production)"` / `"Staging (arkraft-staging)"`
- multiSelect: `false`

Set `BUCKET` from selection:
- Production → `BUCKET=arkraft-production`
- Staging → `BUCKET=arkraft-staging`

## Step 2: Pre-flight Checks

Run the following 2 checks in parallel:

### 2-1. AWS Authentication

```bash
aws sts get-caller-identity --profile ${PROFILE}
```

Failure: stop and guide the user to configure AWS CLI credentials.

### 2-2. MinIO Container

```bash
docker compose ps minio --format json
```

If not running:

```bash
docker compose up -d minio minio-init
```

Wait until minio is healthy (max 10 attempts, 2-second intervals):

```bash
until docker compose ps minio --format json | grep -q '"healthy"'; do sleep 2; done
```

## Step 3: Sync Scope Selection

### 3-1. List remote bucket top-level prefixes

```bash
aws s3 ls s3://${BUCKET}/ --profile ${PROFILE}
```

Print the results to the user.
Example:
```
S3 bucket top-level prefixes:
  PRE users/
  PRE data-query/
  PRE reports/
```

### 3-2. AskUserQuestion for scope selection

- header: `"Sync Scope"`
- options: `"Full bucket"` / `"Select specific prefixes"`
- multiSelect: `false`

**If "Select specific prefixes" is chosen:**
- User enters prefixes in the Other input field (comma-separated).
  - Example: `users/, data-query/`
- Parse the Other input value into `PREFIXES` variable without additional AskUserQuestion.

**If "Full bucket" is chosen:**
- `PREFIXES` is an empty string.

## Step 4: Sync Execution

> `aws s3 sync` uses a single credential set when both source and destination are S3 URIs.
> Therefore, sync via a local temp directory: **Remote S3 → tmpdir → MinIO**.

> Note: Full bucket sync requires sufficient disk space in the temp directory.

Run **`scripts/sync.sh`**. Set Bash tool `timeout` to 600000 (10 minutes):

```bash
.claude/skills/sync-s3-to-minio/scripts/sync.sh "${PROFILE}" "${PREFIXES}" "${BUCKET}"
```

## Step 5: Verify

Check MinIO bucket contents:

```bash
AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
  aws s3 ls s3://${BUCKET}/ \
  --endpoint-url http://localhost:9000 \
  --no-verify-ssl 2>/dev/null
```

Report to the user:
- Sync result (success/error)
- Synced scope (full bucket or specified prefixes)
- MinIO Console URL: `http://localhost:9001` (minioadmin/minioadmin)

## Connection Info

|          | Remote (AWS S3)              | Local (MinIO)            |
| -------- | ---------------------------- | ------------------------ |
| Bucket   | `${BUCKET}`                 | `${BUCKET}`             |
| Endpoint | AWS default                  | `http://localhost:9000`  |
| Console  | -                            | `http://localhost:9001`  |
| Credentials | AWS profile (${PROFILE}) | `minioadmin/minioadmin`  |
