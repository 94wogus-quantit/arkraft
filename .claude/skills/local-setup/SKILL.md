---
name: local-setup
description: Use this skill for full local dev environment setup / onboarding a new teammate to the arkraft stack. Triggers — "local-setup", "로컬 환경 세팅", "local dev setup", "dev bootstrap", "신규 팀원 온보딩", "onboarding", "local 환경 구축", "전체 개발 환경 세팅", plus backward-compat aliases — "reset application", "reset dev", "dev 리셋", "앱 리셋", "전체 리셋", "dev 환경 초기화", "application reset". One-shot bootstrap — preflight checks (gh / aws / api .env with ALPHA_POOL_* + auth token), agent docker builds (alpha / insight / portfolio, always rebuild), arkraft-api full-reset, sync `teams/arkraft/catalogs/` parquet to local MinIO (the only data alpha agent actually needs), arkraft-web pnpm dev, Chrome CDP + team_id cookie. Does NOT mirror staging's DB — local stays local.
user-invocable: true
---

# Local Setup — Full Dev Environment Bootstrap

Bring a brand-new laptop (or a bricked one) to a fully working arkraft dev environment in one pass. Built for **new-teammate onboarding** — just follow the steps top to bottom.

> **New teammate? Follow the sections in order from Step 0 to Step 9. When Step 9's final verification prints all ✅, you are done and can start developing.**

Each step detects "already-done" state and skips when possible. Failures always print a clear recovery hint.

## 🚫 Global execution rule — sequential & foreground only

**Never parallelize or background anything in this skill.** Run each command in the foreground, wait for it to return, then move to the next. No `run_in_background: true`, no `&`, no multi-command fan-out.

Why: every prior attempt at "parallel to save time" (concurrent docker builds, background S3 sync + build, etc.) stalled mid-way or got orphaned by the session, leaving half-finished state that silently breaks later steps. A slow-but-complete run is always better than a fast-but-stuck run. Onboarding is a one-time cost — sequential execution is the right trade.

Concretely, for each Bash tool call in this skill:
- `run_in_background: false` (default)
- Long-running commands (docker build, `make full-reset`, S3 sync): raise `timeout` (e.g. `600000` ms) and let them stream to completion.
- Do NOT dispatch a command and poll its output file — just wait for the return.

## Location Guard (run before every step)

The whole skill assumes you are at the arkraft monorepo root. Always verify:

```bash
# Why: sub-repo work (cd) can silently drift the working directory and
# break later commands. Re-assert the root before every major step.
[ "$(pwd)" = "/Users/wogus/Project/arkraft" ] || cd /Users/wogus/Project/arkraft
pwd  # must print: /Users/wogus/Project/arkraft
```

Every block below that does `cd <sub-repo>` ends with `cd /Users/wogus/Project/arkraft` so the cursor returns to root.

---

## Step 0 — Check agent-browser / Chrome CDP (kill only if broken)

_Why: if CDP + agent-browser are already healthy, nuking them just loses the user's browser state. Only reset when broken._

### 0-1. Health probe

```bash
[ "$(pwd)" = "/Users/wogus/Project/arkraft" ] || cd /Users/wogus/Project/arkraft

# Is CDP port 9222 responding?
CDP_OK=0
curl -s --max-time 2 http://localhost:9222/json/version >/dev/null 2>&1 && CDP_OK=1

# Does agent-browser attach cleanly?
AB_OK=0
if [ "$CDP_OK" = "1" ]; then
  agent-browser --auto-connect eval "1" >/dev/null 2>&1 && AB_OK=1
fi

echo "CDP:$CDP_OK agent-browser:$AB_OK"
```

### 0-2. Branch

- **Both OK** (`CDP:1 agent-browser:1`) → **skip Step 0 entirely**, proceed to Step 1. Step 8 will reuse the existing Chrome + cookie.
- **Either broken** → kill stale processes so Step 8 can restart cleanly:

  ```bash
  pkill -f "agent-browser" 2>/dev/null || true
  pkill -f "chromium.*remote-debugging" 2>/dev/null || true
  sleep 1
  ```

> Don't pkill Chrome itself here — Step 8 handles that when it needs to restart Chrome with `--remote-debugging-port=9222`.

---

## Step 1 — Preflight / Env Verification

_Why: agents need cloud credentials and secrets. Fail fast here instead of deep inside a build._

