# arkraft

> **AI 기반 퀀트 리서치 및 포트폴리오 관리 플랫폼** (by Quantit)

이 레포는 arkraft 제품을 구성하는 12개 서브 레포지토리를 묶는 **메타-레포(meta repo)** 다. 각 서브 레포는 자체 GitHub 레포 + 자체 PR 워크플로우를 그대로 유지하며, 메타-레포는 단지 "어떤 commit hash에서 모두를 같이 보고 있는지" 한 시점의 스냅샷을 git submodule로 pin 한다.

## Repo 맵

| Submodule | Stack | 역할 | Branch |
|-----------|-------|------|--------|
| [`arkraft-api`](./arkraft-api) | Python 3.12, FastAPI, SQLAlchemy 2.0 async | Backend API (port 3002) | `staging` |
| [`arkraft-web`](./arkraft-web) | Next.js 16, React 19, TypeScript, pnpm | Frontend (port 3000) | `staging` |
| [`arkraft-agent-alpha`](./arkraft-agent-alpha) | Python 3.14, Claude Agent SDK | Alpha 전략 발굴 에이전트 (6-phase) | `staging` |
| [`arkraft-agent-insight`](./arkraft-agent-insight) | Python 3.14, Claude Agent SDK | 리서치 가설 에이전트 | `staging` |
| [`arkraft-agent-portfolio`](./arkraft-agent-portfolio) | Python 3.14, Claude Agent SDK + MCP | 포트폴리오 구성 에이전트 | `staging` |
| [`arkraft-agent-data`](./arkraft-agent-data) | Python 3.14, Claude Agent SDK | RDS Scan & File Sync 에이전트 | `staging` |
| [`arkraft-agent-extract`](./arkraft-agent-extract) | Python 3.14, Claude Agent SDK | 데이터 추출 에이전트 | `staging` |
| [`arkraft-deploy`](./arkraft-deploy) | Helm, ArgoCD, Argo Workflows | K8s 배포 차트 / Argo 템플릿 | `main` |
| [`ai-infra`](./ai-infra) | Terraform + Atlantis | AWS 인프라 (EKS, RDS, ElastiCache, Istio) | `main` |
| [`arkraft-sdk`](./arkraft-sdk) | Python | 공통 quant SDK | `main` |
| [`arkraft-cli`](./arkraft-cli) | — | 운영 CLI 도구 | `main` |
| [`arkraft-wiki`](./arkraft-wiki) | Markdown + 정적 HTML | 팀 위키 (`arkraft-manager.git`) | `main` |

> 시스템 전체의 데이터 플로우 / 인증 / 외부 의존성은 [`ARCHITECTURE.md`](./ARCHITECTURE.md) 참고.

## Quick start (신규 팀원)

```bash
# 1. 메타-레포 + 12개 submodule 한 번에 클론
git clone --recurse-submodules git@github.com:94wogus-quantit/arkraft.git
cd arkraft

# 2. 이미 클론한 경우 누락된 submodule 채우기
git submodule update --init --recursive

# 3. 로컬 개발 환경 부트스트랩 (docker / aws / pnpm 일괄 세팅)
#    Claude Code 안에서 실행:
#    Skill(skill: "local-setup")
```

각 submodule은 자기 default branch(`staging` 또는 `main`)로 체크아웃된다 (위 표 참고). submodule이 detached HEAD 상태이면 `git submodule foreach 'git checkout $(git config -f $toplevel/.gitmodules submodule.$name.branch)'` 로 트래킹 브랜치로 옮길 수 있다.

## 디렉터리 구조 (1-depth)

```
arkraft/
├── ARCHITECTURE.md         시스템 deep-dive (데이터 플로우, 인증, 외부 의존성)
├── CLAUDE.md               Claude Code가 따라야 할 룰의 단일 진입점
├── README.md               이 문서 (메타-레포 입구)
├── .claude/
│   ├── rules/              팀 컨벤션 (jira, slack, git-workflow, architecture, ...)
│   ├── skills/             자주 쓰는 스킬 (local-setup, connect-remote, dump-remote-rds, ...)
│   └── settings.json       팀 공유 Claude Code 설정 (settings.local.json은 개인용 — gitignore)
├── ai-infra/               (submodule) Terraform 인프라
├── arkraft-agent-alpha/    (submodule) Alpha 전략 에이전트
├── arkraft-agent-data/     (submodule)
├── arkraft-agent-extract/  (submodule)
├── arkraft-agent-insight/  (submodule)
├── arkraft-agent-portfolio/(submodule)
├── arkraft-api/            (submodule) Backend API
├── arkraft-cli/            (submodule)
├── arkraft-deploy/         (submodule) K8s 차트 / Argo 템플릿
├── arkraft-sdk/            (submodule) 공통 SDK
├── arkraft-web/            (submodule) Next.js Frontend
└── arkraft-wiki/           (submodule, repo=arkraft-manager.git) 팀 위키
```

## 작업 흐름

이 메타-레포 자체에는 비즈니스 로직 코드가 없다. 실제 기능 작업은 **각 submodule 안에서** 그 submodule의 워크플로우를 따라 진행한다:

1. **이슈 분석 → 계획 → 실행 → 문서화 (4단계 wf 파이프라인)**: [`.claude/rules/git-workflow.md`](./.claude/rules/git-workflow.md) — `wf:analyze` → `wf:plan` → `wf:execute` → `wf:record`
2. **Jira**: 프로젝트 키 `ARK`. 활성 epic 매트릭스는 [`.claude/rules/jira.md`](./.claude/rules/jira.md)
3. **Slack**: 채널 ID, 팀/사용자 멘션, 메시지 템플릿은 [`.claude/rules/slack.md`](./.claude/rules/slack.md). `agent-browser`로 Slack 접근 금지 — Slack MCP 사용
4. **PR 규칙**: 모든 일반 작업은 submodule의 `staging` 대상, hotfix만 `main` + `staging` 동시 PR. 직접 push 금지. 머지 전 단일 commit 스쿼시

submodule 안에서 commit 후 sub-repo 자체 PR을 머지하면, 메타-레포에서는 새 commit hash로 pin을 갱신한다:

```bash
# 메타-레포에서 모든 submodule을 추적 브랜치 최신으로 끌어올리기
git submodule update --remote --recursive
git add <updated-submodule-paths>
git commit -m "chore: bump <submodule> to <new-hash>"
```

## 더 읽을 거리

| 문서 | 언제 보나 |
|------|-----------|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 시스템 전체 컴포넌트, 데이터 플로우, AWS 인프라, 인증 계층, MCP 구성 등 deep-dive |
| [`CLAUDE.md`](./CLAUDE.md) | Claude Code가 이 레포에서 따라야 할 룰의 단일 진입점 |
| [`.claude/rules/`](./.claude/rules) | 도메인별 컨벤션 모음 (architecture, web/api/agent/infra conventions, jira, slack, git-workflow, team-execution, wiki) |
| [`.claude/skills/`](./.claude/skills) | 자주 쓰는 스킬 (local-setup, connect-remote, dump-remote-rds, sync-s3-to-minio, create-test-datasource) |
| [`arkraft-wiki/`](./arkraft-wiki) | 팀 위키 (의사결정 기록, 마켓 리서치, 타임라인) |
