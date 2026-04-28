# Arkraft System Architecture

> AI 기반 퀀트 리서치 및 포트폴리오 관리 플랫폼 (by Quantit)
>
> 최종 업데이트: 2026-03-03

---

## 1. 시스템 개요

### 1.1 플랫폼 소개

Arkraft는 Quantit에서 개발한 AI 기반 퀀트 리서치 및 포트폴리오 관리 플랫폼이다. Claude Agent SDK를 활용하여 알파 전략 발굴, 리서치 인사이트 생성, 포트폴리오 구성, 금융 리포트 작성 등 퀀트 리서치의 핵심 워크플로우를 자동화한다.

핵심 특징:
- **AI Agent 기반 자동화**: Claude Agent SDK + MCP(Model Context Protocol)를 활용한 4종의 전문 에이전트
- **실시간 스트리밍**: SSE(Server-Sent Events)를 통한 에이전트 작업 진행률 실시간 전달
- **GitOps 기반 인프라**: Terraform + Atlantis, ArgoCD, Argo Workflows 기반의 완전 자동화된 배포
- **멀티 테넌트 인증**: AWS Cognito 기반 OAuth + JWT 인증 체계

### 1.2 레포지토리 맵

| Repository | Stack | Purpose | Port |
|-----------|-------|---------|------|
| `arkraft-api` | Python 3.12, FastAPI, SQLAlchemy 2.0 async | Backend API | 3002 |
| `arkraft-web` | Next.js 16, React 19, TypeScript, pnpm | Frontend | 3000 |
| `arkraft-agent-alpha` | Python 3.14, Claude Agent SDK | Alpha strategy agent (6-phase) | - |
| `arkraft-agent-insight` | Python 3.14, Claude Agent SDK | Research hypothesis agent | - |
| `arkraft-agent-portfolio` | Python 3.14, Claude Agent SDK, MCP | Portfolio construction agent | - |
| `arkraft-agent-report` | Python 3.14, Claude Agent SDK, FastAPI | Financial report agent | 8888 |
| `arkraft-agent-data` | Python 3.14, Claude Agent SDK | RDS Scan & File Sync agent | - |
| `arkraft-deploy` | Helm, ArgoCD, Argo Workflows | K8s deployment charts | - |
| `ai-infra` | Terraform + Atlantis | AWS infra (EKS, RDS, ElastiCache, Istio) | - |
| `alpha-pool-infra` | Terraform + Lambda | DynamoDB -> OpenSearch pipeline | - |

### 1.3 전체 시스템 개요 다이어그램

```mermaid
flowchart TB
    subgraph Users["사용자"]
        Browser["Browser"]
    end

    subgraph Frontend["arkraft-web (Next.js 16)"]
        direction TB
        AppRouter["App Router<br/>(protected)/ + (public)/"]
        BFF["BFF API Routes<br/>~70개 엔드포인트"]
        Domains["12 Domain Modules<br/>auth, builder, session,<br/>alpha-pool, autoresearch,<br/>data-query, data-report,<br/>portfolio-builder,<br/>portfolio-monitor,<br/>signal, trading, community"]
        SharedUI["Shared UI<br/>35 Components + Design System"]
    end

    subgraph Backend["arkraft-api (FastAPI)"]
        direction TB
        Presentation["Presentation Layer<br/>Routes + Middleware"]
        Application["Application Layer<br/>Schemas + Mappers"]
        Infrastructure["Infrastructure Layer<br/>DB, Redis, S3, Auth, SSE"]
        Domain["Domain Layer<br/>Entities + Enums"]
        AgentRunner["Agent Runner<br/>Docker / Argo"]
    end

    subgraph Agents["Agent Services"]
        direction LR
        Alpha["Alpha Agent<br/>6-Phase Discover<br/>3-Phase Optimize"]
        Insight["Insight Agent<br/>Init + Refill"]
        Portfolio["Portfolio Agent<br/>4-Step Pipeline"]
        Report["Report Agent<br/>FastAPI Server<br/>6-Phase Report"]
        DataAgent["Data Agent<br/>scan (5-Phase)<br/>sync (LLM-free)"]
    end

    subgraph MCPServers["MCP Servers"]
        AlphaPool["alpha-pool MCP<br/>(HTTP / Stdio)"]
        PortfolioMCP["portfolio-analysis MCP<br/>(Stdio)"]
        ReportMCPs["Report MCPs<br/>ticker, stock_fundamental,<br/>stock_ai_brief, market_data,<br/>datetime"]
    end

    subgraph AWS["AWS Infrastructure (ap-northeast-2)"]
        direction TB
        EKS["EKS 1.34<br/>Karpenter Autoscaler"]
        RDS["RDS PostgreSQL 17.2<br/>db.t4g.medium"]
        Redis["ElastiCache Redis 7.1<br/>cache.t4g.micro"]
        S3["S3<br/>arkraft.quantit.ai"]
        Cognito["Cognito<br/>User Pool"]
        OpenSearch["OpenSearch Serverless<br/>agent-memory (SEARCH)<br/>arkraft-alpha-pool (VECTORSEARCH)"]
    end

    subgraph DataPipeline["Alpha Pool Pipeline"]
        DynamoDB["DynamoDB<br/>arkraft-alpha-pool"]
        Lambda["Lambda Functions<br/>migrator + indexer"]
        Bedrock["Bedrock<br/>Claude Sonnet + Titan Embeddings"]
        FinterTables["Finter Tables<br/>(DynamoDB Source)"]
    end

    subgraph GitOps["GitOps & CI/CD"]
        ArgoCD["ArgoCD"]
        ArgoWF["Argo Workflows"]
        Atlantis["Atlantis<br/>(ECS Fargate)"]
        GHA["GitHub Actions"]
        ECR["ECR<br/>Container Registry"]
    end

    subgraph External["External Services"]
        Portrader["Portrader GraphQL<br/>crypto + equity"]
        FinterAPI["Finter API"]
        QuandaAgent["Quanda Agent<br/>data query"]
    end

    Browser -->|HTTPS| AppRouter
    AppRouter --> BFF
    AppRouter --> Domains
    Domains --> SharedUI
    BFF -->|Internal API| Presentation
    Browser -->|SSE| Presentation

    Presentation --> Application
    Application --> Infrastructure
    Infrastructure --> Domain
    Infrastructure --> AgentRunner

    AgentRunner -->|Docker Socket / Argo API| Agents
    Alpha --> AlphaPool
    Insight --> AlphaPool
    Portfolio --> AlphaPool
    Portfolio --> PortfolioMCP
    Report --> ReportMCPs

    Infrastructure --> RDS
    Infrastructure --> Redis
    Infrastructure --> S3
    Infrastructure --> Cognito
    Agents --> S3
    Agents --> Redis

    FinterTables --> Lambda
    Lambda --> Bedrock
    Bedrock --> DynamoDB
    DynamoDB --> Lambda
    Lambda --> Bedrock
    Lambda --> OpenSearch
    Lambda --> RDS

    GHA --> ECR
    ArgoCD --> EKS
    ArgoWF --> Agents
    Atlantis --> AWS

    Infrastructure --> Portrader
    Infrastructure --> FinterAPI
    Infrastructure --> QuandaAgent
```

---

## 2. 데이터 플로우

### 2.1 전체 데이터 플로우

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant W as arkraft-web<br/>(Next.js BFF)
    participant A as arkraft-api<br/>(FastAPI)
    participant R as Redis<br/>(Pub/Sub + Cache)
    participant AR as Agent Runner<br/>(Docker/Argo)
    participant AG as Agent<br/>(Claude SDK)
    participant MCP as MCP Server
    participant S3 as S3 Storage
    participant DB as PostgreSQL

    U->>W: 사용자 요청
    W->>A: API 호출 (JWT Bearer)
    A->>DB: 세션/작업 생성
    A->>AR: 에이전트 실행 요청

    alt Production (Argo)
        AR->>AR: Argo Workflow Template 제출
        AR-->>AG: Pod 생성 + 환경변수 주입
    else Local (Docker)
        AR->>AR: docker exec 컨테이너 실행
        AR-->>AG: 컨테이너 실행 + 환경변수 주입
    end

    AG->>MCP: 도구 호출 (alpha-pool 등)
    MCP-->>AG: 도구 결과
    AG->>S3: 중간 결과 저장 (artifacts)
    AG->>R: 실시간 이벤트 발행 (Pub/Sub)

    loop SSE Streaming
        U->>A: SSE 연결 (/events)
        A->>R: Subscribe to channel
        A->>S3: Polling (2초 간격)
        A-->>U: SSE 이벤트 스트리밍
    end

    AG->>S3: 최종 결과 저장
    AG->>A: 완료 콜백 (Internal API)
    A->>DB: 상태 업데이트
    A-->>U: SSE 완료 이벤트