### 1-1. GitHub auth

```bash
[ "$(pwd)" = "/Users/wogus/Project/arkraft" ] || cd /Users/wogus/Project/arkraft
gh auth status 2>&1 | tee /tmp/gh-auth-status.log
```

**Skip-when-done**: output contains `Logged in to github.com`.
**Recovery on failure**: run `gh auth login` and pick GitHub.com → HTTPS → browser. Private `arkraft-sdk` git dep in agent images requires this.

### 1-2. AWS auth

```bash
aws sts get-caller-identity 2>&1 | tee /tmp/aws-sts.log
```

**Skip-when-done**: JSON with `Account`, `Arn` is printed.

**Recovery on failure** — 회사는 **AWS Identity Center (구 AWS SSO) 안 쓴다**. `aws configure sso`/`aws sso login` 흐름 모두 해당 없음. 표준 흐름은 IAM user + access key + (선택) MFA serial:

1. AWS 콘솔에서 본인 IAM 사용자 access key 발급 (없으면 @backend / @infra 에 요청)
2. `aws configure --profile default` 로 access key + secret + region(`ap-northeast-2`) 입력
3. (필요 시) `~/.aws/config` 의 `[default]` 또는 별도 profile 에 `mfa_serial = arn:aws:iam::<account>:mfa/<user>` 추가
4. `aws sts get-caller-identity` 다시 확인

이건 SSM bastion / S3 / Secrets Manager (Step 5의 RDS·Redis 비밀번호 자동 조회) 에 필요한 root 자격증명이고, **Step 1-3 의 `ALPHA_POOL_*` 와는 별개의 IAM user**다 (`ALPHA_POOL_*` 는 alpha-pool 전용 IAM access key 로, Secrets Manager 가 아니라 `arkraft-api/.env` 에 직접 박는다 — 1-3 참고).

### 1-3. arkraft-api `.env` + required keys

```bash
API_ENV=/Users/wogus/Project/arkraft/arkraft-api/.env

# 1-3-a. file existence
if [ ! -f "$API_ENV" ]; then
  cp /Users/wogus/Project/arkraft/arkraft-api/.env.example "$API_ENV"
  echo "❌ arkraft-api/.env was missing — copied from .env.example. Fill required values and re-run."
  exit 1
fi
echo "✅ arkraft-api/.env present"

# 1-3-b. required keys must be non-empty
#   ALPHA_POOL_* — agent alpha-pool access (staging DynamoDB + OpenSearch index + IAM creds)
#   CLAUDE_OAUTH_TOKEN_1 or AWS_BEARER_TOKEN_BEDROCK — at least one, so DockerRunRunner can
#     inject credentials into spawned agent containers via _common_env() / _oauth_env().
REQUIRED_KEYS=(
  ALPHA_POOL_DYNAMODB_TABLE
  ALPHA_POOL_OS_INDEX_NAME
  ALPHA_POOL_AWS_ACCESS_KEY_ID
  ALPHA_POOL_AWS_SECRET_ACCESS_KEY
)
MISSING=()
for k in "${REQUIRED_KEYS[@]}"; do
  grep -qE "^${k}=.+" "$API_ENV" || MISSING+=("$k")
done
if ! grep -qE '^(CLAUDE_OAUTH_TOKEN_1|AWS_BEARER_TOKEN_BEDROCK)=.+' "$API_ENV"; then
  MISSING+=("CLAUDE_OAUTH_TOKEN_1 or AWS_BEARER_TOKEN_BEDROCK")
fi
if [ ${#MISSING[@]} -gt 0 ]; then
  echo "❌ arkraft-api/.env missing required values:"
  printf '   - %s\n' "${MISSING[@]}"
  echo "   Ask @backend for these (alpha-pool IAM creds + agent auth token) and re-run."
  echo "   Note: 이 값들은 AWS Secrets Manager 가 아니라 backend 가 직접 발급/관리하는 alpha-pool 전용 IAM access key 다. SSO 로 얻을 수 없음."
  exit 1
fi
echo "✅ arkraft-api/.env required keys populated"
```

### 1-4. arkraft-web env (`.env` or `.env.local`)

Next.js loads either file; both are accepted.

