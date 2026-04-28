---
name: connect-remote
description: This skill should be used when the user asks to "connect to production", "connect to staging", "RDS 연결", "Redis 연결", "원격 DB 접속", "production DB", "staging DB", "remote rds", "remote redis", "rds-connect", "redis-connect", "ElastiCache 연결", or needs SSM port forwarding to production/staging AWS resources (RDS, Redis, etc.).
allowed-tools: "Bash, AskUserQuestion"
---

# Connect to Remote Resources

Connect to production/staging AWS resources (RDS, Redis, etc.) from local via SSM port forwarding.

## Known Resources

### SSM Bastion

Instance ID is dynamically resolved via AWS CLI instead of a hardcoded value (see Step 4-4).
Terraform resource path: `module.aws.module.ssm_bastion.aws_instance.this`

### RDS (arkraft-postgres)

Same RDS instance with separate databases per environment.

| Field | Production | Staging |
|-------|------------|---------|
| Host | `arkraft-postgres.cjjgohlf4jlu.ap-northeast-2.rds.amazonaws.com` | (same) |
| Remote Port | `5432` | (same) |
| Default Local Port | `25432` | (same) |
| Database | `arkraft` | `arkraft_staging` |
| User | `arkraft` | (same) |
| Secret Name | `ai-infra/rds/arkraft-postgres` | (same) |
| Secret Region | `ap-northeast-2` | (same) |

### Redis (arkraft-redis)

Same Redis instance with separate DB numbers per environment.

| Field | Production | Staging |
|-------|------------|---------|
| Host | `arkraft-redis.hbi1zz.0001.apn2.cache.amazonaws.com` | (same) |
| Remote Port | `6379` | (same) |
| Default Local Port | `16379` | (same) |
| DB | `1` | `2` |

## Step 1: Select Environment

Use `AskUserQuestion` to ask which environment:

- header: `"Environment"`
- options: `"Production"` / `"Staging"`
- multiSelect: `false`

Set `ENV` from selection. Resource names vary by environment:
- Production → `DATABASE=arkraft`, `REDIS_DB=1`
- Staging → `DATABASE=arkraft_staging`, `REDIS_DB=2`

## Step 2: Select Target Service

Use `AskUserQuestion` to ask which service to connect:

- header: `"Target Service"`
- options: `"RDS (arkraft-postgres)"` / `"Redis (arkraft-redis)"` / `"Other (custom)"`
- multiSelect: `false`

### If RDS is selected

Set variables from Known Resources above:

```
HOST=arkraft-postgres.cjjgohlf4jlu.ap-northeast-2.rds.amazonaws.com
REMOTE_PORT=5432
LOCAL_PORT=25432
```

Proceed to Step 3.

### If Redis is selected

Set variables from Known Resources above:

```
HOST=arkraft-redis.hbi1zz.0001.apn2.cache.amazonaws.com
REMOTE_PORT=6379
LOCAL_PORT=16379
```

Proceed to Step 3.

### If Other is selected

Use `AskUserQuestion` to collect connection details:

1. header: `"Remote Host"` — user enters the host in the Other input field
2. header: `"Remote Port"` — user enters the port in the Other input field
3. header: `"Local Port"` — user enters the local port in the Other input field

Set variables from user input and proceed to Step 3.

## Step 3: AWS Profile

Use `AskUserQuestion` to select AWS profile:

- header: `"AWS Profile"`
- options: `"default"` / `"Other (custom)"`
- multiSelect: `false`

Set `PROFILE` from selection (default: `default`).

## Step 4: Pre-flight Checks

Run the following checks in parallel:

### 4-1. AWS Authentication

```bash
aws sts get-caller-identity --profile ${PROFILE}
```

Failure: stop and guide the user to configure AWS CLI credentials.

### 4-2. Session Manager Plugin

```bash
session-manager-plugin --version
```

Not installed: guide `brew install session-manager-plugin`.

### 4-3. Port Availability

