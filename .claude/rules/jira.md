# Jira 연동

## 프로젝트

- **프로젝트 키**: ARK
- **서브태스크 타입**: `"Sub-task"` (하이픈 포함! `"Subtask"` 아님)

## 활성 에픽 (2026 2Q)

작업 성격에 맞는 에픽을 선택할 것 (레포 기준이 아님).

### Focus

| 에픽 | 이름 |
|------|------|
| ARK-1314 | Early Access 온보딩 준비 |
| ARK-1315 | Data Pipeline |
| ARK-1316 | 실 운영 가동 |
| ARK-1317 | 차별화된 브랜딩 |

### Operations

| 에픽 | 이름 |
|------|------|
| ARK-1085 | 서비스 안정성 개선 |
| ARK-1318 | Agent 고도화 (회귀·토큰) |
| ARK-1319 | 비용 관리 |
| ARK-1320 | Agent 개인화 customer ops |
| ARK-1321 | 고객 VOC |

### Evolution

| 에픽 | 이름 |
|------|------|
| ARK-1322 | AI Framework 탈피 |
| ARK-1323 | Agent Scaling 아키텍처 |
| ARK-1324 | Agent 개인화 internalization |
| ARK-1325 | Quant SDK 확장 |
| ARK-1326 | Hypothesis drift 대응 (신규 모델 연구) |
| ARK-1327 | Trading 집행 레이어 (EMS/OMS) |
| ARK-1328 | 데이터 마켓플레이스 |
| ARK-1329 | Investment Universe 확대 |
| ARK-1330 | Investment Horizon 확대 |

### 에픽 선택 가이드

이슈 생성 시 작업 내용에 가장 적합한 에픽을 상위로 선택할 것. 예시:
- Agent 프롬프트/워크플로우 개선 → ARK-1318
- SDK 데이터 로더 추가 → ARK-1325
- 새 유니버스 지원 → ARK-1329
- 버그 수정/장애 대응 → ARK-1085
- UI/브랜딩 작업 → ARK-1317
- 데이터 파이프라인/연동 → ARK-1315 또는 ARK-1328

## 이슈 생성

```python
# Epic 하위 Task/Bug/Story — Epic은 작업 성격에 맞게 선택
jira_create_issue(
    project_key="ARK",
    summary="이슈 제목",
    issue_type="Task",
    assignee="94wogus@quantit.io",
    additional_fields={"parent": {"key": "ARK-1318"}}  # 적절한 Epic 선택
)

# Task 하위 Sub-task
jira_create_issue(
    project_key="ARK",
    summary="서브태스크 제목",
    issue_type="Sub-task",  # 하이픈 필수!
    additional_fields={"parent": "ARK-489"}
)
```
