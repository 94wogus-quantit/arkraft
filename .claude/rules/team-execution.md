# 팀 실행 규칙

**팀 생성은 사용자가 명시적으로 요청할 때만 수행한다.**

- 서브레포에서 직접 시작할 때 (예: `arkraft-api/`, `arkraft-web/`) → 항상 단독 작업.
- 루트 `arkraft/`에서 시작하더라도 → 사용자가 "팀으로", "teammate 써서", "팀 만들어서" 등 명시적으로 말할 때만 팀 생성.
- 자동으로 팀을 생성하거나 팀원에게 위임하지 말 것.

## 1. 팀 기반 작업 규칙

팀 생성이 명시적으로 요청된 경우에만 적용:
- 팀 리드는 직접 코딩하지 않음 — 팀원에게 위임.
- 각 팀원은 명확히 정의된 도메인 범위를 소유.

## 2. 도메인 소유권 원칙

**각 팀원은 명확히 정의된 도메인을 소유한다. 두 팀원이 같은 도메인 범위를 소유할 수 없다.**

- 팀원은 같은 도메인에 속하는 여러 레포를 소유할 수 있다.
- `harness`는 횡단 관심사 역할: 전 레포를 순회하여 프로토콜과 인터페이스를 통일하지만, 비즈니스 로직은 **절대 수정 금지**.
- `arkraft-deploy`의 경우 서비스별로 소유권 분리 — 각 팀원이 자기 서비스의 차트만 관리.

### arkraft-deploy 소유권 분리

| 범위 | 소유자 |
|------|--------|
| web 서비스 charts | `frontend` |
| api 서비스 charts | `backend` |
| agent 서비스 charts + Argo Workflow templates | `harness` |
| 인프라 공통/네트워크 charts | `infra` |

### arkraft-web 소유권 분리

| 범위 | 소유자 |
|------|--------|
| `app/`, `domains/` (페이지, 기능) | `frontend` |
| `shared/` (디자인 시스템, 공통 컴포넌트) | `designer` |

## 3. 팀원 ↔ 도메인 매핑

| 팀원 | 주요 레포 | 배포 범위 |
|------|-----------|-----------|
| `frontend` | `arkraft-web` | `arkraft-deploy` (web charts) |
| `backend` | `arkraft-api` | `arkraft-deploy` (api charts) |
| `harness` | 전 레포 순회 (프로토콜/인터페이스/배포만) | `arkraft-deploy` (agent charts, Argo templates) |
| `agent-dev` | `arkraft-agent-alpha`, `arkraft-agent-insight`, `arkraft-agent-portfolio`, `arkraft-agent-extract`, `arkraft-agent-data` | — |
| `infra` | `ai-infra`, `alpha-pool-infra` | - |
| `designer` | `arkraft-web` (`shared/` 중심) | — |

## 4. 위반 처리

- 도메인 범위 밖 비즈니스 로직 수정은 **즉시 중단**하고 해당 도메인 소유 팀원에게 위임.
- `harness`가 비즈니스 로직 수정을 시도하면 **즉시 중단**하고 `agent-dev` 또는 `frontend`/`backend`에게 위임.
- `designer`가 `app/`/`domains/` 코드 수정을 시도하면 **즉시 중단**하고 `frontend`에게 위임.
- 팀 리드가 직접 코딩을 시도하면 **즉시 중단**하고 팀원에게 위임.
