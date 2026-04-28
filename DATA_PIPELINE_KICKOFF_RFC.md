# Data Pipeline Kickoff RFC v0.3 — Source-Bundle → Team Datalake → Catalog-Build → Operations Loop

> **상태**: v0.3 draft (kickoff 미팅 전 합의용 초안 — 사용자의 새 vision 반영 재작성)
> **작성**: 백재현 (`<@U015U3DL4RK>`)
> **대상 독자**: 데이터 팀 (`<!subteam^S04D8GC39F0>`), AMT 팀 (`<!subteam^S089G4FCJRJ>`), PoC 의사결정자 (아키텍트/CTO)
> **연관 에픽**: `ARK-1315` (Data Pipeline · Focus 2026Q2), `ARK-1328` (Arkraft Showcase, 별칭 "데이터 마켓플레이스" — `.claude/rules/jira.md:41` · Evolution 2026Q2)
> **이 문서의 목적**: kickoff 미팅에서 양 팀이 함께 띄워 보면서 **역할 분담과 다음 액션을 합의**하기 위한 단일 문서.

> **v0.2 → v0.3 변경 요약**: §2.1 흐름이 3-stage(`data → pipeline → catalog`)에서 **4-stage(`Source-Bundle → Team Datalake → Catalog-Build → Operations Loop`)** 로 확장. 신규 컴포넌트 4개(Source-Bundle / Team Datalake / Datalake-Build Agent / Catalog-Build Agent / Operations Loop)가 추가되었고, **AWS-free PoC 제약**이 명시적 설계 변수로 등장. 기존 v0.2의 컴포넌트는 폐기되지 않고 신규 agent의 first-implementation prototype으로 흡수된다 (§3.1.6 마이그레이션 시각 참조).

---

## 1. 배경/맥락

### 1.1 왜 지금 이 작업이 필요한가

회사 전략이 정렬되면서 데이터 협업의 우선순위가 격상되었다.

- **PMF 시그널은 inbound 기준으로 잡혔고, 형태는 PLG가 아니라 딜 단위 high-touch FDE delivery로 굳어지고 있다** (출처: Slack `<#C0933M2A5CK>` 2026-04-26 이동현). 그래서 헤지펀드/증권사/자산운용 각각의 mandate에 fit한 arena를 standup 해주는 것이 핵심 가치 제안이 되었다.
- **BYOC 배포에서 정적 IP(프롬프트·코드)의 기술적 보호는 구조적으로 불가능하다는 결론이 났다** (출처: Slack `<#C0933M2A5CK>` 2026-04-28 김일웅). 따라서 IP 정의를 동적 자산(**데이터 · 개선 속도 · 운영 노하우**) 중심으로 재편하기로 했고, 데이터는 회사가 보호해야 할 IP의 1순위가 되었다.
- **PoC 제약 — AWS 미사용 가능성**: 향후 BYOC PoC 환경에서는 고객 AWS 계정 외의 인프라(예: on-prem, 다른 클라우드)에서 datalake / 운영 자동화 구동이 요구될 수 있다 (출처: 사용자 vision 명시). 이 RFC는 v0.2의 AWS-tightly-coupled 가정을 풀고 backend 추상화 layer를 설계 변수로 노출시킨다.
- 이미 코드 레벨에서는 외부 DB → 자동 스캔 → Dataset 후보 propose → Workflow 검증 → Argo CronWorkflow 등록 → 주기 자동 동기화 흐름이 `arkraft-agent-data`에 구현되어 있다 (출처: ARK-944 description, `arkraft-agent-data/README.md:50-87`). 즉 **파이프라인의 "기계"는 돌아간다**. 다만 그 위에서:
  - **source의 맥락 문서(spec / dictionary)를 source와 함께 묶어 저장하는 layer가 없다**;
  - **여러 source를 통합한 team-isolated datalake가 없다** — 1 source → 1 catalog 1:1 매핑만 가능;
  - **사용자 의도 → catalog 매핑이 LLM 단일 propose로 끝나며, 의도 변경 / 사용자 대화 / 적재 코드 저장 흐름이 없다**;
  - **datalake update event → catalog 자동 갱신 시스템이 없다** (`data-sync`는 cron 기반).

### 1.2 현재 진행 중인 비공식 협업

이미 양 팀 사이에 다음 협업 흐름이 비공식으로 진행 중이다 (출처: Slack `<#C0A6BSMAG4D>`).

- 2026-03-26 백재현 → 이나현/고민혁: "fnguide에서 주는 데이터 spec 문서 받을 수 있을까요? db 연결 후 scan해서 스키마 알아오는데 spec 문서로 컬럼 정보 더 자세히 파악하도록 가이드하는 작업 중입니다."
- 2026-02-04 이나현 메모: "쓸 수 없는 데이터 필터링이 필요. compustat_us 같은 iceberg는 삭제까진 어려워도 필터링 필요. RDS는 유저가 직접 쿼리하지 못하는데 검색되어야 할까에 대한 고민중."

→ v0.3 vision의 **Source-Bundle**(source + spec 문서 그룹핑)과 **Datalake Knowledge Layer**(필터링 기준 / 노출 정책의 ground truth)가 정확히 위 비공식 흐름의 정식 표면이다.

이 RFC는 위 비공식 흐름을 **공식 협업 트랙**으로 격상시키는 출발점이다.

### 1.3 관련 Jira 에픽

| Epic | 트랙 | 상태 | 핵심 |
|------|------|------|------|
| `ARK-944` | Foundation | **Done** | "RDS scan 및 File Sync 로직 추가". Data Source 파이프라인 골격 완성. v0.3에선 Datalake-Build Agent의 first-implementation prototype 토대. (출처: ARK-944 description) |
| `ARK-1315` | Focus · 2026Q2 | In Progress (~2026-06-30) | "[2026 2Q - 집중] Data Pipeline" — 성공 기준 "TBD — 지표 or 마일스톤 (형님 확정)". 안 하면 "파이프라인 불안정은 Alpha·Agent 전 계층의 신뢰도를 깎음." (출처: ARK-1315 description) |
| `ARK-1328` | Evolution · 2026Q2 | In Progress (~2026-06-30) | "[2026 2Q - 진화] Arkraft Showcase" (별칭: 데이터 마켓플레이스, 출처: `.claude/rules/jira.md:41`). Phase 1 Featured by Quantit (자체 제작물 노출 + 고객 계정 셋업) → Phase 2 파트너 연동 (Finter 데이터 카탈로그 Browse/Subscribe, API 접근 제어) → Phase 3 Open Marketplace. (출처: ARK-1328 description) |

`ARK-944`가 **이미 끝난 토대**, `ARK-1315`가 **이번 분기 목표 (운영 안정화 + v0.3 골격 prototype)**, `ARK-1328`이 **그 다음 단계 (외부 노출)**. 이 RFC는 ARK-1315의 성공 기준 합의 + ARK-1328 Phase 1의 데이터 팀 책임 정의 + v0.3 신규 컴포넌트의 first prototype 합의를 동시에 다룬다.

---

## 2. 목표 (Source-Bundle → Team Datalake → Catalog-Build → Operations Loop)