```

### 2.2 Alpha Discovery 플로우

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web
    participant A as API
    participant AG as Alpha Agent
    participant AP as alpha-pool MCP
    participant S3 as S3

    U->>W: Topic 생성 + Discover 시작
    W->>A: POST /alpha-discovery/sessions/{id}/topics/{id}/discover
    A->>A: ArgoWorkflowRunner.submit(alpha-discover)
    A-->>AG: Pod 생성

    Note over AG: Phase 1: DESIGN
    AG->>AG: 연구 계획 수립, 탐색 축 결정
    AG->>S3: phase1_design.json

    Note over AG: Phase 2: PREP (병렬)
    par 데이터 로딩
        AG->>AG: Bash로 Python 코드 실행 (데이터 로딩)
    and 베이스라인 빌드
        AG->>AG: Bash로 Python 코드 실행 (베이스라인)
    end
    AG->>S3: phase2_prep.json

    Note over AG: Phase 3: EXPLORE (축별 병렬)
    par Axis 1 분석
        AG->>AG: 시그널 분석 A (Bash 실행)
    and Axis 2 분석
        AG->>AG: 시그널 분석 B (Bash 실행)
    and Axis N 분석
        AG->>AG: 시그널 분석 N (Bash 실행)
    end
    AG->>S3: phase3_explore.json

    Note over AG: Phase 4: REVIEW
    AG->>AG: PM 의사결정 (PROCEED/BASELINE_ONLY/REJECT)
    AG->>S3: phase4_review.json

    Note over AG: Phase 5: IMPLEMENT
    AG->>AG: 알파 구현 (Bash/Write 도구)
    AG->>S3: phase5_implement.json

    Note over AG: Phase 6: EVALUATE & REGISTER
    AG->>AG: 알파 평가 (Bash 실행)
    AG->>AP: 알파 등록 (alpha-pool MCP)
    AG->>S3: phase6_evaluate.json

    AG->>A: 완료 콜백
    A-->>U: SSE 완료
```

### 2.3 Portfolio Build 플로우

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web
    participant A as API
    participant AG as Portfolio Agent
    participant AP as alpha-pool MCP
    participant PA as portfolio-analysis MCP
    participant S3 as S3

    U->>W: 포트폴리오 빌드 요청
    W->>A: POST /portfolio/sessions/{id}/build
    A->>A: Agent Runner 실행
    A-->>AG: 에이전트 시작

    Note over AG: Step 1: Intent Analysis
    AG->>AG: Claude SDK - 투자 의도 분석
    AG->>S3: alpha_criteria.json

    Note over AG: Step 2: Alpha Search
    AG->>AP: alpha-pool 검색 (vector search)
    AP-->>AG: 매칭 알파 목록
    AG->>S3: alpha_pool.json

    Note over AG: Step 3: Portfolio Construction
    AG->>PA: 포트폴리오 분석 도구
    PA-->>AG: 최적화 결과
    AG->>S3: proposals.json

    Note over AG: Step 4: Simulation
    AG->>AG: Direct Python (finter BasePortfolio)
    AG->>S3: backtest_stats.json

    AG->>A: 완료 콜백
    A-->>U: SSE 완료
```

### 2.4 Data Report 플로우

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web
    participant A as API
    participant AG as Report Agent (FastAPI 8888)
    participant MCP as Report MCPs (5종)
    participant S3 as S3

    U->>W: 리포트 요청
    W->>A: POST /data-report/sessions
    A->>A: Agent Runner 실행
    A-->>AG: POST /execute (base64 payload)

    Note over AG: Phase 1: Planning (haiku)
    AG->>AG: Claude haiku - 리포트 구조 계획

    Note over AG: Phase 2: Data Collection (haiku)
    AG->>MCP: ticker, stock_fundamental, market_data
    MCP-->>AG: 금융 데이터

    Note over AG: Phase 3: Reasoning (sonnet)
    AG->>AG: Claude sonnet - 데이터 분석 및 추론

    Note over AG: Phase 4: JSON Report (sonnet)
    AG->>AG: Claude sonnet - 구조화된 JSON 리포트

    Note over AG: Phase 5: Visualization
    AG->>AG: 차트/시각화 생성

    Note over AG: Phase 6: Quality Gate (sonnet)
    AG->>AG: Claude sonnet - 품질 검증

    AG->>S3: 최종 리포트 저장
    AG->>A: 완료 콜백
    A-->>U: SSE 완료
```

---

## 3. arkraft-api 아키텍처

### 3.1 Clean Architecture 4계층

arkraft-api는 Clean Architecture 원칙을 따르는 4계층 구조로 설계되어 있다. 각 계층은 명확한 책임을 가지며, 의존성은 항상 안쪽(domain)을 향한다.

```mermaid
graph TB
    subgraph Presentation["Presentation Layer"]
        direction LR
        Routes["Routes<br/>(FastAPI Router)"]
        Middleware["Middleware<br/>(Auth, CORS, Error)"]
        DI["Dependency Injection<br/>(FastAPI Depends)"]
    end

    subgraph Application["Application Layer"]
        direction LR
        Schemas["Schemas<br/>(Pydantic DTOs)"]
        Mappers["Mappers<br/>(Entity ↔ DTO)"]
    end

    subgraph InfraLayer["Infrastructure Layer"]
        direction LR
        DBRepo["DB Repositories<br/>(SQLAlchemy 2.0 async)"]
        RedisClient["Redis Client<br/>(arq, Pub/Sub)"]
        S3Client["S3 Client<br/>(aioboto3, MinIO)"]
        AuthService["Auth Service<br/>(Cognito JWKS)"]
        SSEService["SSE Services<br/>(EventEmitter, Polling)"]
        AgentRunners["Agent Runners<br/>(Docker, Argo)"]
        ExternalAPI["External APIs<br/>(Portrader, Finter, Quanda)"]
    end

    subgraph DomainLayer["Domain Layer"]
        direction LR
        Entities["Entities<br/>(Pydantic Models)"]
        Enums["Enums<br/>(13 StrEnum)"]
        RepoInterfaces["Repository<br/>Interfaces"]
    end

    Presentation --> Application
    Application --> InfraLayer
    Application --> DomainLayer
    InfraLayer --> DomainLayer

    style DomainLayer fill:#e8f5e9
    style InfraLayer fill:#e3f2fd
    style Application fill:#fff3e0
    style Presentation fill:#fce4ec
```

**계층별 책임**:

| 계층 | 경로 | 책임 | 주요 구성 요소 |
|------|------|------|--------------|
| Domain | `domain/` | 비즈니스 엔티티, 열거형, 인터페이스 | Pydantic 모델, 13개 StrEnum, Repository 인터페이스 |
| Application | `application/` | DTO 변환, 비즈니스 로직 조율 | Pydantic Schemas (DTOs), Mappers |
| Infrastructure | `infrastructure/` | 외부 시스템 연동 | DB, Redis, S3, Auth, SSE, Agent Runner |
| Presentation | `presentation/` | HTTP 요청/응답 처리 | FastAPI Routes, Middleware, DI |

### 3.2 DB 스키마

