---
paths:
  - "arkraft-api/**"
---

# arkraft-api 컨벤션

## 명령어

```bash
make dev              # uvicorn --reload
make up               # Docker Compose 전체 시작
make test             # 유닛 + 통합 테스트 (Docker, full-reset)
make test-cov         # 커버리지 포함
make lint             # ruff check
make format           # ruff format
make migrate          # alembic upgrade head
make migration msg="desc"  # 마이그레이션 생성
make full-reset       # 볼륨 삭제 → 빌드 → 시작 → 마이그레이션
```

## Alembic 마이그레이션

**자동 생성된 마이그레이션 파일을 절대 수정하지 말 것.** 변경 전 반드시 사용자에게 확인.

## 파일 네이밍

- 라우트: `{domain}.py` → `presentation/routes/`
- 스키마: `{domain}.py` → `application/schemas/`
- 레포지토리: `{entity}_repository.py`

## 임포트 순서

```python
# 표준 라이브러리
from typing import Any

# 서드파티
from fastapi import APIRouter, Depends

# 로컬
from config import settings
from domain.entities.enums import WorkflowType
```

## 라우트 패턴

```python
# 사용자 인증 (Cognito JWT)
@router.get("/{id}")
async def get_item(
    id: UUID,
    user: AuthUser = Depends(get_current_user_dependency),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[ItemResponse]:

# 사용자 인증 + DB upsert (워크플로우/세션 생성)
@router.post("/start")
async def start_workflow(
    request: StartRequest,
    user: AuthUser = Depends(get_current_user_with_db),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[WorkflowResponse]:

# 에이전트 인증
@router.post("/posts")
async def create_post(
    request: CreatePostRequest,
    agent: AgentUser = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
```

## 에러 처리

```python
from presentation.middleware.error_middleware import NotFoundError
raise NotFoundError(f"Item {id} not found")
```

## 테스트 네이밍

```python
async def test_{행동}_{시나리오}_{예상_결과}():
    """테스트 목적 설명."""
```

## 자주 발생하는 문제

| 문제 | 해결 방법 |
|------|-----------|
| moto/aioboto3 비호환 | `AsyncMock` 사용 (moto의 `MockRawResponse` 미지원) |
| SQLAlchemy `metadata` 예약어 | `post_metadata` 속성 + `"metadata"` 컬럼명 사용 |
| Enum 불일치 (Python vs PostgreSQL) | `values_callable=lambda x: [e.value for e in x]` |
| 테스트에서 이벤트 루프 에러 | `dependency_overrides` + `fakeredis` |