### 2.1 흐름의 정의 (v0.3)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  ┌─────────────────────┐                    ┌──────────────────────────────────┐    │
│  │  Source-Bundle      │  ──────scan──────▶ │  Datalake-Build Agent            │    │
│  │  (per source)       │                    │  - source scan (AS-IS DS1 reuse) │    │
│  │                     │  ──docs──────────▶ │  - bundle docs parsing           │    │
│  │  • RDS / 외부 DB    │                    │  - id map / 컬럼 값/단위 추출     │    │
│  │  • CSV upload       │                    │  - knowledge layer materialize   │    │
│  │  • 애널리스트 리포트 │                    │  (uses ADR-12 waiting_input)     │    │
│  │  • + 맥락 문서       │                    └──────────────────────────────────┘    │
│  │   (FnGuide spec,   │                              │                              │
│  │    column dict,    │                              ▼                              │
│  │    table 정의서)    │                    ┌──────────────────────────────────┐   │
│  └─────────────────────┘                    │  Team Datalake                   │   │
│           ▲                                 │  (per team, multi-tenant 격리)    │   │
│           │                                 │                                  │   │
│           │ bundle metadata                 │  Raw layer:                      │   │
│           │ (어떤 문서가                    │   • per-source parquet/iceberg    │   │
│           │  어떤 테이블/컬럼을              │  Knowledge layer:                │   │
│           │  설명?)                         │   • id map (벤더별 ticker / 재무 │   │
│           │                                 │     코드 매핑)                    │   │
│           │                                 │   • 컬럼 값 enumeration           │   │
│           │                                 │   • 단위 정보                     │   │
│           │                                 │   • column → doc reference        │   │
│           │                                 │  ⚠ AWS-free PoC 가능 (§4.6, §8.2) │   │
│           │                                 └──────────────────────────────────┘   │
│           │                                           │                            │
│           │                                           │ datalake update event      │
│           │                                           │ + intent slice resolution  │
│           │                                           ▼                            │
│           │                                 ┌──────────────────────────────────┐   │
│           │                                 │  Catalog-Build Agent             │   │
│           │                                 │  1. 사용자 의도 input             │   │
│           │                                 │  2. datalake/knowledge 참조       │   │
│           │                                 │  3. catalog 후보 제안             │   │
│           │                                 │  4. 사용자와 대화 (ADR-12 재사용) │   │
│           │                                 │  5. 합의된 catalog 적재           │   │
│           │                                 │  6. 적재 코드 저장 (운영 input)    │   │
│           │                                 └──────────────────────────────────┘   │
│           │                                           │                            │
│           │                                           ▼                            │
│           │                                 ┌──────────────────────────────────┐   │
│           │                                 │  Catalog                         │   │
│           │                                 │  arkraft-sdk:                    │   │
│           │                                 │   Catalog().browse / inspect /   │   │
│           │                                 │           summary / search       │   │
│           │                                 │  S3: catalogs/{cm_id}.parquet    │   │
│           │                                 │  (출처: arkraft-sdk/README.md:46-│   │
│           │                                 │   69)                            │   │
│           │                                 └──────────────────────────────────┘   │
│           │                                           │                            │
│           │                                           ▼                            │
│           │                                 ┌──────────────────────────────────┐   │
│           │                                 │  Operations Loop                 │   │
│           │                                 │  - datalake update event listener│   │
│           │                                 │  - 저장된 적재 코드 dependency    │   │
│           │                                 │    resolution                    │   │
│           │                                 │  - 자동 코드 실행 (LLM-free)      │   │
│           │                                 │    (extends ADR-13 data-sync)    │   │
│           │                                 │  - catalog refresh                │   │
│           │                                 └──────────────────────────────────┘   │
│           │                                           │                            │
│           └───────────────────────────────────────────┘                            │
│                              feedback                                              │
│                              (datalake re-scan trigger)                            │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Stage 1 — Source-Bundle**: 1 source(예: FnGuide RDS) + 그 source의 맥락 문서들(예: FnGuide spec PDF, column dictionary, 테이블 정의서)을 하나로 묶은 단위. AMT의 propose 단계가 spec을 prompt에서 참조 가능하도록 그룹핑 형식의 metadata를 가진다. (출처: 사용자 vision, Slack `<#C0A6BSMAG4D>` 2026-03-26 백재현)

**Stage 2 — Team Datalake**: 한 team의 모든 source-bundle을 통합한 raw + knowledge 저장소. **team별로 격리(multi-tenant)** 되며, AWS 서비스에 의존하지 않을 수 있다(§4.6, §8.2 Open Q1). Raw layer는 per-source parquet/iceberg, Knowledge layer는 id map / 컬럼 값 / 단위 / column-doc reference 등 metadata SSOT. **Datalake-Build Agent** (§3.1.4)가 source-bundle → team datalake 빌드를 담당.

**Stage 3 — Catalog-Build Agent**: 사용자 의도 자연어 → catalog. (1) 사용자 input ("KOSPI 200 종목들의 PER 시계열") → (2) datalake schema + knowledge 참조해 catalog 후보 제안 → (3) **사용자와 multi-turn 대화로 의도 정밀화** — 각 turn은 ADR-12 waiting_input 1 사이클(`input_request.json` → `user_answers.json` polling)을 N번 반복하는 형태로 구현 가정 (`ARCHITECTURE.md:1590-1594`). multi-turn dialog가 단일 사이클 반복으로 충분한지 vs 별도 메커니즘이 필요한지는 §8.2 Q7 — A3 prototype 착수 전 결정 필요 → (4) 합의된 catalog 적재 + (5) **적재 코드 저장** (Operations Loop input). 결과 catalog는 기존 `arkraft-sdk` Catalog API(`Catalog().browse / inspect / summary / search`, 출처: `arkraft-sdk/README.md:46-69`)로 노출.

**Stage 4 — Operations Loop**: datalake update event → 저장된 catalog 적재 코드 자동 실행 → catalog refresh. 기존 `data-sync` Argo CronWorkflow(LLM-free, ADR-13, `ARCHITECTURE.md:1596-1600`)의 **trigger를 cron이 아닌 datalake update event로 진화**시킨 형태. 처리 대상이 단일 cm가 아니라 dependency-resolved catalog set.

### 2.2 이번 협업으로 도달하려는 상태

분기 말(2026-06-30)까지 다음 다섯이 동시에 성립해야 한다.

1. **운영 안정화 (ARK-1315 close)** — 외부 RDS source-bundle에서 들어온 데이터가 사람의 수동 개입 없이 datalake → catalog까지 도달하고, datalake update가 fail하지 않는다. 실패 시 진단·복구 절차가 명확하다.
2. **Source-Bundle 정의 / 큐레이션 거버넌스 합의** — "어떤 source-bundle 형식을 받을 수 있는가" 기준이 합의되어 있고, 그 게이트를 지키는 책임자가 정해져 있다.
3. **Datalake Knowledge Layer ground truth 책임자 결정** — id map / 컬럼 값 / 단위 정보의 SSOT가 데이터 팀인지 AMT인지 명시.
4. **Catalog-Build Agent + Operations Loop prototype** — 사용자 의도 → datalake slice → catalog 적재 + 코드 저장 + datalake update 자동 catalog refresh가 1개 source-bundle에 대해 완전 통합 시연 가능.
5. **Showcase Phase 1 ready (ARK-1328 Phase 1 close)** — 외부 고객(Early Access)이 처음 들어왔을 때 "Featured by Quantit" 자체 제작 catalog N개가 보일 수 있다. 데이터 팀이 큐레이션한 catalog quality check 통과본만 노출된다.

