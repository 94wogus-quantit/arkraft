# Git & PR 워크플로우

## 브랜치 전략

### 기본 브랜치: `staging`

`staging`이 모든 레포의 기본 브랜치 (`arkraft-deploy`만 `main` 사용).
모든 일반 기능/버그 수정 작업은 `staging`을 대상으로 한다.

```
staging  ← 기본 브랜치 (일반 작업의 PR 대상)
main     ← 프로덕션 브랜치 (핫픽스로만 변경)
```

### 브랜치 네이밍

| 유형 | 패턴 | 대상 |
|------|------|------|
| 기능 / 버그 수정 | `wogus/<JIRA-ISSUE-ID>` | `staging` |
| 핫픽스 | `hotfix/wogus/<JIRA-ISSUE-ID>` | `main` + `staging` 동시 PR |

예시:
- `wogus/ARK-715` → `staging`으로 PR
- `hotfix/wogus/ARK-999` → `main` PR + `staging` PR 각각 생성 후 모두 머지

## PR 규칙 (최우선 — 다른 모든 Git 규칙보다 우선)

### staging 또는 main에 직접 커밋 절대 금지

- `staging` 또는 `main`에 직접 커밋은 **엄격히 금지**. 반드시 별도 브랜치 생성.
- 브랜치 → PR → 머지만 허용. 직접 푸시 금지.

### 핫픽스 플로우

긴급한 프로덕션 수정이 필요한 경우:

1. `main`에서 브랜치 생성: `git checkout -b hotfix/wogus/<JIRA-ISSUE-ID> main`
2. 수정 후 커밋 스쿼시
3. 최신 `main`으로 리베이스
4. 동일 브랜치에서 **`main`과 `staging` 양쪽에 각각 PR 생성** 후 모두 머지

```
                 ┌──→ main   (PR #1)
hotfix/wogus/ARK-XXX
                 └──→ staging (PR #2)
```

> 자동 동기화 워크플로우 없음. hotfix는 반드시 양쪽 PR을 모두 머지해야 한다. 한쪽만 머지 시 divergence가 누적된다.

### 머지 전 단일 커밋 스쿼시 필수

- **머지 방법**: 항상 `--merge` (squash/rebase 머지 금지)
- 머지 전 브랜치 커밋을 **반드시 단일 커밋으로 스쿼시**.
- 스쿼시 방법: `git rebase -i staging` (핫픽스는 `main`) 또는 `git reset --soft staging && git commit`
- **기능/버그 수정**: 머지 전 최신 `staging`으로 리베이스
- **핫픽스**: 머지 전 최신 `main`으로 리베이스
- 스쿼시된 커밋 제목과 설명에 **이전 작업 내용을 빠짐없이 포함**해야 한다.

### 리모트 대상 브랜치 최신 상태 필수 (머지 전 검증)

- PR 브랜치 HEAD에 최신 리모트 대상 브랜치 커밋이 포함되어야 함. 동기화 없이 머지 **엄격히 금지**.
- **PR 생성/머지 전**: 항상 리모트 대상 브랜치와 동기화 (일반 작업은 `staging`, 핫픽스는 `main`):
  ```bash
  # 일반 작업
  git fetch origin staging:staging
  git rebase staging
  # 충돌 발생 시 해결
  git push --force-with-lease

  # 핫픽스
  git fetch origin main:main
  git rebase main
  # 충돌 발생 시 해결
  git push --force-with-lease
  ```
- 리베이스 충돌 해결 시, **변경 내용을 사용자에게 보고**하고 머지 전 확인.
- **머지 명령어**:
  ```bash
  gh pr merge <PR_NUMBER> --merge --delete-branch
  ```

### 리베이스 후: Alembic 마이그레이션 체인 복구 (arkraft-api)

arkraft-api 브랜치를 staging으로 리베이스한 후, 브랜치에 마이그레이션 파일이 포함되어 있으면 **항상 Alembic 마이그레이션 체인을 확인하고 복구**해야 한다.

**이유**: 리베이스는 브랜치의 베이스 커밋을 변경한다. 브랜치 마이그레이션의 `down_revision = 'X'`인데 staging에 `X` 이후 마이그레이션이 추가되었으면, 체인이 깨진다 (`X`에서 복수 헤드 발생).

**절차**:

```bash
# 1. 깨진 체인 감지
docker exec arkraft-api-server-1 alembic current
# → "Multiple head revisions" 에러 = 체인 깨짐

# 2. staging HEAD 마이그레이션 확인
git show origin/staging:alembic/versions/ | tail   # 최신 파일 찾기
# 해당 revision ID 확인

# 3. 기존 마이그레이션 파일 삭제 (편집 절대 금지)
rm alembic/versions/<old_migration_id>_*.py

# 4. DB가 staging HEAD 상태인지 확인 (필요 시 make full-reset)
make migrate  # 또는 docker exec alembic current 확인

# 5. staging HEAD 기반으로 마이그레이션 재생성
make migration msg="<원래 설명>"

# 6. FK 삭제 순서 수정 (autogenerate 순서 오류 시)
# (알려진 alembic 한계: FK 제약조건을 테이블 삭제 전에 삭제해야 함)
# 확인: grep "drop_constraint\|drop_table" alembic/versions/<new_file>.py
# drop_constraint 줄을 참조 테이블의 drop_table 앞으로 이동

# 7. 마이그레이션 정상 적용 확인
make migrate

# 8. 커밋 및 푸시
git add alembic/versions/<new_migration_id>_*.py
git commit -m "fix(alembic): migration chain 재생성 (staging rebase 후 down_revision 수정)"
git push --force-with-lease
```