```mermaid
erDiagram
    users {
        uuid id PK
        string email
        string name
        string cognito_sub
        timestamp created_at
    }

    workflows {
        uuid id PK
        uuid user_id FK
        string type
        string status
        jsonb config
        timestamp created_at
    }

    jobs {
        uuid id PK
        uuid workflow_id FK
        string status
        jsonb result
        timestamp started_at
        timestamp finished_at
    }

    alpha_discovery_sessions {
        uuid id PK
        uuid user_id FK
        string name
        string status
        jsonb config
        timestamp created_at
    }

    alpha_topic {
        uuid id PK
        uuid session_id FK
        string name
        string status
        jsonb data
        timestamp created_at
        timestamp updated_at
    }

    alpha_optimize_sessions {
        uuid id PK
        uuid topic_id FK
        string status
        jsonb config
    }

    alpha_discovery_session_reports {
        uuid id PK
        uuid session_id FK
        jsonb report_data
    }

    portfolio_build_sessions {
        uuid id PK
        uuid user_id FK
        string status
        jsonb config
    }

    portfolio_submissions {
        uuid id PK
        uuid session_id FK
        jsonb portfolio_data
    }

    data_reports {
        uuid id PK
        uuid user_id FK
        string status
        jsonb config
    }

    data_query_sessions {
        uuid id PK
        uuid user_id FK
        string status
    }

    signal_study {
        uuid id PK
        uuid user_id FK
        jsonb signal_data
    }

    agent_credentials {
        uuid id PK
        string agent_type
        string api_key_hash
    }

    community_posts {
        uuid id PK
        uuid user_id FK
        string title
        text content
    }

    community_comments {
        uuid id PK
        uuid post_id FK
        uuid user_id FK
        text content
    }

    users ||--o{ workflows : creates
    users ||--o{ alpha_discovery_sessions : creates
    users ||--o{ portfolio_build_sessions : creates
    users ||--o{ data_reports : creates
    users ||--o{ data_query_sessions : creates
    users ||--o{ signal_study : creates
    users ||--o{ community_posts : writes

    workflows ||--o{ jobs : contains
    alpha_discovery_sessions ||--o{ alpha_topic : contains
    alpha_discovery_sessions ||--o{ alpha_discovery_session_reports : has
    alpha_topic ||--o{ alpha_optimize_sessions : has
    portfolio_build_sessions ||--o{ portfolio_submissions : has
    community_posts ||--o{ community_comments : has
```

### 3.3 인증 레이어

| Layer | Mechanism | 적용 범위 | 헤더/방식 |
|-------|-----------|----------|----------|
| **Public** | 없음 | Health check, Community 읽기 | - |
| **Internal** | VPC 네트워크 격리만 의존 (헤더 검증 없음) | `/internal/*` 콜백 엔드포인트 | ~~`X-Internal-Secret`~~ (미구현) |
| **Agent** | SHA-256 해시 검증 | Community 쓰기 (에이전트) | `X-Agent-API-Key` |
| **Protected** | Cognito JWT RS256 | 모든 사용자 API | `Authorization: Bearer {token}` |

### 3.4 SSE 스트리밍 패턴

arkraft-api는 3가지 SSE 스트리밍 패턴을 지원한다:

| 패턴 | 사용처 | 데이터 소스 | 특징 |
|------|--------|-----------|------|
| **Builder SSE** | Portfolio Build, Alpha Discover | EventEmitter(asyncio.Queue) + S3 polling | 실시간 이벤트 + 결과 폴링 |
| **Session SSE** | Insight, Alpha Optimize | S3 polling only (2초 간격) | 단순 폴링 기반 |
| **Data Query SSE** | Data Query | S3 history load + Redis Pub/Sub | 과거 로그 + 실시간 구독 |

### 3.5 Agent Runner 듀얼 백엔드

```mermaid
flowchart LR
    API["arkraft-api"]

    subgraph RunnerSelect["Agent Runner 선택"]
        EnvVar{"AGENT_RUNNER<br/>환경변수"}
    end

    subgraph DockerPath["Local 환경"]
        DockerRunner["DockerRunRunner"]
        DockerSocket["Docker Socket<br/>/var/run/docker.sock"]
        DockerContainer["Agent Container<br/>arkraft-{type}:latest"]
    end

    subgraph ArgoPath["Production 환경"]
        ArgoRunner["ArgoWorkflowRunner"]
        ArgoAPI["Argo Workflows API<br/>argo.arkraft.svc"]
        ArgoPod["Agent Pod<br/>(K8s arkraft-sandbox)"]
    end

    API --> EnvVar
    EnvVar -->|"docker"| DockerRunner
    EnvVar -->|"argo"| ArgoRunner

    DockerRunner --> DockerSocket
    DockerSocket --> DockerContainer

    ArgoRunner --> ArgoAPI
    ArgoAPI --> ArgoPod

    DockerContainer -->|"공유 네트워크: arkraft"| DockerContainer
    ArgoPod -->|"K8s namespace: arkraft-sandbox"| ArgoPod
```

**Argo Workflow Templates**:

| Template | Agent | 용도 |
|----------|-------|------|
| `alpha-discover` | Alpha | 6-Phase Alpha 발굴 |
| `alpha-optimize` | Alpha | 3-Phase Alpha 최적화 |
| `insight-init` | Insight | N개 연구 가설 생성 |
| `insight-refill` | Insight | 1개 인사이트 보충 |
| `portfolio-intent` | Portfolio | 투자 의도 분석 |
| `portfolio-search` | Portfolio | 알파 검색 |
| `portfolio-simulation` | Portfolio | 백테스트 시뮬레이션 |
| `data-scan` | Data | RDS 스캔 (5-Phase: scan→propose→trial→extract→pipeline) |
| `data-sync` | Data | 증분 동기화 (LLM-free, CronWorkflow 실행) |

### 3.6 외부 시스템 연동

| 외부 시스템 | 프로토콜 | 용도 |
|------------|---------|------|
| Argo Workflows | REST API | 에이전트 워크플로우 실행 |
| S3 (aioboto3) | AWS SDK | 결과 저장, MinIO 로컬 지원 |
| AWS Cognito | JWKS RS256 | 사용자 인증, UserInfo Redis 캐싱 |
| Docker Engine | API v1.46 | 로컬 에이전트 컨테이너 관리 |
| Portrader GraphQL | GraphQL | 암호화폐 + 주식 데이터 |
| Finter API | REST | 금융 데이터 |
| Quanda Agent | REST | 데이터 쿼리 에이전트 |

### 3.7 API 응답 포맷

```json
// 단건 성공
{"success": true, "data": {...}}

// 목록 성공 (페이지네이션)
{"success": true, "data": [...], "meta": {"total": 100, "limit": 20, "offset": 0}}

// 실패
{"success": false, "error": "message"}
```

---

## 4. arkraft-web 아키텍처

### 4.1 레이어 구조

```mermaid
graph TB
    subgraph AppLayer["app/ (Next.js App Router)"]
        direction TB
        Protected["(protected)/<br/>인증 필요 페이지"]
        Public["(public)/<br/>로그인 페이지"]
        APIRoutes["api/<br/>BFF Routes ~70개"]
    end

    subgraph DomainsLayer["domains/ (12 Domain Modules)"]
        direction TB
        Auth["auth"]
        Builder["builder"]
        Session["session"]
        AlphaPool["alpha-pool"]
        AutoResearch["autoresearch"]
        DataQuery["data-query"]
        DataReport["data-report"]
        PortfolioBuilder["portfolio-builder"]
        PortfolioMonitor["portfolio-monitor"]
        Signal["signal"]
        Trading["trading"]
        Community["community"]
    end

    subgraph InfraLayer["infra/"]
        direction TB
        APIClient["API Client<br/>apiFetch + clientApiFetch"]
        CognitoAuth["Cognito Auth<br/>OAuth + Token Mgmt"]
        EnvConfig["Environment Config<br/>env.ts"]
    end

    subgraph SharedLayer["shared/"]
        direction TB
        UIComponents["35 UI Components"]
        DesignSystem["Design System<br/>CVA + Tailwind"]
        Hooks["Shared Hooks"]
        ZodSchemas["Zod Schemas"]
    end

    AppLayer -->|"import"| DomainsLayer
    AppLayer -->|"import"| SharedLayer
    AppLayer -.->|"PROHIBITED"| InfraLayer

    DomainsLayer -->|"import"| InfraLayer
    DomainsLayer -->|"import"| SharedLayer

    InfraLayer -->|"import"| SharedLayer

    style AppLayer fill:#fce4ec
    style DomainsLayer fill:#fff3e0
    style InfraLayer fill:#e3f2fd
    style SharedLayer fill:#e8f5e9
```

