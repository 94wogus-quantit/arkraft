---
name: fetch-all
description: Fast-forward `staging` and `main` of the meta-repo and every submodule to `origin` in one shot. Use when the user asks to "fetch all", "전 레포 fetch", "staging/main 동기화", "submodule 다 최신화", "repo 전체 staging main fetch origin", or similar bulk-sync requests. Updates local refs without checking out (uses `git fetch origin <branch>:<branch>`) so the user's working branch is untouched; for whichever branch *is* checked out, performs `git pull --ff-only` instead. Reports a per-repo summary of which branches advanced, which were skipped (no remote ref), and which failed (non-FF / conflict).
user-invocable: true
---

# fetch-all — Bulk fast-forward `staging` + `main` across the meta-repo

Brings the **local** `staging` and `main` refs of the meta-repo and every submodule up to `origin` — without touching the working tree or the currently checked-out feature branch beyond a safe fast-forward.

## Why this skill exists

Doing this manually has two annoying shapes:

1. **`git fetch origin staging main`** only updates the *remote-tracking* refs (`origin/staging`, `origin/main`). Local `staging` / `main` stay stale until you check them out and pull — but you can't check them out without leaving your feature branch.
2. **`git fetch origin main:main`** updates the local ref directly, *except* it refuses if `main` is currently checked out (`fatal: Refusing to fetch into current branch`).

This skill does the right thing in each case automatically, and applies it across the meta-repo + all submodules in a single pass.

## What it does

For the meta-repo and each submodule:

For each branch in `{staging, main}`:

1. **Remote ref missing?** (e.g. ai-infra has no `staging`) → skip with `[skip] no origin/<branch>`.
2. **Branch currently checked out?** → `git pull --ff-only origin <branch>`. Conflict / divergence prints a warning, then continues to next repo. Never resets, never force-pulls.
3. **Branch not checked out?** → `git fetch origin <branch>:<branch>`. If the local ref would not fast-forward, git prints `! [rejected] (non-fast-forward)` — the skill records it as a failure and moves on. Never `+<branch>:<branch>` (force-update), never `--update-head-ok`.

## Safety guarantees

- **Working tree untouched** for any branch other than the one currently checked out.
- **No force updates.** Non-FF cases are surfaced as failures, not silently overwritten.
- **No checkout.** The user's current branch stays current.
- **Read-only on remote.** No push, no PR, no commit.

## Execution

Run from the **arkraft monorepo root** (`/Users/wogus/Project/arkraft`). The skill scopes itself to that directory and its submodules — it never touches other clones.

```bash
# Location guard
cd /Users/wogus/Project/arkraft
```

Then execute, in this exact order:

### Step 1 — Meta-repo

```bash
bash .claude/skills/fetch-all/fetch_one.sh .
```

### Step 2 — All submodules in one pass

```bash
git submodule foreach --quiet '
  bash "$toplevel/.claude/skills/fetch-all/fetch_one.sh" .
'
```

### Step 3 — Print final summary

The per-repo lines already stream to stdout in steps 1–2. After they finish, restate the totals in the conversation so the user can scan at a glance:

- count of repos where everything advanced
- list of repos with at least one `[skip]` (no `origin/<branch>`)
- list of repos with at least one `[fail]` (non-FF / conflict) — these are the ones the user actually needs to look at

If any `[fail]` appeared, surface it prominently — that's usually local commits on `staging`/`main` (which violates the rule in `.claude/rules/git-workflow.md`) or a divergent rebase.

## Output format (per repo)

```
=== <repo-name> ===
  staging  [ok]    fast-forward a1b2c3d..d4e5f6a
  main     [skip]  no origin/main
```

Possible status tokens:

| token  | meaning                                                          |
|--------|------------------------------------------------------------------|
| `ok`   | local ref advanced (or was already up to date)                   |
| `skip` | remote branch doesn't exist for this repo                        |
| `fail` | `pull --ff-only` failed, or `fetch <br>:<br>` was rejected       |

## Known repo topology (2026-05 snapshot, validate before relying)

| Has `staging` | Has only `main` |
|---|---|
| arkraft-agent-{alpha,data,extract,insight,portfolio} | arkraft (meta) |
| arkraft-api | ai-infra |
| arkraft-jupyter | arkraft-cli |
| arkraft-web | arkraft-deploy |
|  | arkraft-sdk |
|  | arkraft-wiki |

The `[skip]` branch above handles whatever the actual remote layout is at runtime — the table is just orientation, not config the skill reads.

## Non-goals

- **Does not pull feature branches.** Only `staging` and `main`. If the user wants to sync `wogus/ARK-XXX`, they should `git pull --rebase` themselves on that branch.
- **Does not run `git submodule update`.** Submodule pins in the meta-repo are not touched; only the submodules' own branch refs.
- **Does not push.** Read-only against `origin`.
- **Does not rebase your feature branch onto fresh `staging`.** That's a separate, deliberate step (see `.claude/rules/git-workflow.md` § "리모트 대상 브랜치 최신 상태 필수").