**FK 삭제 순서 수정 패턴** (흔한 autogenerate 버그):
```python
# 잘못됨 (autogenerate 기본값) — 테이블 삭제 시 FK 참조가 남아있음
op.drop_table('parent_table')           # ← 실패: FK가 아직 존재
op.drop_constraint('child_table_fk', 'child_table', type_='foreignkey')

# 올바름 — 참조 테이블 삭제 전에 FK 제약조건 먼저 삭제
op.drop_constraint('child_table_fk', 'child_table', type_='foreignkey')
op.drop_table('parent_table')           # ← 안전
```

## Jira 티켓 워크플로우

순서대로 진행할 것. 코드 변경부터 바로 시작하지 말 것.

### 1. 이슈 분석

**목적**: 근본 원인 분석 및 문제 이해

**호출 방법**:
```
Skill(skill: "wf:analyze", args: "ARK-XXX")
```

**출력**: `ARK-XXX_REPORT.md` — 근본 원인 분석, 가설, 권장 사항 포함

**팀원에게 지시할 때**, 명시적 Skill 호출 포함:
```
"ARK-XXX 분석을 실행해. wf:analyze 스킬을 사용해:

Skill(skill: 'wf:analyze', args: 'ARK-XXX')

ARK-XXX_REPORT.md에 근본 원인 분석이 생성될 거야."
```

---

### 2. 구현 계획 수립

**목적**: 분석 결과 기반 상세 구현 계획

**호출 방법**:
```
Skill(skill: "wf:plan")
```

**입력**: 분석 단계의 `ARK-XXX_REPORT.md` 필요
**출력**: `[FEATURE]_PLAN.md` — 작업 분해, 의존성, 성공 기준 포함

**팀원에게 지시할 때**, 명시적 Skill 호출 포함:
```
"ARK-XXX_REPORT.md 기반으로 구현 계획을 세워. wf:plan 스킬을 사용해:

Skill(skill: 'wf:plan')

[FEATURE]_PLAN.md가 생성될 거야. 진행 전 사용자 승인을 기다려."
```

---

### 3. 구현 실행

**목적**: 승인된 계획 기반 코드 구현

**호출 방법**:
```
Skill(skill: "wf:execute")
```

**입력**: 승인된 `[FEATURE]_PLAN.md` 필요
**출력**: 구현된 코드, 테스트, 브랜치 + PR

**팀원에게 지시할 때**, 명시적 Skill 호출 포함:
```
"[FEATURE]_PLAN.md의 승인된 계획을 실행해. wf:execute 스킬을 사용해:

Skill(skill: 'wf:execute')

브랜치 생성, 코드 구현, 테스트 실행, PR 생성을 할 거야."
```

---

### 4. 변경 사항 문서화

**목적**: CHANGELOG 및 문서 업데이트

**호출 방법**:
```
Skill(skill: "wf:record")
```

**출력**: 업데이트된 CHANGELOG.md, CLAUDE.md 가이드, 머지 준비 완료

**팀원에게 지시할 때**, 명시적 Skill 호출 포함:
```
"변경 사항을 문서화해. wf:record 스킬을 사용해:

Skill(skill: 'wf:record')

CHANGELOG 업데이트 및 CLAUDE.md 가이드가 추가될 거야. 그 후 사용자에게 머지 승인을 요청해."
```

## 승인 후 PR

1. `Skill(skill: "wf:record")`로 변경 사항 문서화
2. 사용자에게 "머지할까요?" 확인
3. 승인 후 머지

## GitHub 작업

MCP 도구 우선 사용. 지원되지 않는 기능만 `gh` CLI 사용:

| 작업 | 도구 |
|------|------|
| PR 생성 | `mcp__plugin_github_github__create_pull_request` |
| PR 조회 | `mcp__plugin_github_github__get_pull_request` |
| PR 머지 | `mcp__plugin_github_github__merge_pull_request` |
| PR 파일 | `mcp__plugin_github_github__get_pull_request_files` |
| PR 상태 | `mcp__plugin_github_github__get_pull_request_status` |
| 이슈 생성 | `mcp__plugin_github_github__create_issue` |
| 브랜치 생성 | `mcp__plugin_github_github__create_branch` |

**참고**: MCP `create_pull_request`는 본문 줄바꿈 버그가 있음 → PR 생성/수정은 `gh` CLI + HEREDOC 사용.