### 2.3 비목표 (이번 협업 범위 밖)

명시적으로 **이번 RFC 범위에 포함하지 않는다**.

- **Phase 3 Open Marketplace** (ARK-1328 Phase 3) — 외부 제작자가 카탈로그를 등록·거래하는 모델. 이번 분기 외 작업.
- **Investment Universe 확장** (ARK-1329) — 새 유니버스 추가 작업. 별도 에픽.
- **AWS-free PoC 의 정식 backend 결정** — §8.2 Q1으로 분리. 이번 RFC는 backend 추상화 계약(interface)만 정의.

---

## 3. 현재 상태 (As-Is)

### 3.0 데이터 입력 채널 (As-Is)

§2.1 흐름의 첫 단계인 Source-Bundle의 source 부분은 현재 다음 셋으로 들어온다 (출처: `arkraft-agent-data/README.md:13-18`, `arkraft-agent-extract/README.md:9-12`).

| 채널 | 진입 방법 | 현재 운영 |
|------|-----------|----------|
| 외부 DB 연결 (PostgreSQL/MySQL) | API에 connection 등록 → KMS 암호화 → DS1 scan 자동 실행 | ARK-944로 골격 구현 완료. 사용자 등록 / 사용자 선택 흐름은 검증 단계 |
| 사용자 CSV 직접 업로드 | `arkraft data upload` (CLI) 또는 web UI → S3 업로드 → S1 detect-normalize 트리거 | 운영 중. 5-Phase 모두 검증된 경로 |
| 애널리스트 리포트 (PDF/DOCX/XLSX/text) | `arkraft-agent-extract` `extract` 호출 → Bedrock Sonnet 4.6 dual output → arkraft-api 소비 | 운영 중. Pydantic AI v2 (Claude Agent SDK 미사용) |

> **Bundle 측면 (맥락 문서) 부재**: 위 3개 채널 모두 source 자체만 받고, 그 source의 spec / dictionary / 테이블 정의서를 함께 받는 형식(Source-Bundle)은 미구현. 비공식으로는 데이터 팀이 spec PDF를 별도 전달하고 있음 (Slack 2026-03-26).

### 3.1 코드 레벨에서 이미 구현된 것 (v0.2 → v0.3 매핑)

#### 3.1.1 Data Source 5-Phase 파이프라인 (출처: `ARCHITECTURE.md:591`, `arkraft-agent-data/README.md:80-86`, ARK-944 description)

| 단계 | 명령 | 방식 | 출력 | v0.3 매핑 |
|------|------|------|------|----------|
| DS1 | `scan` | 결정론적 | DB 연결 → 전체 테이블/스키마/인덱스 스캔 → `scan_result.json` | Datalake-Build Agent의 source scan sub-step (재사용) |
| DS2 | `propose` (단일) / `propose-team` (팀 전체 일괄) | LLM | scan 결과 기반 Dataset 후보 복수 제안 → `proposals.jsonl` | (1) Datalake-Build Agent의 knowledge extraction + (2) Catalog-Build Agent의 intent → catalog proposal로 split |
| DS3 | `trial` | LLM + 실제 실행 | extract 스크립트 작성 → 시범 쿼리(LIMIT 1000) 실행 → `extract_script.py`, `column_annotations.json`, `trial.parquet` | Catalog-Build Agent의 trial run on datalake slice |
| DS4 | `extract` | LLM + 실제 실행 | 전체 데이터 추출 → 일별 Parquet 분할 업로드 → `extract_recipe.json` | (1) Datalake-Build Agent의 datalake materialization + (2) Catalog-Build Agent의 catalog materialization으로 split |
| DS5 | `pipeline` (자동 트리거) | 결정론적 | extract 완료 후 CSV 5-Phase 진입 → catalog 등록 (출처: `ARCHITECTURE.md:591` `data-scan` 5-Phase 정의) | Operations Loop의 datalake-side update event listener (cron → event-driven 진화) |

#### 3.1.2 CSV 5-Phase 파이프라인 (출처: `arkraft-agent-data/README.md:88-98`)

| 단계 | 명령 | 방식 | 출력 | v0.3 매핑 |
|------|------|------|------|----------|
| S1 | `detect-normalize` | LLM | `detection_report.json`, `normalized.parquet` | Datalake-Build Agent의 CSV ingestion path (재사용) |
| S2 | `cm-check` | 결정론적 (DuckDB) | `readiness.json` | Datalake-Build Agent의 quality gate |
| S3 | `spec` | LLM + 사용자 피드백 | `spec.json` (Q&A `input_request.json`/`user_answers.json`) | (1) Datalake-Build Agent의 schema 정합 + (2) Catalog-Build Agent dialog로 split |
| S4 | `transform` | LLM | `data.parquet`, `incremental_recipe.json` | Catalog-Build Agent의 적재 코드 저장 prototype |
| S5 | `register` | 결정론적 | `register.json` (catalog 등록) | Operations Loop의 code persistence prototype |

#### 3.1.3 증분 동기화 / Catalog 노출 / 보안

- **`data-sync` Argo CronWorkflow** (LLM-free, 출처: `ARCHITECTURE.md:592` 및 ADR-13 `ARCHITECTURE.md:1596-1600`). `extract_recipe.json` 기반으로 매일 결정론적으로 증분 쿼리 실행. **v0.3 Operations Loop의 first-implementation prototype**.
- **Catalog 노출** (`arkraft-sdk`, 출처: `arkraft-sdk/README.md:46-69`, `arkraft-cli/README.md:86-101`):
  - `Catalog().summary()` / `browse(universe)` / `inspect(universe, cm_name)` / `search(query, universe)`. **v0.3에서도 그대로 유지** — datasource는 datalake가 아니라 catalog parquet 자체.
  - S3 경로: `s3://{bucket}/teams/{team_id}/catalogs/{cm_id}.parquet` — `cm_id = {universe}.{cm_name}` (출처: `arkraft-agent-data/CLAUDE.md` S3 Path Structure). **AWS-free PoC 시 backend 분기점**.
- **보안 / 인증**:
  - 외부 DB credentials는 KMS Envelope Encryption (ADR-11, `ARCHITECTURE.md:1584-1588`, ARK-944). **AWS-free PoC 시 분기점** — local secret store / age / SOPS 등.
  - `waiting_input` 재개 패턴 (ADR-12, `ARCHITECTURE.md:1590-1594`, ARK-944) — scan(P1) → propose(P2) → 사용자 선택 → trial(P3) → extract(P4+5) 사이에 user_answers.json으로 사용자 결정 주입. **단방향 단일 사이클** 패턴이며 v0.3 Catalog-Build Agent의 multi-turn 대화는 이 사이클을 N번 반복하는 형태로 구현 가정. multi-turn 메커니즘 확정은 §8.2 Q7 (A3 prototype 착수 전 결정).

#### 3.1.4 Datalake-Build Agent (v0.3 신규 — 미구현)