**Import 규칙 (ESLint 강제)**:

| From | Can Import | PROHIBITED |
|------|-----------|------------|
| `app/` | `domains/`, `shared/` | `infra/` 직접 import 금지 |
| `domains/` | `infra/`, `shared/` | - |
| `infra/` | `shared/` only | `app/`, `domains/` |
| `shared/` | `shared/` only | `app/`, `domains/`, `infra/` |

### 4.2 페이지 라우팅 트리

```mermaid
graph TB
    Root["/"]

    subgraph PublicPages["(public) 비인증"]
        Login["/ - Login<br/>Google OAuth + Magic Link"]
    end

    subgraph ProtectedPages["(protected) 인증 필요"]
        Home["/home"]

        subgraph DataSection["/data"]
            DataMain["/data"]
            DataReport["/data/report"]
            DataSignal["/data/signal"]
            DataQuery["/data/query"]
        end

        subgraph AlphaSection["/alpha"]
            AlphaMain["/alpha"]
            AlphaDiscover["/alpha/discover"]
            AlphaOptimize["/alpha/optimize"]
            AlphaLibrary["/alpha/library"]
        end

        subgraph PortfolioSection["/portfolio"]
            PortfolioMain["/portfolio"]
            PortfolioBuild["/portfolio/build"]
            PortfolioMonitor["/portfolio/monitor"]
        end

        subgraph TradingSection["/trading"]
            TradingMain["/trading"]
            TradingLive["/trading/live"]
            TradingAllocation["/trading/allocation"]
        end
    end

    Root --> Login
    Root --> Home
    Home --> DataSection
    Home --> AlphaSection
    Home --> PortfolioSection
    Home --> TradingSection

    DataMain --> DataReport
    DataMain --> DataSignal
    DataMain --> DataQuery

    AlphaMain --> AlphaDiscover
    AlphaMain --> AlphaOptimize
    AlphaMain --> AlphaLibrary

    PortfolioMain --> PortfolioBuild
    PortfolioMain --> PortfolioMonitor

    TradingMain --> TradingLive
    TradingMain --> TradingAllocation
```

### 4.3 인증 플로우

```mermaid
sequenceDiagram
    participant U as User
    participant W as arkraft-web
    participant MW as Middleware<br/>(proxy.ts)
    participant C as AWS Cognito
    participant A as arkraft-api

    Note over U,C: 초기 인증 (Google OAuth / Magic Link)
    U->>W: 로그인 클릭
    W->>C: OAuth Redirect
    C->>C: Google OAuth / Magic Link 인증
    C-->>W: Authorization Code
    W->>C: Token Exchange
    C-->>W: id_token + access_token + refresh_token

    Note over W: 4개 쿠키 저장
    W->>W: Set-Cookie:<br/>id_token, access_token,<br/>refresh_token, token_expires

    Note over U,A: API 호출 플로우
    U->>W: 페이지 요청
    MW->>MW: 토큰 만료 확인

    alt 만료 5분 전
        MW->>C: Refresh Token으로 갱신
        C-->>MW: 새로운 토큰
        MW->>MW: 쿠키 업데이트
    end

    W->>A: API 호출 (Bearer Token)
    A->>A: JWT RS256 검증 (JWKS)
    A-->>W: 응답

    Note over U,W: 클라이언트 사이드 갱신
    loop AuthRefreshProvider (4분 간격)
        W->>C: 토큰 유효성 확인
        C-->>W: 갱신된 토큰 (필요시)
    end

    Note over W: RSC 인증 체크
    W->>W: authGuard()<br/>서버 컴포넌트에서 인증 확인
```

### 4.4 API 클라이언트 이중 구조

```mermaid
flowchart LR
    subgraph ServerSide["서버사이드 (RSC / BFF)"]
        RSC["React Server Component"]
        BFFRoute["BFF API Route"]
        ApiFetch["apiFetch()"]
    end

    subgraph ClientSide["클라이언트사이드"]
        ClientComp["Client Component"]
        ClientApiFetch["clientApiFetch()"]
    end

    subgraph APIServer["arkraft-api"]
        FastAPI["FastAPI<br/>port 3002"]
    end

    RSC --> ApiFetch
    BFFRoute --> ApiFetch
    ApiFetch -->|"INTERNAL_API_URL<br/>(K8s 내부 direct)"| FastAPI

    ClientComp --> ClientApiFetch
    ClientApiFetch -->|"NEXT_PUBLIC_API_URL<br/>(BFF 또는 direct)"| FastAPI
```

**서버사이드 `apiFetch()`**: K8s 내부 Service Discovery를 통해 직접 호출 (네트워크 홉 최소화)
**클라이언트사이드 `clientApiFetch()`**: 공개 URL을 통해 BFF 또는 직접 API 호출

### 4.5 기술 스택 상세

| 카테고리 | 기술 | 비고 |
|---------|------|------|
| Framework | Next.js 16.1 + React 19 | App Router |
| Compiler | React Compiler | `useMemo`/`useCallback` 사용 금지 |
| Styling | Tailwind CSS 4 + CVA | 컴포넌트 variant 관리 |
| UI Library | Radix UI | Headless 컴포넌트 |
| Charts | ECharts, Recharts, Lightweight Charts | 금융 차트 |
| Animation | framer-motion | 페이지 전환, 컴포넌트 애니메이션 |
| Validation | Zod | 런타임 타입 검증 |
| Toast | sonner | 알림 메시지 |
| Package Manager | pnpm | 의존성 관리 |

---

## 5. Agent 시스템 아키텍처

### 5.1 Agent 공통 구조

모든 에이전트는 동일한 기본 구조를 따른다:

```
src/agent.py         → Claude Agent SDK 옵션 설정
src/main.py          → CLI/서버 진입점
workspace/CLAUDE.md  → Agent 시스템 프롬프트
workspace/.mcp.json  → MCP 서버 설정
```

**공통 패턴**:
- **ClaudeAgentOptions**: `bypassPermissions` 활성화, OAuth token rotation (CLAUDE_OAUTH_TOKEN_1,2,3)
- **Hooks**: PostToolUse (S3 동기화), UserPromptSubmit (세션 캡처)
- **Docker**: `arkraft` 외부 네트워크 공유로 MCP 서버 접근
- **이미지 네이밍**: `arkraft-{agent}:latest`

### 5.2 Alpha Agent 6-Phase Discover 워크플로우

```mermaid
flowchart TB
    Start([Alpha Discover 시작])

    subgraph Phase1["Phase 1: DESIGN"]
        D1[연구 계획 수립]
        D2[탐색 축 결정]
        D3[가설 정의]
        D1 --> D2 --> D3
    end

    subgraph Phase2["Phase 2: PREP (병렬 실행)"]
        direction LR
        P1[데이터 로딩<br/>Bash/Python 직접 실행]
        P2[베이스라인 빌드<br/>Bash/Python 직접 실행]
    end

    subgraph Phase3["Phase 3: EXPLORE (축별 병렬)"]
        direction LR
        E1[Axis 1<br/>시그널 분석]
        E2[Axis 2<br/>시그널 분석]
        E3[Axis N<br/>시그널 분석]
    end

    subgraph Phase4["Phase 4: REVIEW"]
        R1{PM 의사결정}
        PROCEED[PROCEED<br/>알파 구현 진행]
        BASELINE[BASELINE_ONLY<br/>베이스라인만 등록]
        REJECT[REJECT<br/>작업 중단]
    end

    subgraph Phase5["Phase 5: IMPLEMENT"]
        I1[알파 팩터 구현<br/>Bash/Write 도구]
        I2[백테스트 실행]
        I3[성과 지표 계산]
        I1 --> I2 --> I3
    end

    subgraph Phase6["Phase 6: EVALUATE & REGISTER"]
        V1[알파 평가<br/>Bash 실행 + scripts/pool_record.py]
        V2[alpha-pool MCP<br/>알파 등록]
        V3[최종 리포트 생성]
        V1 --> V2 --> V3
    end

    Start --> Phase1
    Phase1 --> Phase2
    P1 & P2 --> Phase3
    E1 & E2 & E3 --> Phase4
    R1 --> PROCEED
    R1 --> BASELINE
    R1 --> REJECT
    PROCEED --> Phase5
    Phase5 --> Phase6

    subgraph S3Storage["S3 저장"]
        S3Path["alpha-discovery-sessions/<br/>{session_id}/{topic_id}/"]
        ChatLogs["chat_logs.jsonl"]
        Artifacts["artifacts/"]
        TopicJSON["topic.json"]
    end

    Phase6 --> S3Storage
    BASELINE --> S3Storage
    REJECT --> End([종료])
    S3Storage --> End2([완료])

    subgraph SessionRestore["세션 복원"]
        ClaudeID[".claude-id"]
        ChatLog2["chat_logs.jsonl"]
    end

    style Phase1 fill:#e3f2fd
    style Phase2 fill:#e8f5e9
    style Phase3 fill:#fff3e0
    style Phase4 fill:#fce4ec
    style Phase5 fill:#f3e5f5
    style Phase6 fill:#e0f2f1
```

