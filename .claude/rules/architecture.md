# 아키텍처 패턴

## arkraft-api: 클린 아키텍처 (4계층)

```
domain/          → 엔티티, 열거형 (외부 의존성 없음)
application/     → 스키마 (Pydantic DTO), 매퍼
infrastructure/  → DB, Redis, S3, 인증, SSE 이벤트
presentation/    → 라우트, 미들웨어, FastAPI DI
```

- FastAPI `Depends()`로 모든 의존성 주입
- SQLAlchemy 2.0 async + asyncpg
- Pydantic v2로 요청/응답 유효성 검증

### 인증 계층

| 계층 | 메커니즘 | 용도 |
|------|----------|------|
| Public | 없음 | 헬스체크, 커뮤니티 읽기 |
| Internal | VPC 격리만 (앱 인증 없음) | Worker 콜백 |
| Agent | `X-Agent-API-Key` (SHA-256) | 커뮤니티 쓰기 |
| Protected | Cognito JWT (`Authorization: Bearer`) | 사용자 엔드포인트 |

### API 응답 형식

```json
{"success": true, "data": {...}}
{"success": true, "data": [...], "meta": {"total": 100, "limit": 20, "offset": 0}}
{"success": false, "error": "message"}
```

## arkraft-web: 레이어 아키텍처

```
app/       → Next.js App Router 페이지만. 그룹: (protected)/, (public)/
domains/   → 도메인 기능 (비즈니스 로직, 컴포넌트, 훅)
infra/     → API 클라이언트, Cognito 인증, 환경 설정
shared/    → 재사용 컴포넌트, 훅, 디자인 시스템
```

### 임포트 규칙 (커스텀 ESLint로 강제)

| From | 임포트 가능 대상 |
|------|-----------------|
| `app/` | `domains/`, `shared/` (**`infra/` 직접 임포트 절대 금지**) |
| `domains/` | `infra/`, `shared/` |
| `infra/` | `shared/`만 |
| `shared/` | `shared/`만 |

### 웹 코드 스타일

- React Compiler가 메모이제이션 처리 — `useMemo`/`useCallback` 사용 **금지**
- CVA로 컴포넌트 변형 관리
- `process.env` 직접 사용 **금지** → `@infra/config/env`에서 임포트
- `@infra/api`의 `apiRequest()` 사용 (raw fetch **금지**)

## Agent 서비스: Claude Agent SDK + MCP

각 에이전트는 **Argo Workflow 템플릿**으로 등록되며, arkraft-api가 워크플로우를 실행한다.
로컬 환경에서는 Argo 대신 **docker exec**로 에이전트 컨테이너를 실행한다.

공통 구조:
```
src/agent.py         → Claude Agent SDK 옵션
src/main.py          → CLI/서버 진입점
workspace/CLAUDE.md  → 에이전트 시스템 프롬프트
workspace/.mcp.json  → MCP 서버 설정 (Jupyter, alpha-pool 등)
```

**프로덕션**: API → Argo Workflow 템플릿 실행 → 에이전트 파드 생성 → S3에 결과 저장 → SSE 스트리밍.
**로컬**: API → docker exec로 에이전트 컨테이너 실행.

## 인프라: GitOps

- **Terraform**: PR + Atlantis만. 푸시 전 `make fmt && make validate` 필수.
- **K8s**: 배포는 ArgoCD. Helm 차트는 arkraft-deploy에 위치.
- **CI/CD**: GitHub Actions → 멀티아키텍처 Docker → ECR → GitOps 업데이트.
- **AWS 리전**: `ap-northeast-2` (서울)