```bash
if [ -f /Users/wogus/Project/arkraft/arkraft-web/.env ] \
   || [ -f /Users/wogus/Project/arkraft/arkraft-web/.env.local ]; then
  echo "✅ arkraft-web env present"
else
  echo "❌ arkraft-web env missing — copying .env.example → .env.local"
  cp /Users/wogus/Project/arkraft/arkraft-web/.env.example \
     /Users/wogus/Project/arkraft/arkraft-web/.env.local 2>/dev/null \
  || echo "⚠️ No .env.example either — ask @backend for values."
  exit 1
fi
```

### 1-5. Agent `.env` — **NOT required for API-triggered runs, skip by default**

Agent containers spawned by `arkraft-api` use **`DockerRunRunner`** (`arkraft-api/infrastructure/agent/base.py`), which creates containers **directly from the image with explicit env injection** — it does NOT load the agent repo's `.env` file.

What the API injects per container (see `_common_env()` + `_oauth_env(email)`):

| Variable | Source |
|----------|--------|
| `S3_BUCKET`, `AWS_REGION`, `REDIS_URL`, `RABBITMQ_URL` | `arkraft-api/.env` (settings) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | `arkraft-api/.env` |
| `ANTHROPIC_API_KEY` | `arkraft-api/.env` |
| `CALLBACK_API_URL`, `ARKRAFT_API_URL`, `ARKRAFT_INTERNAL=true` | auto |
| `AGENT_OAUTH_TOKEN` | per-user lookup via `get_oauth_token_for_user(email)` |

So for the **normal onboarding path (API-driven)**, you can completely skip agent `.env`.

**Only fill it if you need standalone mode** (`docker compose run agent-dev`, `python main.py` direct run, or in-container shell for debugging). In that case:

```bash
AGENT_DIR=/Users/wogus/Project/arkraft/arkraft-agent-<agent>
test -f "$AGENT_DIR/.env" || cp "$AGENT_DIR/.env.example" "$AGENT_DIR/.env"
# Then manually fill CLAUDE_OAUTH_TOKEN_1 or AWS_BEARER_TOKEN_BEDROCK
```

**Default behavior**: skip this check. Only surface it if the user explicitly wants standalone agent debugging.

---

## Step 2 — Agent Selection

_Why: Docker builds take several minutes each; let the user pick._

Use **AskUserQuestion** (multiSelect):

- header: `"Agents to build"`
- options:
  - `alpha` — Alpha strategy agent (image `arkraft-alpha:latest`)
  - `insight` — Insight agent (image `arkraft-insight:latest`)
  - `portfolio` — Portfolio agent (image `arkraft-portfolio:latest`)
  - `all` — build all three
- multiSelect: `true`

Record the selection as `$SELECTED_AGENTS` (space-separated repo names, e.g. `arkraft-agent-alpha arkraft-agent-insight`). Agents without a local `docker-compose.yml` (`report`, `data`, `extract`) are intentionally **not** offered.

**Skip-when-done**: user selects nothing → skip Step 3 entirely.

---

## Step 3 — Agent Docker Build

_Why: in local mode, the API's `DockerRunRunner` spawns agent containers by image name — those images must exist locally._

### 3-0. Ensure shared external network `arkraft` exists

Agents' `docker-compose.yml` declares `networks: arkraft: external: true`. Created once by `arkraft-api`'s compose, but create it up-front so agent builds don't fail when `make full-reset` hasn't run yet:

```bash
[ "$(pwd)" = "/Users/wogus/Project/arkraft" ] || cd /Users/wogus/Project/arkraft
docker network ls | grep -qw arkraft || docker network create arkraft
```

### 3-1. Build each selected agent (foreground, sequential — DO NOT background)

> 🚫 **Absolute rule: run every build in the FOREGROUND, one at a time.** Never use `run_in_background: true`, `&`, or spawn two builds in parallel. Long docker builds launched as background tasks routinely stall or get abandoned mid-session, leaving half-built images that silently fail at runtime. Wait for each build to return before starting the next.

> ⚠️ **Do NOT use `docker compose build --build-arg GITHUB_TOKEN=...`.** Agent Dockerfiles use a **BuildKit secret** (`--mount=type=secret,id=github_token`) to fetch the private `arkraft-sdk` dependency. `--build-arg` does NOT satisfy a `--mount=type=secret` — the secret file will be empty, `uv sync` silently skips the private package, and the resulting image is missing `pydantic` + other transitive deps. You'll only see it at runtime as `ModuleNotFoundError: No module named 'pydantic'`.
>
> Use `docker build` from arkraft root with `--secret id=github_token,src=<file>` — same approach as `arkraft-api/infrastructure/agent/base.py::_ensure_image()`.

