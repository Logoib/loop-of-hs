# Loop skill family TODO

`loop-code`에서 실제 공통점이 확인되기 전에는 별도 `loop-core` abstraction을 만들지
않는다. 새 framework 기능이나 후속 skill보다 실제 UAT를 먼저 수행한다.

## P0 — 실제 변경 UAT

1. 대규모 Vue cross-component 변경 1건
2. NX 또는 Flomaster 변경 1건
3. 필요하면 두 번째 CAE 변경 1건

각 run에서 사용된 gate, ceremony 시간, 발견한 오류, stale-input 발생, 재작업 감소,
쓰이지 않은 ledger field를 기록한다. 쓰이지 않은 field/state는 제거하고, 반복된
실패를 막는 최소 장치만 추가한다. Controller self-test는 UAT로 세지 않는다.

## P1 — `loop-search`

목적: 로컬 자료, KG, 공식 web source를 함께 사용하는 고품질 조사·검색 loop.

필수 계약:

- 질문, 의사결정 목적, freshness 기준, 허용 source 범위
- KK/KU/UK/UU와 query branch ledger
- local/KG lookup은 `kg-lookup`, 최신성이 필요하면 공식 primary source 검색
- claim-evidence matrix, contradiction과 source date/version
- 반증 query와 coverage gap
- stop: critical claim에 근거가 있고, 중대한 contradiction이 해소됐으며, 새 query가
  decision-changing evidence를 만들지 못할 때
- 사용자가 요청하면 결과를 `kg-ingest`; 단순 lookup과 ingest를 자동 혼동하지 않음

산출물은 polished report가 아니라 재사용 가능한 evidence bundle과 claim map이다.

## P2 — `loop-report`

목적: 검증된 source bundle을 보고서, HTML, PDF, 또는 slide deck으로 변환.

필수 계약:

- audience, decision, message, format, 분량, deadline
- source-to-claim traceability와 인용 policy
- outline gate → draft → factual review → narrative/visual review → export QA
- 표·차트 숫자 재검산, 링크와 인용 확인
- slide 요청이면 `slides-grab` workflow 사용
- evidence gap이 발견되면 추측하지 않고 `loop-search`로 되돌림
- stop: 모든 핵심 claim이 source에 연결되고, audience acceptance와 export QA가 통과

`loop-report`가 검색까지 다시 수행하지 않도록 두 skill의 경계를 유지한다.

## P3 — 조건부 `loop-cae`

NX/Flomaster 실사용 2–3건에서 다음 계약이 반복될 때만 만든다.

- application/API/version probe
- source model backup과 working copy
- units/coordinate/material validation
- run/solve/export evidence
- rollback과 원본 보존

그 전에는 `loop-code`의 단일 경로에 rollback과 필요한 acceptance를 추가해 처리한다.

## 보류

- `loop-debug`: 별도 skill 대신 `loop-code`의 unknown/probe flow 사용
- `loop-review`: 독립 review는 각 domain loop 내부 capability로 유지
- `loop-plan`: Direct/Plan/Loop triage와 중복
- `loop-core`: 세 개 이상의 실제 skill에서 안정된 공통 schema가 확인될 때만 추출
- `loop-ops`/`loop-release`: 반복되는 CI/CD·production coordination 수요가 생길 때 검토

## 권장 구현 순서

- [x] `loop-code` controller 최소 구현
- [ ] Vue real-task UAT 1건
- [ ] NX/Flomaster real-task UAT 1–2건
- [ ] `loop-search`
- [ ] `loop-report`
- [ ] 필요가 확인되면 `loop-cae`
