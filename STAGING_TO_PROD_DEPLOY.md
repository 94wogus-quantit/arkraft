# Staging → Production 자동 배포 가이드

> 한 시간마다 스케줄로 실행됨. 12개 submodule 중 staging이 main보다 앞선 레포만 골라 PR을 만들고 순차 배포한다.

## 0. 사전 점검 — 이번 사이클에 할 일이 있나

```bash
cd /Users/wogus/Project/arkraft
for repo in ai-infra arkraft-agent-alpha arkraft-agent-data arkraft-agent-extract arkraft-agent-insight arkraft-agent-portfolio arkraft-api arkraft-cli arkraft-deploy arkraft-sdk arkraft-web arkraft-wiki; do
  cd "/Users/wogus/Project/arkraft/$repo"
  git fetch origin staging main --quiet 2>/dev/null
  ahead=$(git rev-list --count origin/main..origin/staging 2>/dev/null)
  [ "$ahead" -gt 0 ] 2>/dev/null && echo "$repo: $ahead commits ahead"
  cd /Users/wogus/Project/arkraft
done
```

- 출력이 비어 있으면 **이번 사이클은 스킵**. 종료.
- `staging` 브랜치 없는 레포는 자동 제외 (`fetch` 실패) — `ai-infra`, `arkraft-cli`, `arkraft-deploy`, `arkraft-sdk`, `arkraft-wiki`는 staging 운영 안 함.

## 1. 각 후보 레포의 변경 요약 추출

```bash
cd /Users/wogus/Project/arkraft/<repo>
git log --oneline --no-decorate origin/main..origin/staging
```

- merge commit + 본 커밋이 함께 보임. 본 커밋(merge 커밋 아닌 것)을 PR 본문에 정리.
- merge commit 메시지에서 `Merge pull request #N from <branch>` 형식으로 PR 번호 추출 → **Included PRs** 섹션.

## 2. PR 생성

기존 release PR이 이미 있는지 확인 후 없을 때만 생성:

```bash
gh pr list --base main --head staging --json number -q '.[0].number'
```

비어있으면 새 PR 생성:

```bash
cd /Users/wogus/Project/arkraft/<repo>
gh pr create --base main --head staging \
  --title "release: staging → main ($(date +%Y-%m-%d))" \
  --body "$(cat <<'EOF'
## Summary
staging 누적 변경사항을 production(main)으로 배포.

## Changes
- {fix/feat 한 줄 요약}

## Included PRs
- #<num> <branch-name>

## Test plan
- [ ] production 배포 후 동작 확인
EOF
)"
```

> MCP `create_pull_request`에는 줄바꿈 버그가 있음 → **반드시 `gh` + HEREDOC** 사용.

## 3. 배포 순서 결정 (의존성 그래프)

지금까지 관찰된 의존성:

| Producer (먼저 배포) | Consumer (뒤에 배포) |
|----|----|
| `arkraft-api` 새 endpoint | `arkraft-web` (wizard, report 등이 호출) |
| `arkraft-api` 새 internal endpoint | `arkraft-agent-portfolio` (SDK alpha registry 등) |
| `arkraft-api` 새 internal endpoint | `arkraft-agent-{alpha,insight,extract,data}` |
| 독립 변경 (validator, lint 등) | 우선순위 무관 — 마지막 |

**기본 순서**: `arkraft-api` → `arkraft-agent-*` → `arkraft-web` → 독립 변경.
- 단, **commit log를 보고 새 endpoint·계약 변경 키워드 (`feat`, `internal`, `endpoint`, `route`, `schema`)가 있으면** producer로 분류해 먼저 배포.
- producer-consumer 관계가 불분명하면 그냥 알파벳 순으로 진행해도 OK (서비스가 backward-compatible 한 변경이면 안전).

## 4. 순차 머지 + 모니터링 — 한 PR씩

각 PR에 대해 아래 5단계를 **반드시 완료**한 뒤 다음 PR로 넘어갈 것.