```bash
lsof -i :${LOCAL_PORT} -t 2>/dev/null
```

If port is in use, kill existing process and wait 2 seconds:

```bash
lsof -i :${LOCAL_PORT} -t 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 2
```

### 4-4. Resolve Bastion Instance ID

Read the `ssm_bastion_instance_id` output directly from the Terraform state file:

```bash
BASTION_ID=$(aws s3 cp \
  s3://quantit-tfstate/terraform/ai-infra/terraform.tfstate - \
  --profile ${PROFILE} 2>/dev/null \
  | jq -r '.outputs.ssm_bastion_instance_id.value // empty')
```

If lookup fails or result is empty (`$BASTION_ID` is empty):

Print error message and stop. Guide the user to check the following:
- Verify the AWS profile has read access to the `s3://quantit-tfstate` bucket
- Verify `jq` is installed (`brew install jq`)

On success: print `"SSM Bastion: $BASTION_ID"`.

### 4-5. Retrieve RDS Password (RDS only)

Retrieve the RDS password from AWS Secrets Manager:

```bash
PGPASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id ai-infra/rds/arkraft-postgres \
  --region ap-northeast-2 \
  --profile ${PROFILE} \
  --query 'SecretString' --output text | jq -r '.password')
```

On success: print `"RDS password retrieved from Secrets Manager"`.

On failure: print error message and stop. Guide the user to check the following:
- Verify the AWS profile has Secrets Manager read permission (`secretsmanager:GetSecretValue`)
- Verify the secret name is `ai-infra/rds/arkraft-postgres`

## Step 5: Start SSM Port Forwarding

Start SSM session with `run_in_background=true` (using `$BASTION_ID` resolved in Step 4-4):

```bash
aws ssm start-session \
  --profile ${PROFILE} \
  --target ${BASTION_ID} \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["${HOST}"],"portNumber":["${REMOTE_PORT}"],"localPortNumber":["'${LOCAL_PORT}'"]}'
```

## Step 6: Verify Connection

Wait for port to become available (max 5 attempts, 2-second intervals):

```bash
for i in {1..5}; do
  lsof -i :${LOCAL_PORT} -t 2>/dev/null && break
  sleep 2
done
```

After port is detected, wait 2 additional seconds for SSM tunnel to fully establish before attempting service-level verification:

```bash
sleep 2
```

### RDS Verification

Use the `PGPASSWORD` retrieved in Step 4-5 to verify the connection:

```bash
PGPASSWORD="${PGPASSWORD}" psql \
  -h 127.0.0.1 -p ${LOCAL_PORT} -U arkraft -d ${DATABASE} \
  -c "SELECT 1;" 2>/dev/null && echo "RDS connection OK"
```

Note: The `psql` path may vary by environment. Use `which psql` to verify before running.

### Redis Verification

```bash
python3 -c "
import redis
r = redis.from_url('redis://localhost:${LOCAL_PORT}/${REDIS_DB}', socket_timeout=5)
print('PING:', r.ping())
r.close()
"
```

## Step 7: Report

Display connection details to the user:

**RDS:**

| Field | Value |
|-------|-------|
| Environment | `${ENV}` |
| Host | `localhost` |
| Port | `${LOCAL_PORT}` |
| Database | `${DATABASE}` |
| User | `arkraft` |
| Connection String | `postgresql://arkraft@localhost:${LOCAL_PORT}/${DATABASE}` |

**Redis:**

| Field | Value |
|-------|-------|
| Environment | `${ENV}` |
| Host | `localhost` |
| Port | `${LOCAL_PORT}` |
| DB | `${REDIS_DB}` |
| URL | `redis://localhost:${LOCAL_PORT}/${REDIS_DB}` |

**Other:**

| Field | Value |
|-------|-------|
| Host | `localhost` |
| Port | `${LOCAL_PORT}` |

## Session Management

- Check session: `/tasks`
- Stop session: TaskStop tool
