# CLAUDE.md

> 이 파일은 **Claude Code가 arkraft 메타-레포에서 작업할 때 따라야 할 룰의 단일 진입점**이다. 새 세션이 열릴 때 자동으로 컨텍스트에 로드된다.

## 이 레포가 뭔지

`arkraft`는 12개 서브 레포지토리를 git submodule로 묶은 **메타-레포**다. 시스템 전체 개요와 사용자용 입구는 [`README.md`](./README.md), 시스템 deep-dive는 [`ARCHITECTURE.md`](./ARCHITECTURE.md)에 있다. 이 파일은 그 두 문서와 역할이 다르다 — 여기는 *팀 컨벤션 / 자동화 룰 / 자주 쓰는 스킬*의 인덱스다.

## 룰 인덱스 (`.claude/rules/`)

| 파일 | 한 줄 요약 |
|------|------------|
| [`agent-conventions.md`](./.claude/rules/agent-conventions.md) | `arkraft-agent-*` 레포 공통 컨벤션 (Claude Agent SDK + MCP) |
| [`api-conventions.md`](./.claude/rules/api-conventions.md) | `arkraft-api` 컨벤션 (FastAPI 의존성 주입, SQLAlchemy 2.0 async, Pydantic v2) |
| [`architecture.md`](./.claude/rules/architecture.md) | 4계층 클린 아키텍처(API), 레이어 아키텍처(Web), Agent 구조 — 임포트 방향 강제 |
| [`web-conventions.md`](./.claude/rules/web-conventions.md) | `arkraft-web` 컨벤션 (Next.js, React Compiler, CVA, `@infra/api`) |
| [`infra-conventions.md`](./.claude/rules/infra-conventions.md) | `ai-infra` Terraform/Atlantis GitOps 룰 |
| [`git-workflow.md`](./.claude/rules/git-workflow.md) | 브랜치 전략(`staging` 기본, hotfix만 `main`), PR 룰, 4단계 wf 파이프라인(`wf:analyze`→`plan`→`execute`→`record`), 단일 커밋 스쿼시 |
| [`jira.md`](./.claude/rules/jira.md) | Jira 프로젝트 키 `ARK`, 활성 에픽 매트릭스, 이슈/서브태스크 생성 패턴 |
| [`slack.md`](./.claude/rules/slack.md) | 채널 ID / 팀 멘션 / 사용자 ID 표 + 메시지 템플릿. **Slack는 MCP만 — `agent-browser` 금지** |
| [`team-execution.md`](./.claude/rules/team-execution.md) | 멀티-에이전트 팀 실행 룰. **사용자가 명시 요청할 때만 팀 생성** |
| [`wiki.md`](./.claude/rules/wiki.md) | Wiki = `arkraft-wiki/` 폴더 (Confluence 아님). 빌드는 `./build.sh` |

> `agent-conventions.md` / `api-conventions.md` / `web-conventions.md` / `infra-conventions.md`는 frontmatter의 `paths:` 글롭으로 해당 submodule 안에서만 자동 활성화된다.

## 자주 쓰는 스킬 (`.claude/skills/`)

| 스킬 | 언제 |
|------|------|
| [`local-setup`](./.claude/skills/local-setup) | 신규 팀원 온보딩 / 전체 dev 환경 리셋 (docker / aws / pnpm 일괄 세팅) |
| [`connect-remote`](./.claude/skills/connect-remote) | 프로덕션/스테이징 RDS·ElastiCache에 SSM 포트 포워딩 연결 |
| [`dump-remote-rds`](./.claude/skills/dump-remote-rds) | 원격 RDS → 로컬 Docker PostgreSQL 동기화 |
| [`sync-s3-to-minio`](./.claude/skills/sync-s3-to-minio) | 원격 S3 버킷 → 로컬 MinIO 동기화 |
| [`create-test-datasource`](./.claude/skills/create-test-datasource) | 테스트용 datasource 생성 |

호출은 `Skill(skill: "<name>")`. 자세한 트리거 문구는 각 스킬의 `SKILL.md` 참고.

## 문서 역할 분담

| 문서 | 읽는 사람 / 시점 | 무엇을 담나 |
|------|------------------|--------------|
| [`README.md`](./README.md) | 처음 클론한 사람 / 매니저 / Claude Code (자동 로드 X) | 메타-레포 입구, repo 맵, quick-start |
| [`CLAUDE.md`](./CLAUDE.md) | Claude Code (세션 시작 시 자동 로드) | 룰 + 스킬 인덱스 — 본문은 이 안에서 깊이 안 다룬다 |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 시스템 이해 필요한 모든 사람 | 컴포넌트, 데이터 플로우, 인증 계층, MCP, AWS 인프라 deep-dive |
| `.claude/rules/*.md` | Claude Code가 도메인별로 자동 로드 (frontmatter glob) | 각 도메인의 실제 컨벤션 본문 |