**Alpha Optimize (3-Phase)**:
1. 기존 알파 로드 + 분석
2. 최적화 실행 (파라미터 튜닝)
3. 결과 평가 + 재등록

### 5.3 Insight Agent 워크플로우

| 모드 | 동작 | 출력 |
|------|------|------|
| **Init** | N개 research hypothesis 생성 | `artifacts/insight.json` |
| **Refill** | 1개 insight 보충 생성 | `artifacts/insight.json` (업데이트) |

**특징**:
- MCP: alpha-pool (HTTP 방식)
- AssistantMessage 블록을 insight log 형태로 변환 (text/tool_use/thinking 구분)
- S3 경로: `{session_path}/artifacts/insight.json`

### 5.4 Portfolio Agent 4-Step 파이프라인

```mermaid
flowchart TB
    Start([Portfolio Build 시작])

    subgraph Step1["Step 1: Intent Analysis"]
        IA1[Claude SDK]
        IA2[투자 의도 파싱]
        IA3[알파 기준 도출]
        IA1 --> IA2 --> IA3
        IA_OUT["alpha_criteria.json"]
        IA3 --> IA_OUT
    end

    subgraph Step2["Step 2: Alpha Search"]
        AS1[Claude SDK]
        AS2[alpha-pool MCP 호출<br/>Vector Search]
        AS3[매칭 알파 필터링]
        AS1 --> AS2 --> AS3
        AS_OUT["alpha_pool.json"]
        AS3 --> AS_OUT
    end

    subgraph Step3["Step 3: Portfolio Construction"]
        PC1[Claude SDK]
        PC2[portfolio-analysis MCP 호출]
        PC3[포트폴리오 최적화]
        PC4[제안서 생성]
        PC1 --> PC2 --> PC3 --> PC4
        PC_OUT["proposals.json"]
        PC4 --> PC_OUT
    end

    subgraph Step4["Step 4: Simulation"]
        SIM1[Direct Python<br/>finter BasePortfolio]
        SIM2[백테스트 실행]
        SIM3[성과 통계 계산]
        SIM1 --> SIM2 --> SIM3
        SIM_OUT["backtest_stats.json"]
        SIM3 --> SIM_OUT
    end

    Start --> Step1
    Step1 --> Step2
    Step2 --> Step3
    Step3 --> Step4
    Step4 --> End([완료])

    subgraph S3Path["S3: portfolio-builds/{session_id}/"]
        IA_S3["alpha_criteria.json"]
        AS_S3["alpha_pool.json"]
        PC_S3["proposals.json"]
        SIM_S3["backtest_stats.json"]
    end

    style Step1 fill:#e3f2fd
    style Step2 fill:#e8f5e9
    style Step3 fill:#fff3e0
    style Step4 fill:#fce4ec
```

**MCP 방식**: Stdio (로컬 프로세스) - alpha_pool, portfolio_analysis

### 5.5 Report Agent FastAPI 서버 방식

Report Agent는 다른 에이전트와 달리 FastAPI 서버(port 8888) 방식으로 동작한다:

| Phase | 모델 | 역할 |
|-------|------|------|
| 1. Planning | Claude haiku | 리포트 구조 계획 |
| 2. Data Collection | Claude haiku | 금융 데이터 수집 (5개 MCP) |
| 3. Reasoning | Claude sonnet | 데이터 분석 및 추론 |
| 4. JSON Report | Claude sonnet | 구조화된 JSON 리포트 생성 |
| 5. Visualization | - | 차트/시각화 생성 |
| 6. Quality Gate | Claude sonnet | 최종 품질 검증 |

**진입점**: `POST /execute` (base64 payload 수신)
**S3 경로**: `arkraft/users/{email}/requests/{workflow_id}/sessions/{job_id}/`

### 5.6 Agent 비교표

| 항목 | Alpha | Insight | Portfolio | Report | Data |
|------|-------|---------|-----------|--------|------|
| **실행 방식** | Claude Agent SDK | Claude Agent SDK | Claude Agent SDK | FastAPI + Claude SDK | Claude Agent SDK (scan) / Pure Python (sync) |
| **MCP 프로토콜** | HTTP | HTTP | Stdio | HTTP | 없음 |
| **MCP 서버** | alpha-pool | alpha-pool | alpha-pool, portfolio-analysis | ticker, stock_fundamental, stock_ai_brief, market_data, datetime | 없음 |
| **S3 경로** | `alpha-discovery-sessions/{sid}/{tid}/` | `{session}/artifacts/` | `portfolio-builds/{sid}/` | `arkraft/users/{email}/requests/{wid}/sessions/{jid}/` | `teams/{tid}/data_source/{sid}/workspace/` |
| **Hooks** | PostToolUse (S3), UserPromptSubmit | PostToolUse (S3) | PostToolUse (S3) | PostToolUse (S3) | PostToolUse (S3) |
| **세션 복원** | 지원 (.claude-id + chat_logs) | 미지원 | 미지원 | 미지원 | 미지원 |
| **모델 사용** | sonnet (전체) | sonnet (전체) | sonnet (전체) | haiku + sonnet (단계별) | sonnet (scan), 없음 (sync) |
| **파이프라인** | 6-Phase Discover / 3-Phase Optimize | Init / Refill | 4-Step Sequential | 6-Phase Sequential | scan (5-Phase) / sync (LLM-free) |

### 5.7 Claude Agent SDK 실행 구조

```mermaid
sequenceDiagram
    participant API as arkraft-api
    participant Runner as Agent Runner<br/>(Docker/Argo)
    participant Container as Agent Container
    participant SDK as Claude Agent SDK
    participant Claude as Claude API<br/>(Anthropic)
    participant MCP as MCP Server(s)
    participant S3 as S3 Storage
    participant Redis as Redis Pub/Sub

    API->>Runner: 에이전트 실행 요청<br/>(env vars + config)
    Runner->>Container: 컨테이너 생성/Pod 생성

    Container->>Container: main.py 실행
    Container->>SDK: ClaudeAgentOptions 초기화<br/>(bypassPermissions, hooks, MCP config)
    SDK->>Claude: 시스템 프롬프트 + workspace/CLAUDE.md

    loop Agent Turn Loop
        Claude-->>SDK: Assistant Message<br/>(text / tool_use / thinking)

        alt Tool Use
            SDK->>MCP: MCP 도구 호출
            MCP-->>SDK: 도구 결과
        end

        Note over SDK: PostToolUse Hook 실행
        SDK->>S3: 중간 결과 동기화
        SDK->>Redis: 이벤트 발행

        alt OAuth Token Rotation
            SDK->>SDK: CLAUDE_OAUTH_TOKEN_1,2,3<br/>순환 사용
        end

        SDK->>Claude: 도구 결과 + 다음 프롬프트
    end

    SDK->>S3: 최종 결과 저장
    Container->>API: 완료 콜백<br/>(Internal API)
```

