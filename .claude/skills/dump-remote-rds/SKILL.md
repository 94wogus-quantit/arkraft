---
name: dump-remote-rds
description: This skill should be used when the user asks to "dump remote rds", "sync remote db", "원격 DB 동기화", "RDS 덤프", "dump-remote-rds-to-local", "staging DB 덤프", "staging 동기화", or needs to synchronize remote RDS data to local Docker PostgreSQL.
allowed-tools: "Bash, AskUserQuestion"
---

# Dump Remote RDS to Local

Synchronize remote RDS data to local Docker PostgreSQL.
Either reset local DB (delete volume → recreate) and do a full copy, or keep existing DB and sync selected tables only.

## Parameters

Use defaults or confirm with the user:

| Parameter | Default   | Description              |
| --------- | --------- | ------------------------ |
| PROFILE   | `default` | AWS profile name         |
| PORT      | `25432`   | SSM forwarding local port |

## Environments

Same RDS instance with separate databases per environment.

| Environment | Remote Database   | Local Database |
| ----------- | ----------------- | -------------- |
| Production  | `arkraft`         | `arkraft`      |
| Staging     | `arkraft_staging` | `arkraft`      |

> When syncing Staging → Local, dump from `arkraft_staging` on remote and restore into `arkraft` on local.

## Connection Info

|          | Remote (RDS)             | Local (Docker) |
| -------- | ------------------------ | -------------- |
| Host     | SSM → 127.0.0.1:${PORT} | 127.0.0.1:5432 |
| User     | arkraft                  | arkraft        |
| Password | (Secrets Manager)        | arkraft        |
| Database | `${REMOTE_DB}`           | `arkraft`      |

## Step 1: Select Environment

Use `AskUserQuestion` to ask which environment:

- header: `"Environment"`
- options: `"Production (arkraft)"` / `"Staging (arkraft_staging)"`
- multiSelect: `false`

Set `REMOTE_DB` from selection:
- Production → `REMOTE_DB=arkraft`
- Staging → `REMOTE_DB=arkraft_staging`

## Step 2: Pre-flight Checks

Run the following 4 checks in parallel:

### 2-1. pg_dump & pg_restore (v17)

```bash
/opt/homebrew/opt/postgresql@17/bin/pg_dump --version && /opt/homebrew/opt/postgresql@17/bin/pg_restore --version
```

If not found: guide `brew install postgresql@17`.

### 2-2. AWS Authentication

```bash
aws sts get-caller-identity --profile ${PROFILE}
```

### 2-3. Docker postgres

```bash
docker compose ps postgres --format json
```

If not running: `docker compose up -d postgres`, then wait for `pg_isready` (max 5 attempts, 2-second intervals).

### 2-4. RDS Password (auto-retrieve from Secrets Manager)

```bash
RDS_PASS=$(aws secretsmanager get-secret-value \
  --secret-id ai-infra/rds/arkraft-postgres \
  --region ap-northeast-2 \
  --profile ${PROFILE} \
  --query 'SecretString' --output text | jq -r '.password')
```

On success: print `"RDS password retrieved from Secrets Manager"`.

On failure: stop and guide the user to check:
- AWS profile has Secrets Manager read permission (`secretsmanager:GetSecretValue`)
- Secret name: `ai-infra/rds/arkraft-postgres`
- `jq` is installed

## Step 3: SSM Port Forwarding

### 3-1. Check port

```bash
lsof -i :${PORT} -t 2>/dev/null
```

- If in use: skip to Step 4
- If free: proceed to 3-2

### 3-2. Resolve Bastion ID

Dynamically resolve bastion instance ID from Terraform state:

```bash
BASTION_ID=$(aws s3 cp \
  s3://quantit-tfstate/terraform/ai-infra/terraform.tfstate - \
  --profile ${PROFILE} 2>/dev/null \
  | jq -r '.outputs.ssm_bastion_instance_id.value // empty')
```

If `$BASTION_ID` is empty: stop and guide the user to check AWS permissions and `jq` installation.

### 3-3. Start SSM (background)

Run with `run_in_background=true`:

```bash
aws ssm start-session \
  --profile ${PROFILE} \
  --target ${BASTION_ID} \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["arkraft-postgres.cjjgohlf4jlu.ap-northeast-2.rds.amazonaws.com"],"portNumber":["5432"],"localPortNumber":["'${PORT}'"]}'
```

### 3-4. Wait for port

Check `lsof -i :${PORT}` max 5 times (2-second intervals). Stop if port never becomes available.

## Step 4: Local DB Reset

Use `AskUserQuestion` to ask whether to reset local DB:

- header: `"Local DB"`
- options: `"Reset and full sync"` / `"Keep existing DB"`
- multiSelect: `false`

### If "Reset and full sync" is chosen:

Run sequentially:

```bash
docker compose down postgres
docker volume rm arkraft-api_postgres_data || true
docker compose up -d postgres
```

Wait until postgres is healthy (max 10 attempts, 2-second intervals):

```bash
until docker compose ps postgres --format json | grep -q '"healthy"'; do sleep 2; done
```

`TABLES` is empty string (all tables), `RESET=true` → **skip to Step 5** (skip table selection).