**중복 금지 원칙**: 본 CLAUDE.md / README.md는 위 4개 카테고리의 *입구*만 제공한다. 동일 내용을 여기서 다시 풀어쓰지 말 것 — 각 룰 파일을 갱신하면 된다.

## Submodule 작업 주의

이 레포에서 sub-repo 안의 파일을 직접 편집하더라도, **commit / push는 그 sub-repo 자체의 워크플로우(자기 PR, 자기 브랜치 전략)를 따른다**:

- 메타-레포의 `git status`는 submodule을 "modified content" 1줄로만 보여준다 — 실제 변경은 `cd <submodule> && git status`로 봐야 한다.
- sub-repo PR이 머지된 뒤, 메타-레포는 단지 새 commit hash로 pin을 갱신한다 (`git add <submodule>` → 새 commit).
- 메타-레포에서는 sub-repo의 `staging`/`main` 브랜치에 **직접 push하지 말 것** — 반드시 sub-repo 안에서 별도 브랜치로 PR.
- 작업 디렉터리 이동 후 메타-레포 루트로 돌아오는 게 안전 (`cd /Users/wogus/Project/arkraft`) — 일부 도구가 cwd에 의존한다.

## 안전 가드

- **`ARCHITECTURE.md`는 53,985 bytes 시스템 문서다 — 직접 수정하지 말 것**. 시스템 변경은 sub-repo PR이 머지된 뒤 별도 작업으로 갱신한다.
- **`.claude/settings.local.json`은 개인용** (gitignore). 팀 공유 설정은 `.claude/settings.json`에만.
- **`.archive/`, `.ralph/`는 gitignore** — 옛 보고서/계획과 ralph-loop 상태 파일.
- 메타-레포 `git push --force` **금지**. submodule pin 갱신은 항상 새 commit으로.

## 메타-레포 commit 컨벤션

이 레포에서 직접 만드는 commit은 보통 다음 셋 중 하나다:

| 패턴 | 메시지 예 |
|------|-----------|
| Submodule pin 갱신 | `chore: bump arkraft-api to 1a2b3c4 (PR #481)` — 가능하면 PR 번호 포함 |
| 메타-레포 문서 변경 | `docs: ...` (README.md / CLAUDE.md / ARCHITECTURE.md 갱신) |
| 메타-레포 설정 변경 | `chore: ...` (.gitignore / .claude/rules / .claude/settings.json) |

여러 submodule을 한 번에 bump 한다면 한 commit에 묶어도 OK — 단 메시지에 어떤 submodule들이 어디로 갔는지 명시.

## 자주 쓰는 명령 cheatsheet

```bash
# 12개 submodule의 추적 브랜치 최신으로 끌어올리기
git submodule update --remote --recursive

# 모든 submodule을 자기 추적 브랜치로 체크아웃 (detached HEAD 해소)
git submodule foreach 'git checkout $(git config -f $toplevel/.gitmodules submodule.$name.branch)'

# 어떤 submodule이 dirty 한지 한 번에 확인
git submodule foreach --quiet 'git status --porcelain | head -1 && echo'

# 메타-레포에서 본 submodule pin 상태 (commit hash + tag/branch 정보)
git submodule status
```

## 워크플로 / 자동화 진입점

| 작업 | 진입점 |
|------|--------|
| Jira 이슈 분석 → 계획 → 실행 → 문서화 | `wf:analyze` → `wf:plan` → `wf:execute` → `wf:record` (자세히는 `.claude/rules/git-workflow.md`) |
| 다중 iteration 자동화 (코드 + 디자인 + 문서) | `run-ralph:choo-choo` 스킬 — multi-agent + acceptance criteria + 게이팅 |
| 신규 팀원 dev 환경 부트스트랩 | `Skill(skill: "local-setup")` |
| 원격 DB / 데이터 동기화 | `Skill(skill: "connect-remote" / "dump-remote-rds" / "sync-s3-to-minio")` |

## 사용자 메모

- 사용자 ID: `wogus` / 이메일 `94wogus@quantit.io` (commit author)
- AWS 리전: `ap-northeast-2` (Seoul)
- Jira 프로젝트: `ARK`
- 회사 GitHub Org (sub-repo들): `Quantit-Github` — 단 메타-레포 자체는 개인 계정 `94wogus-quantit/arkraft.git`