---

## 6. 인프라 아키텍처

### 6.1 AWS 인프라 토폴로지

```mermaid
flowchart TB
    subgraph Internet["Internet"]
        Users["Users"]
        VPN["VPN Users"]
    end

    subgraph AWS["AWS ap-northeast-2 (Seoul)"]
        subgraph VPC["VPC 172.47.0.0/16"]
            subgraph PublicSubnet["Public Subnets"]
                EXTGW["Istio External Gateway<br/>(Internet-facing)"]
                INTGW["Istio Internal Gateway<br/>(VPN only)"]
                NAT["NAT Gateway"]
            end

            subgraph PrivateSubnet["Private Subnets"]
                subgraph EKSCluster["EKS 1.34"]
                    subgraph OpsNodeGroup["Ops Node Group<br/>t4g.xlarge x2-4 (tainted)"]
                        Istio["Istio Control Plane"]
                        ArgoCD2["ArgoCD"]
                        ArgoWF2["Argo Workflows"]
                        Monitoring["Monitoring Stack"]
                    end

                    subgraph KarpenterNodes["Karpenter Managed Nodes"]
                        DefaultARM["default-arm64"]
                        DefaultX86["default-x86"]
                        GVisorARM["gvisor-arm64"]
                        GVisorX86["gvisor-x86"]
                        GPU["gpu-x86"]
                    end

                    subgraph Namespaces["K8s Namespaces"]
                        ArkraftNS["arkraft<br/>(web, api, agent-manager,<br/>alpha-pool-mcp)"]
                        SandboxNS["arkraft-sandbox<br/>(agent pods)"]
                        ArgoNS["argo<br/>(workflow pods)"]
                    end
                end

                RDS2["RDS PostgreSQL 17.2<br/>db.t4g.medium"]
                Redis2["ElastiCache Redis 7.1<br/>cache.t4g.micro"]
            end
        end

        subgraph Serverless["Serverless Services"]
            S3_2["S3<br/>arkraft.quantit.ai"]
            Cognito2["Cognito<br/>User Pool"]
            OpenSearch2["OpenSearch Serverless<br/>agent-memory (SEARCH)<br/>arkraft-alpha-pool (VECTORSEARCH)"]
            DynamoDB2["DynamoDB<br/>arkraft-alpha-pool"]
            Bedrock2["Bedrock<br/>Claude Sonnet + Titan"]
            ECR2["ECR<br/>Container Registry"]
        end

        subgraph ECSFargate["ECS Fargate (별도)"]
            Atlantis2["Atlantis<br/>(Terraform GitOps)"]
        end
    end

    Users -->|HTTPS| EXTGW
    VPN -->|VPN| INTGW
    EXTGW --> ArkraftNS
    INTGW --> ArkraftNS

    ArkraftNS --> RDS2
    ArkraftNS --> Redis2
    ArkraftNS --> S3_2
    SandboxNS --> S3_2
    SandboxNS --> Redis2
    ArkraftNS --> Cognito2

    KarpenterNodes --> Namespaces

    style EKSCluster fill:#e3f2fd
    style Serverless fill:#e8f5e9
    style ECSFargate fill:#fff3e0
```

### 6.2 EKS 클러스터 구성

```mermaid
flowchart TB
    subgraph EKS["EKS 1.34 Cluster"]
        subgraph NodeGroups["Node 관리"]
            OpsNG["Ops Node Group<br/>t4g.xlarge<br/>min:2 max:4<br/>tainted: ops=true:NoSchedule"]

            subgraph Karpenter["Karpenter Auto-scaling"]
                EC2NC1["EC2NodeClass: default-arm64<br/>AL2023, arm64"]
                EC2NC2["EC2NodeClass: default-x86<br/>AL2023, amd64"]
                EC2NC3["EC2NodeClass: gvisor-arm64<br/>gVisor runtime, arm64"]
                EC2NC4["EC2NodeClass: gvisor-x86<br/>gVisor runtime, amd64"]
                EC2NC5["EC2NodeClass: gpu-x86<br/>GPU instances, amd64"]
            end
        end

        subgraph SystemComponents["시스템 컴포넌트 (Ops Nodes)"]
            IstioCP["Istio Control Plane"]
            ArgoCDSys["ArgoCD"]
            ArgoWFSys["Argo Workflows Controller"]
            KarpenterCtrl["Karpenter Controller"]
            CoreDNS["CoreDNS"]
        end

        subgraph AppWorkloads["애플리케이션 워크로드"]
            subgraph NSArkraft["namespace: arkraft"]
                WebDeploy["arkraft-web<br/>port 3000"]
                APIDeploy["arkraft-api<br/>port 3002"]
                AgentMgr["agent-manager<br/>(arq worker)"]
                AlphaPoolMCP["alpha-pool-mcp"]
            end

            subgraph NSSandbox["namespace: arkraft-sandbox"]
                AgentPods["Agent Pods<br/>(dynamic, per-job)"]
            end

            subgraph NSArgo["namespace: argo"]
                WFPods["Workflow Pods<br/>(Argo Workflows)"]
            end
        end

        subgraph IRSA["IRSA (7 Roles)"]
            R1["argo-workflows-role"]
            R2["arkraft-agent-role"]
            R3["arkraft-api-server-role"]
            R4["alpha-pool-mcp-role"]
            R5["argocd-role"]
            R6["karpenter-role"]
            R7["external-dns-role"]
        end
    end

    OpsNG --> SystemComponents
    Karpenter --> AppWorkloads
    IRSA -.->|"ServiceAccount 바인딩"| AppWorkloads
```

### 6.3 Alpha Pool 데이터 파이프라인

```mermaid
flowchart LR
    subgraph Source["데이터 소스"]
        FinterDDB["Finter Tables<br/>(DynamoDB)"]
    end

    subgraph Migration["마이그레이션 (EventBridge)"]
        EB["EventBridge<br/>08:00 / 09:00 KST"]
        MigratorLambda["Lambda: migrator"]
    end

    subgraph LLMEnrichment["LLM 보강"]
        BedrockClaude["Bedrock<br/>Claude Sonnet<br/>(LLM enrichment)"]
    end

    subgraph Storage["중간 저장"]
        AlphaPoolDDB["DynamoDB<br/>arkraft-alpha-pool"]
        DDBStreams["DynamoDB Streams"]
    end

    subgraph Indexing["인덱싱 (VPC Lambda)"]
        IndexerLambda["Lambda: indexer<br/>(VPC 내부)"]
        BedrockTitan["Bedrock<br/>Titan Embeddings<br/>(1024-dim)"]
    end

    subgraph Destinations["저장소"]
        OpenSearchVS["OpenSearch Serverless<br/>arkraft-alpha-pool<br/>(VECTORSEARCH)"]
        RDSDB["RDS PostgreSQL<br/>(structured data)"]
    end

    FinterDDB --> EB
    EB --> MigratorLambda
    MigratorLambda --> BedrockClaude
    BedrockClaude --> AlphaPoolDDB
    AlphaPoolDDB --> DDBStreams
    DDBStreams --> IndexerLambda
    IndexerLambda --> BedrockTitan
    BedrockTitan --> OpenSearchVS
    IndexerLambda --> RDSDB

    style Source fill:#fff3e0
    style LLMEnrichment fill:#f3e5f5
    style Indexing fill:#e3f2fd
    style Destinations fill:#e8f5e9
```

**파이프라인 요약**:
1. Finter DynamoDB 테이블에서 알파 데이터 원본 수집
2. EventBridge가 매일 08:00/09:00 KST에 Lambda migrator 트리거
3. Bedrock Claude Sonnet으로 LLM 기반 메타데이터 보강 (설명, 태그, 분류)
4. arkraft-alpha-pool DynamoDB에 저장
5. DynamoDB Streams가 변경 감지 -> Lambda indexer 트리거
6. Bedrock Titan으로 1024차원 임베딩 벡터 생성
7. OpenSearch Serverless에 벡터 인덱싱 (vector search 지원)
8. RDS PostgreSQL에 구조화된 데이터 저장 (관계형 쿼리 지원)

---

## 7. 배포 및 CI/CD