For every `$AGENT_DIR` in `$SELECTED_AGENTS` (alpha-first if both alpha and insight selected, so `arkraft-sdk` cache is warm):

```bash
# image name (canonical, matches what arkraft-api's DockerRunRunner looks for)
case "$AGENT_DIR" in
  arkraft-agent-alpha)     IMAGE=arkraft-alpha:latest ;;
  arkraft-agent-insight)   IMAGE=arkraft-insight:latest ;;
  arkraft-agent-portfolio) IMAGE=arkraft-portfolio:latest ;;
esac

[ "$(pwd)" = "/Users/wogus/Project/arkraft" ] || cd /Users/wogus/Project/arkraft

# Write GitHub token to a temp file (keeps it out of process args / build cache)
GH_TOKEN_FILE=$(mktemp)
gh auth token > "$GH_TOKEN_FILE"

# Build from arkraft root as context, using the Dockerfile inside the agent repo.
# --secret satisfies the Dockerfile's --mount=type=secret,id=github_token.
DOCKER_BUILDKIT=1 docker build \
  -f "$AGENT_DIR/Dockerfile" \
  -t "$IMAGE" \
  --secret "id=github_token,src=$GH_TOKEN_FILE" \
  .

rm -f "$GH_TOKEN_FILE"

docker image inspect "$IMAGE" --format '{{.Id}} {{.Created}}' \
  && echo "✅ $IMAGE rebuilt"
```

> When invoking this step via the Bash tool, pass `run_in_background: false` and set a generous `timeout` (e.g. `600000` ms). Let the build stream to completion.

**Post-build sanity check** (catch the "silent missing deps" failure immediately, not at runtime):

```bash
docker run --rm --entrypoint /app/.venv/bin/python "$IMAGE" \
  -c "import pydantic, arkraft_sdk; print('✅ venv healthy:', pydantic.__version__)"
```

If this fails, the image has the token-less build bug — rebuild after confirming `gh auth token` returns a valid token.

**No skip** — always rebuild. Docker's layer cache makes re-runs fast when source hasn't changed. Pass `--no-cache` to force a full rebuild.

---

## Step 4 — arkraft-api `full-reset`

_Why: brings DB + queue + API up in a known-clean state._

> ⚠️⚠️ **DESTRUCTIVE** — `make full-reset` runs `docker compose down -v` which **wipes all DB volumes**. Existing local data is gone. If the user has uncommitted demo data, pause and confirm first.

```bash
[ "$(pwd)" = "/Users/wogus/Project/arkraft" ] || cd /Users/wogus/Project/arkraft
cd /Users/wogus/Project/arkraft/arkraft-api
make full-reset
cd /Users/wogus/Project/arkraft
pwd  # expect: /Users/wogus/Project/arkraft
```

Internal sequence: `build` → `docker compose down -v --remove-orphans` → `make up` → `sleep 5` → `make migrate`. Takes several minutes. Verify the final `alembic upgrade head` succeeds.

**Skip-when-done**: if `docker ps --filter 'name=arkraft-api' --format '{{.Status}}' | grep -q Up` AND user confirms "don't wipe", skip this step entirely. Otherwise always run.

---

## Step 5 — Seed Catalog Data (DB rows + S3 parquet, catalog-only)

_Why: alpha agent needs (a) catalog rows in DB so API endpoints return "which catalogs exist" and (b) the actual parquet files on MinIO so alpha can read timeseries. Both are scoped **strictly to the catalog domain** — we do NOT mirror staging's full DB or full bucket._

> ⚠️ Scope: catalog-domain tables only (7 tables) + `teams/arkraft/catalogs/` S3 prefix only. Everything else (users, reports, alpha sessions, data-query, …) stays empty locally. That's the whole point of "local" — minimal data, not a staging clone.

### 5-0. Decide: sync or skip?

Use **AskUserQuestion** (single select): **Seed catalog data from staging (DB rows + S3 parquet)?**
- `Yes — DB catalog tables + S3 teams/arkraft/catalogs/ (~11.3 GiB)` — required for alpha agent
- `Skip` — pick this only if you already seeded before or you're not running alpha locally

If `Skip`, jump to Step 6.