- **책임**: source-bundle → team datalake 구축
- **현재 코드 부재**. 기존 `arkraft-agent-data` DS1/DS4/CSV S1/S2/S3가 일부 building block.
- **재활용 가능 인프라**: `arkraft-agent-extract`의 **Pydantic AI harness (실행 루프 / S3 sync / RabbitMQ callback / 도구 세트 Read·Write·Bash)** 재사용 가능 (출처: `arkraft-agent-extract/README.md:9-12`, CLAUDE.md). 단 `analyst-report-extractor` skill은 애널리스트 리포트 전용 7-section 포맷이므로, **bundle 내 spec/dictionary 문서 파싱용 신규 skill 작성 필요** (`source-spec-parser` 같은). dual output 자체를 재활용하는 것이 아니라 harness만 재활용.
- **데이터 팀이 이 Agent에 제공해야 하는 인풋** (§5 D-row 종합):
  - source-bundle 샘플 (D1 산출물, Week 2)
  - "쓸 수 있는 데이터" verdict 매트릭스 (D2 산출물, Week 3)
  - knowledge layer ground truth — id map / 컬럼 값 / 단위 / column-doc reference (D3 산출물, Week 6)
  - bundle metadata 형식 답변 (D8 산출물, Week 1)

#### 3.1.5 Catalog-Build Agent (v0.3 신규 — 미구현)

- **책임**: 사용자 의도 → catalog (multi-turn 대화 기반)
- **현재 코드 부재**. 기존 `arkraft-agent-data` DS2/DS3/DS4/S3/S4가 일부 building block.
- **재활용 가능 메커니즘**:
  - ADR-12 waiting_input 단일 사이클 (`ARCHITECTURE.md:1590-1594`)을 **N번 반복**해서 multi-turn dialog 구현 (§8.2 Q7 — 단일 사이클 N회 반복으로 충분한지 별도 메커니즘이 필요한지 prototype 착수 전 결정)
  - `arkraft-sdk` Catalog API는 그대로 외부 노출 표면

#### 3.1.6 v0.2 → v0.3 마이그레이션 시각

v0.3는 **기존 v0.2 시스템을 폐기하지 않는다**. 대신:
- 기존 `arkraft-agent-data` 5-Phase는 Datalake-Build Agent의 first-implementation prototype으로 **흡수**
- 기존 `arkraft-sdk` Catalog API는 v0.3 catalog의 외부 표면으로 **유지**
- 기존 `data-sync` CronWorkflow는 Operations Loop의 first-implementation prototype으로 **흡수** (cron → event-driven으로 진화)

즉 **v0.2 → v0.3는 incremental refactor + new agent 추가**. 큰 폭의 backend 교체는 PoC 제약(AWS-free, §4.6) 시점에서만 발생한다. (출처: 사용자 vision; 흡수 매핑 근거는 `arkraft-agent-data/README.md:80-98` 5-Phase, `ARCHITECTURE.md:592` data-sync, `arkraft-sdk/README.md:46-69` Catalog API 인터페이스)

### 3.2 데이터 팀 외부 자산 (v0.3 Source-Bundle 후보)

데이터 팀이 운영 중인 외부 데이터 자산 — Iceberg (`compustat_us` 등), RDS, Finter 문서 (출처: Slack `<#C0A6BSMAG4D>` 2026-02-04 이나현 메모). **v0.3 Source-Bundle의 source 후보**. 자산별 적재 우선순위는 §5 D7, datalake ingestion 견적은 §6 A11에서 다룬다.

### 3.3 비어 있는 영역 (v0.3 vision 기준)

v0.3 vision 7가지 핵심 변화 모두에 대해 현재 구현이 없다:

- **Source-Bundle 그룹핑 미구현**: source + 맥락 문서 묶음 형식 정의 부재 (출처: 사용자 vision)
- **Team Datalake 미구현**: per-team 격리된 raw + knowledge 통합 저장소 부재 (출처: 사용자 vision)
- **Datalake Knowledge Layer 미구현**: id map / 컬럼 값 / 단위 SSOT 부재 (출처: 사용자 vision)
- **Datalake-Build Agent 미구현**: §3.1.4 (출처: `arkraft-agent-data` 코드에 없음)
- **Catalog-Build Agent 미구현**: §3.1.5 (출처: 동상)
- **Operations Loop 미구현**: datalake update event 기반 catalog auto-refresh 부재. `data-sync`는 cron 기반 (출처: `ARCHITECTURE.md:592`, ADR-13)
- **AWS-free backend 분기점 정의 부재**: 현재 시스템이 KMS / S3 / Argo / EKS에 tight하게 결합 (출처: `ARCHITECTURE.md:1584-1601`)

추가로 v0.2부터 이어지는 미해결:
- 데이터 팀 자산(Iceberg, Compustat US, RDS, Finter 등) ↔ AMT의 SDK Catalog 사이의 **공식 통합 경로 없음** (출처: Slack `<#C0A6BSMAG4D>` 2026-02-04 이나현 메모)
- "쓸 수 있는 데이터 / 못 쓰는 데이터" 필터링 기준 미정 (출처: Slack `<#C0A6BSMAG4D>` 2026-02-04 이나현)
- propose 단계가 LLM 자동 생성한 cm_id 네이밍 / 메타데이터 / deprecation 정책에 대한 **사람 검수 게이트 부재** (출처: `arkraft-agent-data/CLAUDE.md` propose-team 패턴 + ADR-12)
- ARK-1315 자체에 측정 가능한 성공 기준 없음 — "TBD — 지표 or 마일스짷 (형님 확정)" 상태 (출처: ARK-1315 description)

---

## 4. 갭 분석

§3 As-Is와 §2 목표 사이의 차이를 카테고리별로 정리한다. 각 갭이 §5/§6 역할 매트릭스의 입력이다.

### 4.1 데이터 정의 / Source-Bundle 갭

| # | 갭 | 근거 |
|---|----|------|
| G1 | 외부 데이터 spec(FnGuide 등) 공급 채널이 비공식 — 이메일/슬랙 1:1 요청 흐름만 존재 | Slack `<#C0A6BSMAG4D>` 2026-03-26 백재현 |
| G2 | "쓸 수 있는 데이터" 정의 미합의 — compustat_us 같은 iceberg를 datalake / catalog 노출 대상에서 어떻게 거를지 합의 부재 | Slack `<#C0A6BSMAG4D>` 2026-02-04 이나현 메모 |
| G3 | RDS 데이터의 사용자 직접 노출 정책 미정 — "유저가 직접 쿼리하지 못하는데 검색되어야 할까" | Slack `<#C0A6BSMAG4D>` 2026-02-04 이나현 메모 |
| G4 (신규) | Source-Bundle 형식/스키마 미정 — source + 맥락 문서 묶음의 metadata 표준 부재 | 사용자 vision; v0.3 Stage 1 정의 |

### 4.2 Datalake-Build Agent 갭

| # | 갭 | 근거 |
|---|----|------|
| G5 | DS2 propose 단계 LLM 결과의 사람 검수 게이트 부재 — 자동 생성 cm_id가 그대로 catalog로 흘러감 | `arkraft-agent-data/CLAUDE.md` propose-team 패턴 + ADR-12 |
| G6 (신규) | Team Datalake schema / multi-tenancy 모델 부재 — team 간 격리 메커니즘 미정 | 사용자 vision; v0.3 §2.1 Stage 2 |
| G7 (신규) | Knowledge Layer 데이터 모델 부재 — id map / 컬럼 값 / 단위 representation 미정 | 사용자 vision; v0.3 §2.1 Stage 2 |
| G8 (신규) | Datalake-Build Agent 미구현 — bundle 내 문서 파싱 + knowledge 추출 + raw layer 적재 일관 흐름 부재 | §3.1.4 |
| G9 | data-sync CronWorkflow 실패 시 알림 / 진단 / 복구 책임 분담 미정 — 운영자가 누구인지 불명확 | `ARCHITECTURE.md:592` |

