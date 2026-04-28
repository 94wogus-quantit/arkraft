---
paths:
  - "arkraft-agent-*/**"
  - "arkraft-alpha-agent/**"
---

# Agent 서비스 컨벤션

## 공통 스택

- Python 3.14 (alpha-agent: 3.11)
- 패키지 매니저: `uv`
- Claude Agent SDK
- MCP로 도구 통합 (Jupyter, alpha-pool 등)

## 명령어

```bash
uv sync                     # 의존성 설치
uv run pytest               # 테스트
ruff check .                # 린트
ruff format .               # 포맷
```

## 프로젝트 구조

```
src/
├── agent.py                # Claude Agent SDK 옵션
├── main.py                 # CLI/서버 진입점
├── handler.py              # SDK 메시지 핸들러 + S3 동기화
└── mode/                   # 실행 모드 (discover, optimize 등)

workspace/
├── CLAUDE.md               # 에이전트 시스템 프롬프트 (AI 에이전트의 자체 지시문)
├── .mcp.json               # MCP 서버 설정
└── .claude/settings.json   # Claude Code 설정 & 훅
```

## 에이전트 종류 & 진입점

| 에이전트 | 명령어 |
|----------|--------|
| alpha | `python main.py discover --session-id ID --topic-id ID` |
| insight | `uv run arkraft-insight "topic"` |
| portfolio | `uv run arkraft-portfolio --session-id ID --intent "request"` |
| report | `uv run arkraft-report-server` (포트 8888) |

## 환경 변수

| 변수 | 용도 |
|------|------|
| `CLAUDE_OAUTH_TOKEN_{N}` | 로테이션용 OAuth 토큰 (N=1,2,3) |
| `AVAILABLE_TOKENS` | 사용할 토큰 번호 (기본값: `1,2,3`) |
| `CALLBACK_API_URL` | API 서버 콜백 URL |
| `S3_BUCKET` | 결과물 S3 버킷 |

## Docker

모든 에이전트 이미지: 멀티스테이지 빌드 (Python 베이스) + Node.js + Claude CLI.
non-root 사용자 (uid 1000). 진입점: `uv run --no-sync python main.py`.