### 4.1 PR check 완료 대기 + SUCCESS 확인

```bash
cd /Users/wogus/Project/arkraft/<repo>
until [ "$(gh pr view <PR> --json statusCheckRollup -q '[.statusCheckRollup[] | select(.status != "COMPLETED")] | length')" = "0" ]; do sleep 30; done
gh pr view <PR> --json mergeStateStatus,statusCheckRollup -q '{state: .mergeStateStatus, checks: [.statusCheckRollup[] | {name, conclusion}]}'
```

- 모든 conclusion이 `SUCCESS`이고 `mergeStateStatus`가 `CLEAN` (또는 mergeable=`MERGEABLE`)이어야 머지.
- 하나라도 `FAILURE` / `CANCELLED` → **즉시 중단**, 사용자에게 알림.
  - **이유**: Quantit-Github free plan은 private repo branch protection 미지원이라 GitHub이 머지를 막아주지 않음. 사람 룰로만 차단.

### 4.2 머지

```bash
gh pr merge <PR> --merge
```

- **`--merge`만 사용** (squash/rebase 금지). release PR은 staging 커밋들을 main에 그대로 보존해야 함.
- **`--delete-branch` 절대 금지**. `staging`은 영구 기본 브랜치.

### 4.3 Auto Tagging 워크플로우 완료 확인

머지 직후 `Auto Tagging` (push to main → 새 태그 생성) 트리거됨.

```bash
sleep 15
gh run list --workflow="Auto Tagging" --limit 1 --json databaseId,status,conclusion,headSha
```

`status=completed conclusion=success` 이면 새 태그가 push됨 → `Production Build` 자동 트리거.

### 4.4 Production Build 워크플로우 완료 대기

```bash
gh run list --workflow="Production Build" --limit 1 --json databaseId,headBranch,headSha
# 새 태그(예: 0.2619.1)와 머지 commit sha 확인
gh run watch <RUN_ID> --exit-status
```

- jobs: `test` → `build-arm64` / `build-amd64` → `create-manifest` → `gitops`
- 모두 SUCCESS 되어야 ECR push + GitOps repo manifest 업데이트 완료.
- `gitops` job이 끝나면 ArgoCD가 자동 sync해 prod에 반영. **다음 PR 머지 가능**.

### 4.5 다음 PR로 (1단계 건너뛰지 말 것)

이전 PR의 `gh run watch` exit code가 0인 걸 확인한 뒤에만 다음 PR의 4.1로 넘어갈 것.

## 5. 자동화 동작 규칙

- **무변경**: 0단계에서 후보 0개면 그냥 종료 (PR도 만들지 않음).
- **에러 시**: 어느 단계든 실패하면 즉시 중단하고 Slack `#project_ark`(C0933M2A5CK)에 보고. 사람이 개입해야 함.
- **로그**: 각 사이클의 결과(머지된 PR, 태그, 실패 사유)를 마지막에 한 표로 요약 출력.

## 6. 안전 가드 — 자동화에서 절대 하지 말 것

| 금지 | 이유 |
|------|------|
| `gh pr merge --delete-branch` | staging 브랜치 삭제 = 시스템 전체 깨짐 |
| `gh pr merge --squash` 또는 `--rebase` | release PR은 staging 커밋 보존 필요 |
| CI fail PR 머지 | branch protection 없음 — 사람 룰만 신뢰. 즉시 중단 |
| hotfix 워크플로우와 혼동 | 이 자동화는 일반 release만. `hotfix/*` 브랜치는 사용자가 직접 처리 |
| 메타-레포 submodule pin 자동 갱신 | 별도 작업. 이 자동화 범위 아님 |
| `staging` / `main` 직접 push | PR 외 경로 절대 금지 |

## 7. 의존성 매트릭스 업데이트

새로운 PR에서 producer-consumer 관계를 발견하면 이 문서의 §3 표를 갱신할 것. 이 가이드는 living document — 자동화가 잘못된 순서로 머지하지 않도록 배운 걸 항상 기록.