### 4.3 Catalog-Build Agent + Operations Loop 갭

| # | 갭 | 근거 |
|---|----|------|
| G11 | cm_id 네이밍 / 카테고리 / universe 분류에 대한 큐레이션 컨벤션 없음 | `arkraft-sdk/CLAUDE.md` enums.py SSOT 언급만, 실 컨벤션 미정 |
| G12 | Catalog 메타데이터 (description, sample_period, delivery_lag, license)의 SSOT 위치 미정 — `inspect()` 응답 품질을 누가 책임지는지 모름 | `arkraft-sdk/README.md:46-69` Catalog API + ADR-12 proposals DB |
| G13 (신규) | Catalog-Build Agent 미구현 — 사용자 의도 input → datalake 슬라이스 + 적재 코드 저장 일관 흐름 부재 | §3.1.5 |
| G14 (신규) | Operations Loop 미구현 — datalake update event 발행 / 코드 dependency resolution / 자동 재실행 시스템 부재 | §3.1.3 (data-sync는 cron 기반) |
| G15 (신규) | 적재 코드 저장소 schema 미정 — Catalog-Build Agent의 output 코드를 어디에/어떤 형식으로 저장할지 미합의 | 사용자 vision |

### 4.4 외부 노출 / Showcase 갭

| # | 갭 | 근거 |
|---|----|------|
| G16 | ARK-1328 Phase 1 "Featured by Quantit"에서 데이터 카탈로그 큐레이션 책임자 미정 | ARK-1328 description |
| G17 | Showcase에 노출되는 카탈로그 quality check 게이트 정의 부재 | ARK-1328 description |
| G18 | Phase 2 Finter 파트너 연동의 데이터 팀 contact 라인 미정 — Finter는 데이터 팀 영역인지 AMT 영역인지 합의 없음 | ARK-1328 description, Slack `<#C0A6BSMAG4D>` 2026-02-13 Finter 캐싱 PR |

### 4.5 거버넌스 / IP 갭

| # | 갭 | 근거 |
|---|----|------|
| G19 | 동적 IP로서의 "데이터" 정의가 회사 차원에선 결정됐으나 운영 차원의 책임 매트릭스 부재 | Slack `<#C0933M2A5CK>` 2026-04-28 김일웅 |
| G20 | BYOC 환경에서 고객별 카탈로그 격리 / 라이선스 모델 미정 — "고객별 mandate에 fit한 arena" 전략 (출처: Slack `<#C0933M2A5CK>` 2026-04-26 이동현)과 데이터 라이선스 어떻게 결합할지 미정 | Slack `<#C0933M2A5CK>` 2026-04-26 이동현 + 2026-04-28 김일웅 |

### 4.6 PoC 인프라 갭 (신규)

v0.3 vision의 "AWS 미사용 가능성" 제약은 다음 backend 분기점들을 만든다:

| # | 영역 | AWS 의존 | AWS-free 후보 | 결정 필요 |
|---|------|---------|---------------|----------|
| G21 (신규) | Object storage | S3 | local filesystem / MinIO / on-prem S3 호환 | §8.2 Q1 |
| G22 (신규) | Secrets / KMS (ADR-11) | AWS KMS | local secret store / age / SOPS | §8.2 Q1 |
| G23 (신규) | Workflow orchestration | Argo Workflows | local cron / Prefect / 단순 systemd timer | §8.2 Q1 |
| G24 (신규) | Datalake compute | EKS Karpenter | local docker / on-prem k8s / bare metal | §8.2 Q1 |
| G25 (신규) | Datalake storage backend | (현재 catalog만 S3 parquet) | datalake 자체의 backend 미정 — Iceberg local? PostgreSQL local? DuckDB local? | §8.2 Q1 |

→ §8.2 Q1으로 통합 — "AWS-free PoC backend 결정"

#### 4.6.1 PoC 최소 운영 가능 구성 예시 (제안값)

§8.2 Q1 결정을 돕기 위한 **시작 후보 1개 — kickoff에서 PoC 아키텍트가 합의/대체 결정**:

| 영역 | 제안 backend | 근거 |
|------|-------------|------|
| Object storage | **MinIO** (single-node, S3 호환) | `arkraft-sdk/README.md:30` `S3_ENDPOINT` 환경변수가 이미 MinIO 분기를 지원 — SDK 코드 변경 불필요 |
| Secrets / KMS | **age + SOPS** (file-based, gitops 호환) | ADR-11 KMS dev bypass(`DATA_SOURCE_KMS_ENABLED=false`)가 이미 존재 (`ARCHITECTURE.md:1584-1588`) — 동일 분기점에 SOPS 추가 |
| Workflow orchestration | **단순 systemd timer + Python script** (1-node PoC 한정) | ADR-13 sync는 LLM-free 결정론적 (`ARCHITECTURE.md:1596-1600`) — Argo CronWorkflow 대신 systemd timer로 trigger 교체 가능 |
| Datalake compute | **single docker host** (1-node) | `arkraft-agent-data` 컨테이너 이미지(`arkraft-data:latest`)는 single docker host에서 실행 가능 (출처: `arkraft-agent-data/.claude/rules/architecture.md:89-110`). 단 `arkraft` Docker 네트워크 생성을 위해 `arkraft-api` compose가 먼저 실행되어야 함 (`arkraft-agent-data/README.md:185`) — PoC 시 네트워크 초기화 방법 별도 확인 필요 |
| Datalake storage backend | **DuckDB local + Parquet on MinIO** | `arkraft-agent-data` S2 cm-check이 이미 DuckDB 사용 (`arkraft-agent-data/CLAUDE.md` DuckDB 패턴) — datalake raw layer로 동일 backend 확장 |

> 이 5개 조합이 "동시에" 작동 가능한지(예: MinIO + age/SOPS + systemd + docker + DuckDB가 single-node PoC에 모두 들어가도) prototype 검증 필요 — A12 ADR(Week 2)의 입력. 위 후보가 거부되면 §8.2 Q1에서 대체안 결정.

---

## 5. 데이터 팀 역할/요청 사항

> **포맷**: action-level 매트릭스. 각 행은 `데이터 팀이 X를 Y한다 — 산출물 / 기한 / AMT 의존성`. 이 표 그대로 kickoff에서 한 줄씩 짚으면서 합의/조정.

