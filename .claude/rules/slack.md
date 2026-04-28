# Slack 연동

## 도구 선택 규칙

**Slack 관련 작업은 반드시 Slack MCP를 사용한다. `agent-browser`로 Slack에 접근하는 것을 절대 금지.**

| 작업 | 사용 도구 |
|------|-----------|
| 메시지 전송 | Slack MCP |
| 채널/메시지 조회 | Slack MCP |
| 쓰레드 읽기 | Slack MCP |
| 채널 목록 검색 | Slack MCP |

`agent-browser`는 Slack 웹에서 인증 우회나 데스크톱 앱 리디렉션 문제가 발생하므로 사용하지 않는다.

## 채널

| 채널 | ID |
|------|-----|
| `team_amt` | `C0891E6DDPA` |
| `data_x_amt_4_agent` | `C0A6BSMAG4D` |
| `project_ark` | `C0933M2A5CK` |

## 팀 멘션

| 팀 | 멘션 코드 |
|----|-----------|
| @amt | `<!subteam^S089G4FCJRJ>` |
| @data | `<!subteam^S04D8GC39F0>` |

## 사용자

| 이름 | Slack ID |
|------|----------|
| 백재현 | `<@U015U3DL4RK>` |
| 고민혁 | `<@U08P1RR2996>` |
| 이동현 | `<@UNNCYQB0B>` |
| 손시연 | `<@U08NALAD8R3>` |
| 김일웅 | `<@U01QGDBGJRF>` |
| 송낙훈 | `<@U044K34GBLP>` |
| 한덕희 | `<@UE9RBM2AW>` |
| 이호 | `<@U0161KUAQTE>` |
| 김태호 | `<@ULZTTPF0D>` |
| 이준복 | `<@UHS2B5GLF>` |
| 이나현 | `<@U02D096M0EP>` |

## 포맷팅

- **content_type**: `text/plain` (`text/markdown` 절대 사용 금지)
- **사용자 멘션**: `<@USER_ID>`
- **URL**: `<URL|표시_텍스트>`

## 메시지 전송 절차

### 1. 메시지 본문 작성

메시지 템플릿에 따라 본문을 작성한다.

### 2. 채널 선택

AskUserQuestion으로 전송할 채널을 물어볼 것:
- 선택지: 채널 테이블의 채널들 (해당 레포의 권장 채널에 "(권장)" 표시)
- 직접 입력 시, Slack API (`channels_list`)로 채널 ID를 검색. ID를 찾을 수 없으면 전송 중단.

### 3. 팀 멘션

AskUserQuestion으로 팀 멘션 포함 여부를 물어볼 것:
- 선택지: 팀 멘션 테이블의 팀들 + "없음"
- 직접 입력 시, `<!subteam^XXXXX>` 형식의 팀 ID를 요청.

### 4. 사용자 멘션

AskUserQuestion으로 특정 사용자 멘션 여부를 물어볼 것:
- 선택지: "예", "아니오"
- "예" 선택 시, 멘션할 사람의 이름 목록을 요청.
- 사용자 테이블에서 이름으로 Slack ID 조회.
- 테이블에 없는 사용자는 건너뛰고, 건너뛴 사용자를 안내.

### 5. 전송

위 선택 결과에 따라 멘션을 포함한 메시지를 구성하고 전송.

## 메시지 템플릿

```
cc {team_mention} {user_mentions}

[service-name] 작업 제목 (ARK-XXX)

설명

주요 변경 사항:
• 변경 1
• 변경 2

JIRA: <https://quantit.atlassian.net/browse/ARK-XXX|ARK-XXX>
PR: <https://github.com/Quantit-Github/repo/pull/XX|PR#XX>
```