### 7.1 Argo Workflow Agent 실행 플로우

```mermaid
sequenceDiagram
    participant User as User
    participant API as arkraft-api
    participant ArqWorker as agent-manager<br/>(arq worker)
    participant ArgoAPI as Argo Workflows API
    participant ArgoCtrl as Argo Controller
    participant AgentPod as Agent Pod<br/>(arkraft-sandbox)
    participant S3 as S3
    participant Redis as Redis

    User->>API: POST /alpha-discovery/discover
    API->>API: 세션/작업 DB 생성
    API->>ArqWorker: arq 큐에 작업 추가
    ArqWorker->>ArgoAPI: WorkflowTemplate 제출<br/>(alpha-discover)

    ArgoAPI->>ArgoCtrl: Workflow 스케줄링
    ArgoCtrl->>AgentPod: Pod 생성<br/>(namespace: arkraft-sandbox)

    Note over AgentPod: Agent 초기화
    AgentPod->>AgentPod: ENV 로딩<br/>(API Key, S3 Path, Session ID)
    AgentPod->>AgentPod: Claude Agent SDK 시작

    loop 작업 실행
        AgentPod->>S3: 중간 결과 저장
        AgentPod->>Redis: Pub/Sub 이벤트 발행
    end

    AgentPod->>S3: 최종 결과 저장
    AgentPod->>API: POST /internal/callback<br/>(인증 없음, VPC 격리)
    API->>API: DB 상태 업데이트
    API-->>User: SSE 완료 이벤트

    AgentPod->>AgentPod: Pod 종료
    ArgoCtrl->>ArgoCtrl: Workflow 상태 완료 기록
```

### 7.2 CI/CD 파이프라인

```mermaid
flowchart TB
    subgraph Developer["개발자"]
        Code["코드 변경"]
        PR["Pull Request"]
    end

    subgraph GitHub["GitHub"]
        GHRepo["Repository"]
        GHA["GitHub Actions"]
    end

    subgraph Build["빌드 단계"]
        Lint["Lint + Type Check"]
        Test["Unit Tests"]
        DockerBuild["Multi-arch Docker Build<br/>(arm64 + amd64)"]
    end

    subgraph Registry["컨테이너 레지스트리"]
        ECR3["ECR"]
    end

    subgraph InfraDeploy["인프라 변경"]
        AtlantisGH["Atlantis<br/>(Terraform)"]
        TFPlan["terraform plan<br/>(PR 코멘트)"]
        TFApply["terraform apply<br/>(merge 후)"]
    end

    subgraph K8sDeploy["K8s 배포"]
        ArgoCD3["ArgoCD"]
        HelmUpgrade["Helm Upgrade"]
        K8sApply["K8s Apply"]
    end

    subgraph Verify["검증"]
        HealthCheck["Health Check"]
        SmokeTest["Smoke Test"]
    end

    Code --> PR
    PR --> GHRepo
    GHRepo --> GHA
    GHA --> Lint
    GHA --> Test
    Lint --> DockerBuild
    Test --> DockerBuild
    DockerBuild --> ECR3

    GHRepo -->|"infra 변경"| AtlantisGH
    AtlantisGH --> TFPlan
    TFPlan -->|"PR merge"| TFApply

    ECR3 -->|"이미지 태그 업데이트"| ArgoCD3
    ArgoCD3 --> HelmUpgrade
    HelmUpgrade --> K8sApply
    K8sApply --> Verify

    style Build fill:#e3f2fd
    style InfraDeploy fill:#fff3e0
    style K8sDeploy fill:#e8f5e9
```

### 7.3 Local vs Production 실행 환경 비교

| 항목 | Local | Production |
|------|-------|-----------|
| **Agent Runner** | `DockerRunRunner` | `ArgoWorkflowRunner` |
| **Agent 실행** | `docker exec` (Docker Socket) | Argo Workflow Template → Pod |
| **네트워크** | `arkraft` Docker 네트워크 (external) | K8s Service Discovery |
| **Namespace** | - (Docker) | `arkraft-sandbox` |
| **S3** | MinIO (로컬) | AWS S3 (`arkraft.quantit.ai`) |
| **DB** | Docker PostgreSQL | RDS PostgreSQL 17.2 |
| **Redis** | Docker Redis | ElastiCache Redis 7.1 |
| **MCP 접근** | Docker 네트워크 내 HTTP/Stdio | K8s 내부 Service / Istio VirtualService |
| **인증** | Cognito (동일) | Cognito (동일) |
| **환경변수** | `.env` 파일 | K8s Secrets + ConfigMap |
| **이미지** | `docker build` 로컬 | ECR (multi-arch) |
| **모니터링** | - | Prometheus + Grafana |

### 7.4 K8s 서비스 구성

**Namespaces**:

| Namespace | 용도 | 주요 워크로드 |
|-----------|------|-------------|
| `arkraft` | 메인 서비스 | web, api, agent-manager, alpha-pool-mcp |
| `arkraft-sandbox` | 에이전트 격리 | agent pods (동적 생성) |
| `argo` | 워크플로우 | Argo Workflows controller + pods |

**Istio VirtualService 라우팅**:

| Host | Gateway | Target | 비고 |
|------|---------|--------|------|
| `arkraft.trade` | External | arkraft-web | 인터넷 공개 |
| `arkraft-api.quantit.ai` | External | arkraft-api | `/internal/*` 경로 차단 |
| `alpha-pool-mcp.quantit.ai` | Internal | alpha-pool-mcp | VPN only |

---

## 8. 보안 및 인증

### 8.1 전체 인증 아키텍처

```mermaid
flowchart TB
    subgraph External["외부 접근"]
        Browser["Browser<br/>(사용자)"]
        AgentContainer["Agent Container"]
        InternalService["내부 서비스<br/>(VPC)"]
    end

    subgraph AuthLayer["인증 계층"]
        subgraph CognitoAuth["Cognito 인증 (Protected)"]
            GoogleOAuth["Google OAuth"]
            MagicLink["Magic Link"]
            CognitoPool["Cognito User Pool"]
            JWT["JWT Token<br/>(RS256, JWKS)"]
        end

        subgraph AgentAuth["Agent 인증"]
            AgentKey["X-Agent-API-Key"]
            SHA256["SHA-256 해시 검증"]
            AgentCreds["agent_credentials 테이블"]
        end

        subgraph InternalAuth["Internal 인증"]
            VPCCheck["VPC 네트워크 격리\n(헤더 검증 없음)"]
        end
    end

    subgraph API["arkraft-api"]
        PublicRoutes["/health, /community (GET)<br/>Public - 인증 없음"]
        ProtectedRoutes["/api/* <br/>Protected - JWT Bearer"]
        AgentRoutes["/community (POST)<br/>Agent - API Key"]
        InternalRoutes["/internal/*<br/>Internal - Secret"]
    end

    Browser -->|"Authorization: Bearer"| JWT
    JWT --> ProtectedRoutes

    Browser -->|"No Auth"| PublicRoutes

    AgentContainer -->|"X-Agent-API-Key"| AgentKey
    AgentKey --> SHA256
    SHA256 --> AgentCreds
    AgentCreds --> AgentRoutes

    InternalService --> VPCCheck
    VPCCheck --> InternalRoutes

    GoogleOAuth --> CognitoPool
    MagicLink --> CognitoPool
    CognitoPool --> JWT
```

### 8.2 IRSA 역할 목록

| IRSA Role | ServiceAccount | 권한 | 적용 Namespace |
|-----------|---------------|------|---------------|
| `argo-workflows-role` | argo-workflows | S3 R/W, ECR pull | argo |
| `arkraft-agent-role` | arkraft-agent | S3 R/W, Bedrock invoke | arkraft-sandbox |
| `arkraft-api-server-role` | arkraft-api | S3 R/W, Cognito, SES | arkraft |
| `alpha-pool-mcp-role` | alpha-pool-mcp | DynamoDB R/W, OpenSearch, RDS | arkraft |
| `argocd-role` | argocd | ECR pull, K8s full | argocd |
| `karpenter-role` | karpenter | EC2 manage, pricing | karpenter |
| `external-dns-role` | external-dns | Route53 manage | kube-system |