### If "Keep existing DB" is chosen:

Proceed to Step 4-1.

### 4-1. List remote tables

Fetch public table list from Remote RDS via SSM tunnel:

```bash
PGPASSWORD="$RDS_PASS" /opt/homebrew/opt/postgresql@17/bin/psql \
  -h 127.0.0.1 -p ${PORT} -U arkraft -d ${REMOTE_DB} -t -A \
  -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
```

Print results as a numbered table list (excluding `alembic_version`).
Example:
```
Remote RDS tables:
1. agent_credentials
2. community_posts
3. users
...
```

### 4-2. AskUserQuestion for table selection

After printing the table list, call `AskUserQuestion`:

- header: `"Tables"`
- options: `"All tables"` / `"Select"`
- multiSelect: `false`

**If "Select" is chosen:**
- User enters table names in the Other input field (comma-separated).
  - Example: `users, workflows, sessions, jobs`
- Parse the Other input value into `TABLES` variable without additional AskUserQuestion.

Store selection in `TABLES` as comma-separated. Empty string for all tables.

## Step 5: Dump

Run pg_dump inline (timeout 5 minutes).

`DUMP_FILE=/tmp/arkraft_dump_$(date +%Y%m%d_%H%M%S).dump`

### All tables (TABLES is empty):

```bash
PGPASSWORD="$RDS_PASS" /opt/homebrew/opt/postgresql@17/bin/pg_dump \
  -h 127.0.0.1 -p ${PORT} -U arkraft -d ${REMOTE_DB} -Fc \
  -f "$DUMP_FILE"
```

### Selected tables (TABLES is comma-separated):

Add `-t` flag for each table:

```bash
PGPASSWORD="$RDS_PASS" /opt/homebrew/opt/postgresql@17/bin/pg_dump \
  -h 127.0.0.1 -p ${PORT} -U arkraft -d ${REMOTE_DB} -Fc \
  -t table1 -t table2 ... \
  -f "$DUMP_FILE"
```

Check dump file size after completion:

```bash
ls -lh "$DUMP_FILE"
```

## Step 6: Restore

Run pg_restore inline (timeout 5 minutes).

### RESET=true (reset and full sync):

Schema + data full restore:

```bash
PGPASSWORD=arkraft /opt/homebrew/opt/postgresql@17/bin/pg_restore \
  -h 127.0.0.1 -p 5432 -U arkraft -d arkraft \
  --no-owner --no-privileges \
  "$DUMP_FILE" 2>&1 || true
```

### RESET=false (keep existing DB):

#### 6-1. Truncate target tables

If TABLES is empty (all tables):

```bash
TABLE_LIST=$(PGPASSWORD=arkraft /opt/homebrew/opt/postgresql@17/bin/psql \
  -h 127.0.0.1 -p 5432 -U arkraft -d arkraft -t -A \
  -c "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename != 'alembic_version' ORDER BY tablename;")
TRUNCATE_CSV=$(echo "$TABLE_LIST" | paste -sd, -)
PGPASSWORD=arkraft /opt/homebrew/opt/postgresql@17/bin/psql \
  -h 127.0.0.1 -p 5432 -U arkraft -d arkraft \
  -c "TRUNCATE TABLE $TRUNCATE_CSV CASCADE;"
```

If TABLES is specified:

```bash
PGPASSWORD=arkraft /opt/homebrew/opt/postgresql@17/bin/psql \
  -h 127.0.0.1 -p 5432 -U arkraft -d arkraft \
  -c "TRUNCATE TABLE ${TABLES} CASCADE;"
```

#### 6-2. Data-only restore

```bash
PGPASSWORD=arkraft /opt/homebrew/opt/postgresql@17/bin/pg_restore \
  -h 127.0.0.1 -p 5432 -U arkraft -d arkraft \
  --data-only --no-owner --no-privileges --disable-triggers \
  "$DUMP_FILE" 2>&1 || true
```

## Step 7: Post-restore Migration

Apply latest migrations that only exist in local code.

### 7-1. Start server container

```bash
docker compose up -d server
```

### 7-2. Wait for server healthy

Max 15 attempts, 2-second intervals:

```bash
for i in {1..15}; do
  docker compose ps server --format json | grep -q '"healthy"' && break
  sleep 2
done
```

### 7-3. Run migration

```bash
make migrate
```

- Full reset: the remote alembic_version is restored, so `make migrate` applies any ahead migrations from local code.
- Data-only: alembic_version is unchanged, so `make migrate` is a safe no-op or applies additional migrations.

## Step 8: Verify

```bash
PGPASSWORD=arkraft /opt/homebrew/opt/postgresql@17/bin/psql -h 127.0.0.1 -p 5432 -U arkraft -d arkraft \
  -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;" \
  -c "SELECT * FROM alembic_version;"
```

Report to the user:

- Restore result (success/error)
- Synced tables (all or specified list)
- Alembic migration version

## Step 9: Cleanup

### 9-1. Delete dump file

```bash
rm -f "$DUMP_FILE"
```

### 9-2. SSM session

SSM port forwarding session persists after sync.

- Check: `/tasks`
- Stop: TaskStop tool