### 5-1. Catalog DB rows → `dump-remote-rds`

```
Skill(skill: "dump-remote-rds")
```

Answer its prompts exactly as below — **do not ask the user these again** (Step 4 already wiped the local DB, and we explicitly want catalog-only scope):

| Prompt | Answer | Why |
|--------|--------|-----|
| `Environment` | `Staging` | same env as 5-2 |
| `Local DB` | `Keep existing DB` | we need per-table selective restore, NOT full DB dump |
| `Tables` (Other input, comma-separated, exact string) | `data_sources,data_files,data_sets,catalogs,catalog_analysis,catalog_sessions,catalog_session_logs` | 7 catalog-domain tables from `arkraft-api/infrastructure/persistence/models/data_integration.py` + `data_source.py` |

The skill opens the SSM tunnel, `pg_dump` these 7 tables from `arkraft_staging`, truncates them locally, and restores into local `arkraft` DB (schema already exists from Step 4's migrate).

### 5-2. Catalog S3 parquet → `sync-s3-to-minio` + bucket rename

> ⚠️ **Bucket name mismatch**: `sync-s3-to-minio` mirrors the remote bucket name as-is, so a staging sync lands in local MinIO's `arkraft-staging`. But local `arkraft-api/.env` has `S3_BUCKET=arkraft-production` and `docker-compose.yml::minio-init` only creates the `arkraft-production` bucket. If you leave the synced data in `arkraft-staging`, the local API can't find it. We sync first, then copy into `arkraft-production` locally.

#### 5-2-a. Sync staging → local MinIO

```
Skill(skill: "sync-s3-to-minio")
```

Answer exactly:

| Prompt | Answer |
|--------|--------|
| `Environment` | `Staging (arkraft-staging)` |
| `Sync Scope` | `Select specific prefixes` |
| `Prefixes` (Other input, comma-separated, exact string) | `teams/arkraft/catalogs/` |

One prefix only — `teams/arkraft/catalogs/` (the shared `kr_stock.*` parquet library, ~11.3 GiB, ~1800 objects). `catalog_sessions/` and `showcase/` are session artifacts — don't pull them.

Expect 10–30 min depending on link. After return: local MinIO has the objects under `s3://arkraft-staging/teams/arkraft/catalogs/`.

#### 5-2-b. Copy into the local API's bucket (read from `arkraft-api/.env`)

> The local API reads `S3_BUCKET` from `arkraft-api/.env` (default: `arkraft-production`, also what `docker-compose.yml::minio-init` creates). Don't hard-code — read it from the actual `.env` so the skill stays correct if someone changes it.

```bash
[ "$(pwd)" = "/Users/wogus/Project/arkraft" ] || cd /Users/wogus/Project/arkraft

# 1. Read what bucket the local API expects
LOCAL_BUCKET=$(grep -E '^S3_BUCKET=' /Users/wogus/Project/arkraft/arkraft-api/.env | cut -d= -f2- | tr -d '"' | tr -d "'" | tr -d ' ')
: "${LOCAL_BUCKET:=arkraft-production}"   # fallback to default
echo "Local API reads from bucket: $LOCAL_BUCKET"

if [ "$LOCAL_BUCKET" = "arkraft-staging" ]; then
  echo "⏭ Local API already points at arkraft-staging — sync-s3-to-minio's output is in the right place. Skip copy."
else
  # 2. Ensure destination bucket exists
  AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
    aws --endpoint-url http://localhost:9000 s3api head-bucket --bucket "$LOCAL_BUCKET" 2>/dev/null \
    || AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
       aws --endpoint-url http://localhost:9000 s3 mb "s3://$LOCAL_BUCKET"

  # 3. Copy the catalog prefix from arkraft-staging → $LOCAL_BUCKET (in-MinIO; no re-download)
  AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
    aws --endpoint-url http://localhost:9000 s3 sync \
    "s3://arkraft-staging/teams/arkraft/catalogs/" \
    "s3://$LOCAL_BUCKET/teams/arkraft/catalogs/"
  echo "✅ copied teams/arkraft/catalogs/ → s3://$LOCAL_BUCKET/ (local MinIO)"
fi
```

Server-side copy inside MinIO — fast, no re-download. Leave the `arkraft-staging` mirror as a backup; drop it later with `aws ... s3 rb s3://arkraft-staging --force` if space is tight.

### 5-3. Parity check

Both DB and S3 must be non-empty, and both must point at the same environment (staging):

```bash
# DB side — catalog rows restored?
psql postgresql://postgres:postgres@localhost:5432/arkraft \
  -c "SELECT 'catalogs='||COUNT(*) FROM catalogs UNION ALL
      SELECT 'data_files='||COUNT(*) FROM data_files UNION ALL
      SELECT 'data_sources='||COUNT(*) FROM data_sources;"

# S3 side — parquet landed?
AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
  aws --endpoint-url http://localhost:9000 s3 ls \
  s3://arkraft-staging/teams/arkraft/catalogs/ --recursive | wc -l
# Expect: ~1800 parquet files
```

**Skip-when-done**: both sides non-empty. If only one is populated, re-run the missing half.

---

## Step 6 — Query `quantit` team_id

_Why: the web app gates most features behind a `team_id` cookie; the quantit team is seeded during migrate + seed._

```bash
[ "$(pwd)" = "/Users/wogus/Project/arkraft" ] || cd /Users/wogus/Project/arkraft
TEAM_ID=$(psql postgresql://postgres:postgres@localhost:5432/arkraft \
  -t -c "SELECT id FROM teams WHERE name ILIKE '%quantit%' LIMIT 1;" \
  | tr -d ' \n')
echo "TEAM_ID=$TEAM_ID"
```

If empty, try inside the container:

```bash
TEAM_ID=$(docker exec $(docker ps -qf "name=postgres") \
  psql -U arkraft -d arkraft \
  -t -c "SELECT id FROM teams WHERE name ILIKE '%quantit%' LIMIT 1;" \
  | tr -d ' \n')
echo "TEAM_ID=$TEAM_ID"
```

Keep `$TEAM_ID` for Step 8.

**Skip-when-done**: `$TEAM_ID` already matches a UUID.

---

## Step 7 — Start arkraft-web `pnpm dev`

_Why: frontend must be running for the browser verification in Step 8._

```bash
[ "$(pwd)" = "/Users/wogus/Project/arkraft" ] || cd /Users/wogus/Project/arkraft
lsof -i :3000 | grep -q LISTEN \
  && echo "⏭  arkraft-web already listening on :3000" \
  || { \
    cd /Users/wogus/Project/arkraft/arkraft-web; \
    pnpm dev > /tmp/arkraft-web-dev.log 2>&1 & \
    cd /Users/wogus/Project/arkraft; \
  }

# Wait for readiness (max 30s)
for i in $(seq 1 30); do
  curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 \
    | grep -qE "200|30[27]" && echo "ready" && break
  sleep 1
done
pwd  # expect: /Users/wogus/Project/arkraft
```

**Skip-when-done**: port 3000 already listening and responds 200/307.

---

## Step 8 — Chrome CDP + agent-browser + team_id cookie

_Why: agent-browser is used for local UI verification; it attaches to Chrome via CDP, reusing cookies/sessions._

### 8-1. Ensure Chrome is running with remote debugging

```bash
curl -s http://localhost:9222/json/version | head -1 \
  && echo "⏭  CDP 9222 already open" \
  || { \
    pkill -9 -f "Google Chrome" 2>/dev/null; sleep 2; \
    nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
      --remote-debugging-port=9222 \
      --user-data-dir=/tmp/chrome-debug-profile \
      --no-first-run \
      --no-default-browser-check \
      > /tmp/chrome-debug.log 2>&1 & \
    sleep 5; \
    curl -s http://localhost:9222/json/version | head -1; \
  }
```

> ⚠️ Do NOT use `open -a "Google Chrome" --args --remote-debugging-port=9222`. Without `--user-data-dir`, macOS refuses to open CDP, and `open -a` reuses an existing instance, ignoring the flag.

### 8-2. Verify access

```bash
agent-browser --auto-connect open http://localhost:3000
agent-browser --auto-connect wait --load networkidle
agent-browser --auto-connect snapshot -i
```

### 8-3. Set `team_id` cookie

```bash
agent-browser --auto-connect cookies set team_id "$TEAM_ID" \
  --url http://localhost:3000 --path /
```

> ⚠️ `run-js` subcommand does not exist. Use `cookies set`. Cookie key is `team_id` (see `arkraft-web/src/infra/auth/team.ts`).

### 8-4. Reload and re-verify

```bash
agent-browser --auto-connect navigate http://localhost:3000
agent-browser --auto-connect wait --load networkidle
agent-browser --auto-connect snapshot -i
```

---

## Step 9 — Final Verification

_Why: surface a single green checklist so the user can see everything is ready._

```bash
[ "$(pwd)" = "/Users/wogus/Project/arkraft" ] || cd /Users/wogus/Project/arkraft

echo "── Final Verification ──────────────────────────────"

# API containers
docker ps --filter "name=arkraft-api" --format "{{.Names}}: {{.Status}}" \
  | grep -q Up && echo "✅ arkraft-api containers up" \
  || echo "❌ arkraft-api containers NOT up"

# Web listening
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 \
  | grep -qE "200|30[27]" && echo "✅ arkraft-web responding on :3000" \
  || echo "❌ arkraft-web NOT responding"

# Agent images
for IMAGE in arkraft-alpha:latest arkraft-insight:latest arkraft-portfolio:latest; do
  docker image inspect "$IMAGE" >/dev/null 2>&1 \
    && echo "✅ image $IMAGE present" \
    || echo "⏭  image $IMAGE not built (only failures for agents you selected in Step 2 matter)"
done

# Catalog parquet in local MinIO (the actual requirement for alpha)
OBJS=$(AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
  aws --endpoint-url http://localhost:9000 s3 ls \
  s3://arkraft-staging/teams/arkraft/catalogs/ --recursive 2>/dev/null | wc -l | tr -d ' ')
[ "$OBJS" -gt 0 ] 2>/dev/null \
  && echo "✅ MinIO teams/arkraft/catalogs: $OBJS objects" \
  || echo "❌ MinIO teams/arkraft/catalogs empty — alpha agent cannot load parquet. Re-run Step 5."

# Chrome CDP
curl -s http://localhost:9222/json/version >/dev/null \
  && echo "✅ Chrome CDP on :9222" \
  || echo "❌ Chrome CDP NOT open"

echo "────────────────────────────────────────────────────"
pwd  # expect: /Users/wogus/Project/arkraft
```

If every line starts with `✅` (or `⏭` for agents you intentionally skipped), onboarding is complete. Open <http://localhost:3000> in the debug Chrome window and sign in.

---

## Path Reference

| Item | Value |
|------|-------|
| Repo root | `/Users/wogus/Project/arkraft` |
| API repo | `/Users/wogus/Project/arkraft/arkraft-api` |
| Web repo | `/Users/wogus/Project/arkraft/arkraft-web` |
| Agent repos (docker-compose ready) | `arkraft-agent-alpha`, `arkraft-agent-insight`, `arkraft-agent-portfolio` |
| Dev Web | <http://localhost:3000> |
| DB (local) | `postgresql://postgres:postgres@localhost:5432/arkraft` |
| DB (staging, via SSM) | `postgresql://arkraft@localhost:25432/arkraft_staging` |
| Cookie key | `team_id` |
| Web log | `/tmp/arkraft-web-dev.log` |
| Chrome debug log | `/tmp/chrome-debug.log` |
| MinIO (local S3) | `http://localhost:9000` (minioadmin/minioadmin) |
| CDP port | `9222` (Chrome remote debugging) |

## Agent Image Names

| Agent repo | Image tag | Notes |
|------------|-----------|-------|
| `arkraft-agent-alpha` | `arkraft-alpha:latest` | Needs `GITHUB_TOKEN` for private `arkraft-sdk` pull. |
| `arkraft-agent-insight` | `arkraft-insight:latest` | |
| `arkraft-agent-portfolio` | `arkraft-portfolio:latest` | |

`arkraft-agent-report`, `arkraft-agent-data`, `arkraft-agent-extract` have no local `docker-compose.yml` and are out of scope for this skill — add them here when they get one.

## Related Skills (all at arkraft root)

- **`sync-s3-to-minio`** — invoked by Step 5 with prefix `teams/arkraft/catalogs/`. The actual workhorse of local-setup's data seeding.
- **`dump-remote-rds`** — out of scope for local-setup. Run separately if you need real staging DB rows for UI work.
- **`connect-remote`** — ad-hoc SSM tunnels for RDS/Redis for raw DB inspection.
- **`create-test-datasource`** — synthesize a local data source instead of mirroring.
- **`workflow-seed-and-test`** — seed security_master + upload E2E CSVs (alternative data seed).