| # | 데이터 팀이 책임지는 것 | 산출물 | 1차 기한 (제안) | AMT 의존성 |
|---|-------------------------|---------|------------------|-------------|
| D1 (신규) | **Source-Bundle 정의 / 큐레이션 기준** — 어떤 source(RDS / 외부 DB / CSV / 리포트) + 어떤 맥락 문서(spec PDF / column dict / 테이블 정의서)를 묶어서 bundle로 만들지 표준 정의 (G1, G4) | Source-Bundle 정의 1-pager + 초기 N개 bundle 샘플 (FnGuide / Compustat / 사내 RDS 등) | kickoff +2주 | AMT가 어떤 bundle metadata 형식(JSON schema / YAML 등)을 받을 수 있는지 spec 제출 (D8 참조) |
| D2 | **"쓸 수 있는 데이터" 큐레이션 매트릭스** — compustat_us / iceberg / RDS 등 자산별로 datalake 적재 가능 / 적재 불가 / 보강 필요로 구분 (G2, G3) | 자산별 verdict + 사유 매트릭스 | kickoff +3주 | AMT가 verdict 사유를 datalake knowledge layer에 어떻게 노출할지 인터페이스 제안 (A4) |
| D3 (신규) | **Datalake Knowledge Layer ground truth** — id map (벤더별 ticker / 재무 코드 매핑), 컬럼 값 enumeration, 단위 정보, column → 문서 reference의 ground truth를 데이터 팀이 작성·갱신 (G7, G12) | knowledge layer 입력 가이드 + 초기 N개 source-bundle의 knowledge entries | kickoff +6주 | AMT가 knowledge schema 확정 (A4) + 입력 인터페이스 제공 (A5) |
| D4 (신규) | **Catalog-Build Agent 사용자 의도 검수자 운영** — Catalog-Build Agent가 만든 catalog 후보를 검수하여 cm_id 네이밍 / 카테고리 / 노출 여부 최종 결정 (G5, G11) | per-intent 검수 결과 (intent × verdict × 메모) | kickoff +5주 (1차 검수 운영 시작) | AMT가 검수 UI / 워크플로우 / 알림 채널 제공 (A6) |
| D5 | **Catalog 메타데이터 SSOT 책임** — description / sample_period / delivery_lag / license / quality_note의 ground truth를 데이터 팀이 작성·갱신 (G12) | 카탈로그 메타데이터 입력 가이드 + 초기 N개 카탈로그 메타데이터 채움 | kickoff +6주 | AMT가 메타데이터 schema 확정 (A4) + 입력 인터페이스 제공 |
| D6 | **Showcase Featured 카탈로그 큐레이션** — ARK-1328 Phase 1에 노출될 "Featured by Quantit" 카탈로그를 N개 선정 + quality check 통과 (G16, G17) | Featured 카탈로그 리스트 + quality check 보고서 | kickoff +8주 | AMT가 Showcase 노출 인터페이스 (web UI / API) 제공 (A8) |
| D7 (신규) | **데이터 팀 자산(Iceberg / Compustat / Finter / RDS)의 Source-Bundle 변환 우선순위** — 어떤 자산을 언제 source-bundle로 변환할지 로드맵 | 자산별 변환 일정 (Q2 / Q3 / 미정) | kickoff +3주 | AMT가 자산별 datalake ingestion 비용 견적 제공 (A11) |
| D8 (신규) | **Source-Bundle metadata 형식 spec 답변** — AMT가 bundle metadata를 어떤 형식(JSON schema / YAML / 다른 표준)으로 받으면 가장 잘 흡수하는지 답변 (G4 후속) | "AMT가 받을 bundle metadata 형식" 1-pager | kickoff +1주 | AMT가 현재 propose의 prompt 구조 공유 (A10 작업 중 부산물) |
| D9 (신규) | **Datalake Knowledge Layer schema 검토 / 합의** — AMT가 제안하는 knowledge schema (A4)에 대한 검토 + 데이터 거버넌스 관점에서 누락 항목 제기 | schema review 코멘트 | kickoff +2주 | AMT가 schema 초안 제출 (A4) |

### 5.1 데이터 팀 작업 시작 전 AMT 선행 의존 (Hard Blocker)

§5 매트릭스의 "AMT 의존성" 컬럼을 작업 순서 관점에서 다시 본다. **데이터 팀이 일을 시작하려면 AMT에서 먼저 와야 하는 것 = hard blocker**, 그 외는 병행 가능 / 후행 의존.

| 순번 | AMT가 먼저 줘야 하는 것 (hard blocker) | 이게 없으면 막히는 데이터 팀 작업 | AMT 산출물 |
|------|-----------------------------------------|----------------------------------|-----------|
| ⓐ | propose 단계의 현재 prompt / input 형식 (Week 0~1) | D8 (bundle metadata 형식 답변), D1 source-bundle 정의 | A10 작업 시작 시 부산물로 공유 |
| ⓑ | Datalake Knowledge Layer schema 초안 (Week 1) | D3 (knowledge ground truth), D5 (catalog 메타 채움), D9 (schema review) | A4 |
| ⓒ | Catalog 검수 UI / 워크플로우 (Week 4) | D4 (1차 검수 운영, Week 5 시작) | A6 |
| ⓓ | 자산별 datalake ingestion 견적 (Week 3) | D7 (변환 우선순위 결정, Week 3) — 양방향 의존이지만 견적이 먼저 와야 우선순위 결정 가능 | A11 |
| ⓔ | Showcase 노출 인터페이스 (Week 8) | D6 결과물의 종착지 — 인터페이스 없으면 D6 문서로만 끝남 | A8 (Week 9, D6 완료 1주 후 backfill) |
| ⓕ (신규) | AWS-free backend 결정 (Week 2) — datalake / 운영 자동화 backend 선택 | D1 (source-bundle 저장 위치 결정), D3 (knowledge layer 저장 backend 결정) | A12 |

> 위 6개 외의 §5 의존성은 **병행 가능**(예: D2 verdict ↔ A4 schema 동시 진행 가능)이거나 **후행 의존**(예: A1 안정화 리포트는 D4 검수 운영 데이터 누적 후).

---

## 6. AMT 팀 역할/책임

> **포맷**: §5와 동일한 action-level 매트릭스. AMT가 책임지는 것 / 산출물 / 기한 / 데이터 팀 의존성.

