---
name: user-simulation-validator
description: After completing any feature or project, automatically assume the primary user persona (extracted from PRD or inferred from code context), simulate realistic usage scenarios, evaluate against professional "worth paying for" standards, and iterate until all criteria pass. Use this skill when any feature is complete, before declaring "done", or when asked to validate/test/verify a program. All output must be written in Korean.
---

All validation reports, gap analyses, scenario logs, and final outputs must be written in Korean regardless of the language used in code or project files.

## When to Activate

Run this skill automatically when:
- A feature or module is fully implemented
- About to declare "완료" / "done" / "작업 완료"
- User requests "검증" / "테스트" / "확인" / "validate"
- Project reaches first runnable state

## Step 1 — Persona Extraction

**If PRD.md exists:** Read the target customer section and extract the primary user.

**If no PRD.md:** Infer from file structure, README, domain language in code, and route names.

Extract and output in Korean:
```
[페르소나 확정]
역할/직책:
업종 및 규모:
기술 수준: 비개발자 | 일반 사용자 | 전문가
핵심 목적: (이 소프트웨어로 오늘 해결해야 할 일)
시간 제약: (설명서 없이 N분 안에 핵심 기능 사용 가능해야 함)
```

Persona inference table (use when no PRD):

| Code Signal | Inferred Persona |
|---|---|
| dashboard, analytics, stats | Operations team, data-driven decisions, trust is critical |
| invoice, payment, billing | Finance role, accuracy first, audit trail needed |
| admin, settings, users | Internal power user, efficiency over aesthetics |
| login, signup, onboarding | General public, zero learning curve expected |
| api, webhook, sdk | Developer audience, documentation matters |
| brand, threat, monitor | Security/PR role, speed and clarity under pressure |

## Step 2 — Scenario Design

Design minimum 5 scenarios based on the persona. Output in Korean.

Required scenario types:
- **S1 First run / onboarding** — most critical
- **S2-S3 Core daily workflow** — what they do every session
- **S4 Error / edge case** — no data, API failure, wrong input
- **S5 Output utilization** — report, share, hand off to someone else

Scenario format (output in Korean):
```
[시나리오 N] 제목
상황: 페르소나가 처한 구체적 상황
목표: 이 시나리오에서 달성해야 할 것
실행 단계:
  1. ...
  2. ...
기대 결과: 성공 시 어떤 화면/응답이 나와야 하는가
```

## Step 3 — Scenario Execution

Trace each scenario at code level: follow the API calls, render logic, and data flow as the persona would experience it. Output in Korean.

```
[시나리오 N 실행 로그]
실행한 행동:
실제 발생한 일:
페르소나 반응: 이해함 | 혼란 | 막힘 | 불신
결과: PASS | FAIL | PARTIAL
FAIL 이유:
```

## Step 4 — Quality Gate Evaluation

Evaluate all 7 criteria using scenario results. Output in Korean.

| # | 기준 | 설명 | 비중 |
|---|---|---|---|
| 1 | 즉시 이해 가능성 | 설명서 없이 첫 화면에서 다음 행동을 알 수 있는가 | 높음 |
| 2 | 핵심 기능 도달 속도 | 가장 중요한 기능까지 3클릭 이내 도달 가능한가 | 높음 |
| 3 | 데이터 신뢰성 | 표시 내용이 실제 의사결정에 쓸 수 있는 수준인가 | 높음 |
| 4 | 에러 내성 | API 실패·데이터 없음 상황에서도 우아하게 동작하는가 | 중간 |
| 5 | 피드백 명확성 | 저장·실패·로딩 상태가 명확히 구분되는가 | 중간 |
| 6 | 결과물 활용성 | 산출물을 바로 보고·공유·후속 액션에 쓸 수 있는가 | 중간 |
| 7 | 전문가 기준 충족 | 이 분야 전문가가 봤을 때 돈 내고 쓸 수 있는 수준인가 | 높음 |

Output format:
```
[품질 기준 평가표]
1. 즉시 이해 가능성: PASS | FAIL | PARTIAL — 판단 근거
2. 핵심 기능 도달 속도: ...
...
7. 전문가 기준 충족: ...

전체 판정: PASS | FAIL
```

**Only declare completion when all 7 criteria are PASS.**

### Pass / Fail Reference

**PASS conditions:**
- User can identify their next action within 10 seconds of first screen
- Core feature reachable in 3 clicks or fewer from any state
- Error messages guide the user toward a fix, not just report a failure
- Empty state tells the user what to do next
- Loading / saving / error states are visually distinct
- Output (report, data, result) is usable externally without modification

**FAIL conditions:**
- First screen causes "I don't know what to do" reaction
- App crashes or shows raw error codes when API key is missing
- Core feature requires 4+ clicks or prior knowledge
- Mock data is too abstract to simulate real decisions
- No visual feedback after user actions (save, delete, update)

## Step 5 — Gap Analysis and Fix

For every FAIL or PARTIAL, immediately perform and output in Korean:

```
[갭 분석]

🔴 심각 (즉시 수정):
1. 문제:
   원인: (파일명, 함수명 등 정확한 위치)
   수정:

🟡 보통 (이번 세션 내):
2. ...

⚪ 경미 (다음 세션):
3. ...
```

After fixing, re-run Step 3 for affected scenarios only.
Repeat Steps 3-5 until all criteria pass.

Loop limit: If FAIL persists after 3 iterations, document reason and escalate to user. Log in UNSEEN_CHANGES.md.

## Step 6 — Final Validation Report

Output entirely in Korean when all criteria pass:

```
========================================
  자가 검증 완료 리포트
========================================
검증 일시:
페르소나: [직책] [이름(가명)]
총 시나리오: N개 전체 PASS
품질 기준: 7/7 PASS
반복 횟수: N회

이번 검증에서 수정된 항목:
- 항목 요약

현장 투입 판정: ✅ 즉시 사용 가능
========================================
```

## Output Language Rule

All output must be in Korean. This includes:
- Persona descriptions
- Scenario narratives
- Execution logs
- Gap analysis
- Quality evaluations
- Final report

Code, file names, and technical identifiers remain in English.