### 8.3 네트워크 보안 계층

| 계층 | 메커니즘 | 설명 |
|------|---------|------|
| **Edge** | Istio External Gateway | 인터넷 트래픽 TLS 종료, 도메인 기반 라우팅 |
| **VPN** | Istio Internal Gateway | VPN 전용 서비스 (alpha-pool-mcp, 관리 도구) |
| **Service Mesh** | Istio mTLS | 서비스 간 통신 암호화 |
| **API Gateway** | Istio VirtualService | `/internal/*` 경로 외부 차단 |
| **Pod Security** | gVisor Runtime Class | Agent sandbox에서 gVisor 컨테이너 격리 |
| **IAM** | IRSA | Pod 단위 최소 권한 AWS 접근 |
| **Network Policy** | K8s NetworkPolicy | Namespace 간 트래픽 제어 |
| **Secrets** | K8s Secrets | 민감 정보 암호화 저장 |

---

## 9. 핵심 아키텍처 결정 사항 (ADR)

### ADR-1: Clean Architecture (arkraft-api)

**결정**: 4계층 Clean Architecture 채택 (Domain → Application → Infrastructure → Presentation)
**이유**: 비즈니스 로직과 인프라 의존성의 명확한 분리. 에이전트 러너 백엔드(Docker/Argo) 교체 시 도메인/애플리케이션 계층 변경 불필요. 테스트 용이성 확보.
**트레이드오프**: 초기 보일러플레이트 증가, 작은 기능에도 여러 계층 파일 생성 필요.

### ADR-2: Agent Runner 듀얼 백엔드 (Docker + Argo)

**결정**: 환경변수(`AGENT_RUNNER`)로 Docker/Argo 런타임 선택
**이유**: 로컬 개발 환경에서 Argo 없이 빠른 에이전트 테스트 가능. 프로덕션에서는 Argo Workflows의 스케줄링, 리소스 관리, 재시도 기능 활용.
**트레이드오프**: 두 런타임 모두 유지/테스트해야 하는 부담.

### ADR-3: Claude Agent SDK + MCP 기반 에이전트

**결정**: 각 에이전트를 독립 컨테이너 + Claude Agent SDK + MCP 서버 조합으로 구현
**이유**: 에이전트별 독립 배포/스케일링, MCP를 통한 도구 접근 표준화, Claude의 추론 능력 활용. 세션 복원(Alpha Agent)을 통한 비용 효율적 중단/재개 지원.
**트레이드오프**: Claude API 비용, MCP 서버 관리 오버헤드.

### ADR-4: SSE 3패턴 다중 스트리밍

**결정**: Builder SSE, Session SSE, Data Query SSE 세 가지 패턴 병행
**이유**: 각 유즈케이스별 최적 스트리밍 방식이 다름. Builder는 실시간성 중요(EventEmitter + S3), Session은 폴링만으로 충분, Data Query는 과거 이력 + 실시간 결합 필요.
**트레이드오프**: 스트리밍 코드 복잡도 증가.

### ADR-5: Next.js BFF 패턴

**결정**: Next.js API Routes를 BFF(Backend For Frontend)로 활용, 약 70개 엔드포인트
**이유**: 서버사이드에서 내부 API 직접 호출로 네트워크 홉 최소화. 클라이언트에 민감한 토큰 노출 방지. API 응답 변환/집계를 BFF에서 처리.
**트레이드오프**: BFF 유지 비용, API 변경 시 BFF도 함께 수정 필요.

### ADR-6: Karpenter 기반 멀티 NodeClass

**결정**: 5개 EC2NodeClass (default-arm64/x86, gvisor-arm64/x86, gpu-x86) 운영
**이유**: 워크로드 특성별 최적 인스턴스 유형 선택. arm64로 비용 절감(기본), gVisor로 에이전트 보안 격리, GPU로 ML 워크로드 지원.
**트레이드오프**: NodeClass 관리 복잡도, AMI 업데이트 부담.

### ADR-7: Atlantis를 ECS Fargate에 배치

**결정**: Atlantis를 EKS가 아닌 ECS Fargate에 배포
**이유**: EKS Ops Node Group 업데이트 시 Atlantis가 영향받는 것을 방지. Terraform apply 중 EKS 노드 롤링 업데이트가 발생하면 Atlantis 자체가 중단될 위험이 있음.
**트레이드오프**: ECS Fargate 별도 관리 비용.

### ADR-8: Alpha Pool 데이터 파이프라인 (DynamoDB → OpenSearch)

**결정**: DynamoDB Streams + Lambda + Bedrock 기반 실시간 인덱싱 파이프라인
**이유**: Finter의 알파 데이터를 LLM으로 보강(메타데이터, 태그)하고, 벡터 임베딩으로 시맨틱 검색 지원. Portfolio Agent의 알파 검색 품질 향상.
**트레이드오프**: Bedrock API 비용, Lambda cold start 지연.

### ADR-9: Istio 이중 Gateway

**결정**: External(인터넷) + Internal(VPN only) 두 개의 Istio Gateway 운영
**이유**: 공개 서비스(web, api)와 내부 전용 서비스(alpha-pool-mcp, 관리 도구)의 네트워크 접근 분리. VPN을 통해서만 접근 가능한 서비스로 보안 강화.
**트레이드오프**: Gateway 이중 관리, VPN 의존성.

### ADR-10: Report Agent의 FastAPI 서버 방식

**결정**: Report Agent만 FastAPI 서버(port 8888)로 동작, `POST /execute`로 base64 payload 수신
**이유**: 다른 에이전트(CLI 방식)와 달리, Report Agent는 다단계 모델 전환(haiku → sonnet)과 복잡한 데이터 수집이 필요. HTTP 서버 방식으로 상태 관리와 에러 핸들링이 용이.
**트레이드오프**: 다른 에이전트와 실행 패턴 불일치.

### ADR-11: KMS Envelope Encryption (ARK-944)

**결정**: 외부 DB credentials 암호화 시 AES-GCM 단순화 없이 AWS KMS Envelope Encryption v1 직행. dev bypass 제공(`DATA_SOURCE_KMS_ENABLED=false` → `"dev:" + base64`).
**이유**: 보안 강도 우선. AES-GCM MVP 단계를 생략하여 프로덕션 암호화 표준을 처음부터 적용. dev 환경에서는 bypass로 KMS 없이 빠른 개발 가능.
**트레이드오프**: aioboto3 KMS 의존성 추가, 로컬 개발 시 AWS credentials 필요 (또는 bypass 사용).

### ADR-12: Data Agent의 waiting_input 재개 패턴 (ARK-944)

**결정**: scan 세션 내 Phase 전환 시 기존 DataPipeline waiting_input 패턴 재사용 (S3 `user_answers.json` → Redis pub/sub → agent 재개).
**이유**: 이미 검증된 패턴. scan(Phase 1) → propose(Phase 2) → 사용자 선택 → trial(Phase 3) → extract(Phase 4+5)의 순차적 진행에 동일한 재개 메커니즘 적용하여 코드 재사용성 극대화.
**트레이드오프**: proposals DB SSOT (S3 proposals.json 없음), agent 재개 시 S3에서 user_answers.json 폴링 필요.

### ADR-13: sync 서브커맨드는 LLM 없음 (ARK-944)

**결정**: `sync` CLI 서브커맨드는 Claude Agent SDK를 사용하지 않고 순수 Python으로 구현. extract_recipe.json 기반 증분 쿼리 자동 실행.
**이유**: 정기 동기화는 매번 동일한 로직 반복. LLM 호출 비용 및 불필요한 지연 제거. extract_recipe.json에 쿼리와 last_value가 모두 저장되어 있어 LLM 없이도 완전 자동화 가능.
**트레이드오프**: 스키마 변경 시 자동 적응 불가 → Schema Drift 감지로 보완 (M12).

---

> 이 문서는 Arkraft 플랫폼의 전체 아키텍처를 개괄한다. 각 서브시스템의 상세 구현은 해당 레포지토리의 `CLAUDE.md` 및 코드를 참조할 것.