| # | AMT가 책임지는 것 | 산출물 | 1차 기한 (제안) | 데이터 팀 의존성 |
|---|-------------------|---------|------------------|------------------|
| A1 | **`arkraft-agent-data` 파이프라인 운영 안정화 (v0.2 prototype 안정화)** — DS1~DS5 + S1~S5 모든 단계가 sample 데이터 셋 N개로 fail 없이 완주 (ARK-1315 close) | 안정화 리포트 + 측정 가능한 SLA (성공률 % / 평균 소요시간) | kickoff +6주 | 데이터 팀이 sample 데이터 자산 N개를 D2에서 verdict 부여한 것 중 추출 |
| A2 (신규) | **Datalake-Build Agent prototype 구현** — source-bundle → team datalake 빌드 1개 완전 통합 시연 (1 source-bundle 기준) | Datalake-Build Agent v0.1 + 통합 테스트 | kickoff +6주 | D1 source-bundle 정의 (Week 2) + D3 knowledge ground truth (Week 6) |
| A3 (신규) | **Catalog-Build Agent prototype 구현** — 사용자 의도 input → datalake slice → catalog 적재 + 적재 코드 저장 1개 완전 통합 시연 (ADR-12 waiting_input 패턴 재사용) | Catalog-Build Agent v0.1 + 통합 테스트 | kickoff +7주 | D4 검수자 운영 시작 (Week 5), A6 검수 UI 의존 |
| A4 | **Datalake Knowledge Layer schema 초안 + Catalog 메타데이터 schema 초안** — id map / 컬럼 값 / 단위 / column-doc reference / catalog metadata 필드 정의 + SSOT 위치 (datalake KB vs catalog parquet metadata) | schema ADR 1건 (knowledge + catalog 통합) | kickoff +1주 | 데이터 팀 의존 없음 — A4는 D3 / D5 / D9의 hard blocker (선행 산출물) |
| A5 | **Knowledge Layer 입력 인터페이스** — 데이터 팀이 D3에서 knowledge entries를 빠르게 입력할 수 있도록 UI(또는 CLI/Slack 봇 / git PR 워크플로) 제공 | 입력 인터페이스 v1 + 사용 가이드 | kickoff +3주 | A4 schema (Week 1)에 의존 |
| A6 | **Catalog-Build Agent 검수 워크플로우 / UI 제공** — 데이터 팀이 D4에서 cm_id 네이밍 / 카테고리 / 노출 여부 결정을 빠르게 할 수 있도록 검수 UI(또는 CLI/Slack 봇) 제공 | 검수 인터페이스 v1 + 사용 가이드 | kickoff +4주 | 데이터 팀 의존 없음 — A6 자체가 D4의 hard blocker (선행 산출물) |
| A7 (신규) | **Operations Loop prototype 구현** — datalake update event 발행 → 저장된 catalog 코드 dependency resolution → 자동 재실행 → catalog refresh (LLM-free, ADR-13 패턴 재사용) | Operations Loop v0.1 + 통합 테스트 | kickoff +8주 | A2 / A3 prototype 의존 |
| A8 | **Showcase Phase 1 노출 인터페이스** — ARK-1328 Phase 1 "Featured by Quantit" 카탈로그가 web/SDK에서 보이도록 — `Catalog().browse(featured=True)` 같은 필터 + web 카드 (G16) | Showcase v1 (web + SDK) | kickoff +9주 | D6 Featured 카탈로그 리스트 (Week 8) |
| A9 | **data-sync 운영 모니터링 / 알림** — 기존 `data-sync` Argo CronWorkflow 실패 시 Slack 알림 + S3 로그 + Argo Archive RDS 진단 절차 문서화. v0.3 Operations Loop 운영에도 그대로 적용. (G9) | 운영 runbook + 알림 봇 | kickoff +4주 | 데이터 팀이 운영 알림을 어떤 채널/형식으로 받기 원하는지 답변 |
| A10 | **ARK-1315 성공 기준 / 마일스톤 확정 작성** — kickoff 합의 결과를 ARK-1315 description의 "TBD — 지표 or 마일스톤 (형님 확정)" 부분에 채워 넣음 (G5에 따른 ARK-1315 description 수정) | 업데이트된 ARK-1315 description + sub-task 분해 | kickoff +1주 | 본 RFC에서 양 팀 합의된 §5 + §6 매트릭스 |
| A11 | **데이터 팀 자산 datalake ingestion 비용 견적** — D7 입력으로 데이터 팀 자산(Iceberg / Compustat / Finter / RDS) 별 datalake 적재 비용(엔지니어 days + 인프라 비용) 견적 | 자산별 ingestion 견적표 | kickoff +3주 | 데이터 팀이 자산별 row count / volume / spec 정보 제공 |
| A12 (신규) ⚠ **CRITICAL PATH** | **AWS-free backend 결정 ADR** — Object storage / Secrets / Workflow / Compute / Datalake storage 5개 영역의 AWS-free 대안 선택 + 분기 메커니즘 정의 (G21~G25). §4.6.1 5개 후보 (MinIO / age+SOPS / systemd timer / docker / DuckDB)를 시작점으로 검증. **kickoff에서 PoC 의사결정자(아키텍트) 직접 결정 필수** — 이 결정 없이는 A2/A3/A7 prototype의 backend 선택 못 함. | "AWS-free backend ADR" 1건 + backend 추상화 layer 인터페이스 정의 | kickoff +2주 (hard deadline) | 데이터 팀 의존 없음 — AMT 내부 인프라 결정. 단 PoC 의사결정자(아키텍트) review 필요 |

---

## 7. 마일스톤 & 타임라인

### 7.1 절대 날짜 앵커

분기 말(2026-06-30, ARK-1315 / ARK-1328 due date) 기준 역산. **kickoff 미팅을 2026-04-30(목) 전후로 잡으면** Week 9 종료 = 2026-07-02로 분기 말과 거의 일치한다 (Week 10+ retro는 Q3 초). 더 늦어지면 §7.2의 핵심 마일스톤이 분기 말을 초과한다.

### 7.2 주차별 마일스톤

```
Week 0   ────  kickoff 미팅 (이 RFC 합의)                              목표 2026-04-30
Week 1   ────  A4 knowledge+catalog schema, A10 ARK-1315 description, ~2026-05-07
              D8 bundle metadata 형식 답변
Week 2   ────  D1 source-bundle 정의, D9 schema review,               ~2026-05-14
              A12 AWS-free backend ADR
Week 3   ────  D2 큐레이션 매트릭스, D7 자산 변환 우선순위,             ~2026-05-21
              A5 knowledge 입력 UI, A11 ingestion 견적
Week 4   ────  A6 catalog 검수 UI, A9 운영 runbook + 알림 봇          ~2026-05-28
Week 5   ────  D4 1차 검수 운영 시작                                  ~2026-06-04
Week 6   ────  A1 v0.2 안정화 리포트, A2 Datalake-Build Agent v0.1,   ~2026-06-11
              D3 knowledge ground truth, D5 메타데이터 N개 채움
Week 7   ────  A3 Catalog-Build Agent v0.1                            ~2026-06-18
Week 8   ────  A7 Operations Loop v0.1, D6 Featured 카탈로그 큐레이션  ~2026-06-25
Week 9   ────  A8 Showcase v1 (web + SDK)                             ~2026-07-02 (분기 말±)
Week 10+ ────  ARK-1315 / ARK-1328 Phase 1 close 판정, retro          Q3 초
```

> **kickoff 후 2주 / 4주 / 8주 시점에 짧은 sync 미팅** (15분, 양 팀 1명씩 attend) 권장. 주차별 산출물의 진행 상황 점검 + blocker 식별만.

### 7.3 위험 구간 (kickoff 미팅에서 별도 합의 필요)

- **A2 (Week 6) → A3 (Week 7) → A7 (Week 8) 직렬 의존**: Datalake-Build → Catalog-Build → Operations Loop가 1주 간격 직렬. 각 단계 1주 slip 시 분기 말 초과. kickoff에서 prototype 범위 축소 옵션 협의 권장 (예: A2/A3는 1 source-bundle 기준만, A7은 manual trigger도 OK로 정의).
- **A3 multi-turn dialog 구현 위험** (§8.2 Q7 미해결 시): A3의 사용자 대화 구현이 ADR-12 단일 사이클 N회 반복만으로 가능한지, 아니면 multi-round dialog 신규 구현이 필요한지가 Week 7 착수 전 확인 필요. 불명확 시 A3 범위를 "catalog 후보 제안 + 1회 사용자 선택"으로 제한하는 fallback 검토.
- **D6 (Week 8) → A8 (Week 9)** 1주 간격 (v0.2 위험 그대로 상속).
- **A1 안정화 리포트 (Week 6)** 는 D4 검수 운영(Week 5 시작) 데이터 1주분으로만 측정 — 표본 부족 위험.
- **A12 AWS-free backend ADR (Week 2)** 결정 늦어지면 A2/A3/A7 prototype의 backend 선택 영향. Week 2 hard deadline. §4.6.1 5개 후보가 거부되면 Week 2 안에 대체안 합의 필요.

---

## 8. 다음 액션 / Open Questions

### 8.1 kickoff 미팅에서 합의받아야 할 항목 (체크리스트)

- [ ] **§2.1 v0.3 4-stage 흐름 합의** — Source-Bundle / Team Datalake / Catalog-Build / Operations Loop 정의 양 팀 모두 confirm
- [ ] **§5 매트릭스 D1~D9** — 데이터 팀이 모두 owner 받을 수 있는지, 기한 조정 필요한지
- [ ] **§5.1 hard blocker ⓐ~ⓕ** — AMT 선행 산출물 6개 일정이 §7.2와 일치하는지 양 팀 모두 confirm
- [ ] **§6 매트릭스 A1~A12** — AMT가 모두 owner 받을 수 있는지, 기한 조정 필요한지
- [ ] **§7.1 kickoff 절대 날짜 confirm** — 2026-04-30 또는 다른 날짜로 확정 후 §7.2의 절대 날짜 줄을 갱신
- [ ] **§7.3 prototype 범위 축소 옵션** — A2/A3/A7 직렬 의존 위험 처리: 1 source-bundle 기준 / manual trigger 허용 등
- [ ] **§7 sync 미팅 cadence** — 2주 / 4주 / 8주 sync에 양 팀 누가 참여
- [ ] **§2.3 비목표 합의** — Phase 3 Open Marketplace, ARK-1329 Investment Universe 확장, AWS-free backend 정식 결정은 이번 분기 협업 범위 밖이라는 것 확인
- [ ] **ARK-1315 / ARK-1328 sub-task 분해 책임자** — A10 산출물(업데이트된 ARK-1315 description)을 누가 작성하고 누가 review할지
- [ ] **§8.2 Open Questions Q1~Q7 답변 책임자 / 기한**

### 8.2 Open Questions (kickoff에서 양 팀 + PoC 의사결정자가 함께 답해야 하는 질문)

> 일부 질문은 데이터 팀이 답하기 적합하고, 일부는 양 팀 공동 답변, 일부는 PoC 의사결정자(아키텍트/CTO)의 결정 필요. 미팅에서 질문별 책임자를 같이 정한다.

1. **AWS-free PoC backend 결정** (신규, 책임자: PoC 아키텍트 + AMT) — Object storage / Secrets / Workflow / Compute / Datalake storage 5개 영역 중 어떤 것을 AWS-free로 강제할지, 강제하면 어떤 backend를 prototype에 채택할지. backend 추상화 layer 인터페이스 정의 (A12 산출물).
2. **데이터 팀 ↔ AMT 팀 공식 멤버 정의** — `<!subteam^S04D8GC39F0>` (data) / `<!subteam^S089G4FCJRJ>` (amt)에 누가 속하는지 (출처: `.claude/rules/slack.md` 사용자 표가 두 팀을 같이 묶고 있어 명확화 필요).
3. **외부 데이터 spec 권리 관계** — FnGuide / Compustat 등의 spec 문서가 AMT 팀에게 노출 가능한지 (벤더 NDA 제약). AMT의 Datalake-Build Agent가 spec 본문을 prompt에 포함시켜도 되는지.
4. **데이터 자산 라이선스 / 재배포** — ARK-1328 Phase 2 Finter 파트너 연동 시 Finter 데이터를 외부 고객에게 재노출(re-distribute)하는 것이 상업 계약상 가능한지. 가능하지 않다면 Phase 2 정의 자체를 다시 그려야 함.
5. **BYOC 환경에서 고객별 카탈로그 격리** — 김일웅의 BYOC IP 보호 메모(2026-04-28)와 데이터 큐레이션을 결합하면 "고객 A에게는 노출 / 고객 B에게는 비노출" 같은 카탈로그 ACL이 필요한가. 필요하다면 어느 레이어가 강제하는가 (SDK / API / 인프라). v0.3 team datalake multi-tenancy 모델과 결합 검토 필요.
6. (신규) **Operations Loop의 SLA / 장애 대응** — datalake update event → catalog refresh의 지연 허용치 (분 단위 / 시간 단위 / 일 단위)? 자동 재실행 실패 시 사람 개입 임계점은? `data-sync` cron 모델보다 event-driven으로 바뀌면서 SLA 정의가 새로 필요.
   - **제안값 (kickoff 결정 입력)**: 기존 `data-sync` Argo CronWorkflow가 일별 실행(출처: `ARCHITECTURE.md:592`, ADR-13)이라는 점을 근거로 **PoC 초기 SLA = datalake update → catalog refresh 24h 이내**를 default로 제안. 자동 재실행 3회 연속 실패 시 Slack 알림(`<#C0A6BSMAG4D>`) + 24h 대기 후 사람 개입. kickoff에서 더 엄격한 기준 필요 시 조정 (예: critical catalog는 1h SLA).
7. (신규) **Catalog-Build Agent multi-turn dialog 구현 메커니즘** — A3 prototype 착수 전(Week 7) 결정 필요. ADR-12 waiting_input 단일 사이클을 N번 반복(3.1.5 가정)으로 구현 가능한가, 아니면 별도 SSE/streaming 메커니즘이 필요한가? 후자라면 A3 prototype 공수 재산정 필요.

### 8.3 미해결 / 다음 RFC로 넘기는 항목

- **Phase 3 Open Marketplace 모델** — ARK-1328 Phase 3. 데이터 팀이 답할 질문이 너무 많아 별도 RFC로.
- **Investment Universe 확대** (ARK-1329) — 새 유니버스가 추가될 때 데이터 팀이 universe 정의의 SSOT인지. 별도 에픽이라 이번 RFC 범위 밖.
- **AI Framework 탈피** (ARK-1322) — Claude Agent SDK 대신 Pydantic AI로 전환하는 흐름이 `arkraft-agent-extract`에서 시작되었는데, `arkraft-agent-data`도 같은 길을 갈지 결정. AMT 내부 결정이라 데이터 팀에 영향 없음. v0.3 신규 agent들(Datalake-Build / Catalog-Build)도 어느 framework로 갈지 별도 ADR.
- **AWS-free backend 정식 운영 결정** — §8.2 Q1은 PoC prototype에 한정. 정식 운영(production)에서 AWS-free 유지할지는 비즈니스 / 비용 / 규모 분석 따로 필요.

---

## 부록 A. 출처 표기 규약

본 문서의 모든 단정문은 다음 형식 중 하나의 출처를 가진다:

- `(출처: <repo-relative-path>:<line>)` — 메타-레포 또는 서브모듈 파일
- `(출처: ARK-XXXX description)` — Jira 이슈 description
- `(출처: Slack <#CXXXXXXXX> YYYY-MM-DD <speaker>)` — Slack 메시지 (channel ID는 `.claude/rules/slack.md` 참조)
- `(출처: 사용자 vision)` — 본 ralph loop의 prompt.md "사용자 새 vision" 섹션 인용

추측 / 창작 / 일반론은 §8.2 Open Questions로 분리. 출처 없는 단정문은 없어야 한다.

## 부록 B. 컨텍스트 노트

본 RFC 작성에 사용된 1차 자료 정리는 다음 두 파일 참조 (gitignore 대상):
- `.ralph/data-team-engagement-rfc/_CONTEXT_NOTES.md` (v0.2 1차 자료)
- `.ralph/data-pipeline-rfc-v0.3/_CONTEXT_NOTES_v0.3.md` (v0.3 추가 컨텍스트, 사용자 vision 매핑, 기존 컴포넌트 → v0.3 매핑 표)
