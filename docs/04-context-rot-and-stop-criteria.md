# Long-context degradation and operational stop criteria

> **문서 역할:** context 연구 근거와 운영 원칙을 분리한다. 아래 연구 근거는
> 유지하되, v0.4는 보편 임계값을 주장하지 않는다. 150K는 사용자가 선택한
> Codex soft cap으로만 취급한다.

> 작성 기준일: 2026-07-21 (Asia/Seoul)
> 범위: 장문 컨텍스트 성능 저하의 근거, loop의 refresh/fork/stop 기준, ledger 기반 working-set 설계
> 표기: **사실**은 외부 근거가 직접 지지하는 내용, **설계 추론**은 그 근거를 이 프로젝트의 운영 규칙으로 변환한 제안이다.

## 1. 결론

**사실:** 공개 연구는 모든 모델이 정확히 200K에서 급격히 무너진다는 보편 임계값을 입증하지 않는다. 대신 다음 세 현상을 일관되게 보여준다.

1. 모델이 입력을 받을 수 있는 `advertised context window`와 그 입력을 안정적으로 사용하는 `effective context length`는 다르다. RULER에서 200K를 주장한 Yi-34B의 effective length는 해당 연구의 기준상 32K였고, 4K/32K/64K/128K 점수는 93.3/87.5/83.2/77.3이었다. [RULER 공식 저장소](https://github.com/NVIDIA/RULER) — 확인 2026-07-21.
2. 저하는 단일한 절벽보다 길이·위치·과제 복잡도·distractor에 따른 gradient인 경우가 많다. 관련 정보가 중간에 있을 때 성능이 떨어지는 `lost in the middle`, literal match가 없을 때 32K 이전부터 나타나는 저하, 완전한 검색을 보장해도 입력 길이만으로 생기는 저하가 각각 관찰됐다. [Lost in the Middle, TACL 2024](https://aclanthology.org/2024.tacl-1.9/), [NoLiMa, ICML 2025](https://arxiv.org/abs/2502.05167), [Du et al., Findings of EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.1264/) — 모두 확인 2026-07-21.
3. 단순 needle retrieval 성공은 코드 변경, 다중 문서 추론, 장기 agent 작업의 신뢰성을 보증하지 않는다. HELMET은 NIAH 점수와 실제 응용 성능의 예측력이 낮고 과제 범주 간 상관도 낮다고 보고했다. [HELMET](https://arxiv.org/abs/2410.02694) — 확인 2026-07-21.

**사실:** 현재 사용 후보의 API 최대치는 이미 200K보다 크다. GPT-5.6 Sol은 1,050,000-token window, Claude Fable 5는 1M-token window로 문서화되어 있다. 이는 수용 가능한 입력 용량이며, 프로젝트별 effective length를 뜻하지 않는다. [OpenAI GPT-5.6 Sol model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [Claude context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows) — 확인 2026-07-21.

**로컬 사실:** ChatGPT 로그인 + Codex CLI `0.144.6`의 2026-07-21
`models_cache.json`은 Sol/Terra/Luna의 `context_window`와
`max_context_window`를 272,000, `effective_context_window_percent`를 95로
기록한다. 최근 session log의 budget은 `258400 = 272000 × 0.95`다. 전역
`model_context_window=1050000`을 넣어도 이 값은 늘지 않았다. OpenAI의 해당
release PR도 세 모델에 272,000을 유지한다고 명시한다.
[Codex PR #34009](https://github.com/openai/codex/pull/34009) — 확인 2026-07-21.

**설계 추론:** 이 loop는 큰 window를 작업 메모리로 가득 채우지 않는다. **파일 시스템의 ledger/checkpoint를 durable memory로, 매 세션의 context를 짧고 교체 가능한 cache로** 취급한다. 논리적 hub는 지속되지만 hub의 채팅 세션 자체는 영구적이지 않다. 실행·premortem·review는 각각 fresh context에서 수행하고, transcript 대신 검증된 task capsule만 넘긴다.

## 2. 근거 지도

| 근거 | 직접 관찰 | 이 설계에 주는 의미 | 한계 |
|---|---|---|---|
| [Lost in the Middle, TACL 2024](https://aclanthology.org/2024.tacl-1.9/) — 확인 2026-07-21 | 관련 정보가 입력의 시작/끝에 있을 때보다 중간에 있을 때 성능이 낮아지는 U-shaped 경향 | 핵심 계약을 긴 transcript 중간에 묻지 말고 task capsule로 재구성 | 당시 모델과 QA/retrieval 중심 |
| [RULER, COLM 2024](https://openreview.net/forum?id=kIoBbc76Sy) 및 [공식 결과표](https://github.com/NVIDIA/RULER) — 확인 2026-07-21 | vanilla NIAH는 거의 완벽해도 multi-needle, tracing, aggregation은 길이에 따라 하락. 주장 길이 32K 이상인 당시 모델 중 절반만 32K에서 연구 기준을 충족 | vendor maximum 대신 모델·과제별 effective length를 측정 | synthetic benchmark이고 연구의 effective threshold는 저자 정의 |
| [∞Bench, ACL 2024](https://aclanthology.org/2024.acl-long.814/) — 확인 2026-07-21 | 평균 100K+ 입력의 영어/중국어 retrieval·QA·code·math 등에서 당시 long-context 모델에 큰 개선 여지가 존재 | 100K+ 입력 가능 여부를 실제 long-dependency 이해와 혼동하지 않음 | 최신 모델에 그대로 외삽할 수 없음 |
| [HELMET](https://arxiv.org/abs/2410.02694) — 확인 2026-07-21 | 51개 모델, 7개 응용 범주, 최대 128K 평가에서 NIAH가 downstream performance의 좋은 예측기가 아니며 길이가 늘수록 full-context reasoning 격차가 확대 | loop 자체의 실제 산출물·테스트로 local eval 구성 | 범주별 metric과 평가 모델의 영향을 받음 |
| [NoLiMa, ICML 2025](https://arxiv.org/abs/2502.05167) — 확인 2026-07-21 | 최소 lexical overlap을 요구한 12개 128K+ 지원 모델 중 10개가 32K에서 강한 short baseline의 50% 아래. GPT-4o도 99.3%에서 69.7%로 하락 | grep 가능한 literal cue만 잘 찾는 평가로 context health를 판단하지 않음 | controlled associative retrieval이며 일반 코딩 성공률 자체는 아님 |
| [Context Length Alone Hurts LLM Performance Despite Perfect Retrieval, Findings of EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.1264/) — 확인 2026-07-21 | 5개 모델의 math·QA·coding에서 관련 근거를 완전히 검색해 줘도 길이에 따라 13.9%~85% 저하. 답변 전 근거 recitation으로 RULER의 GPT-4o가 최대 4% 개선 | retrieval 후 바로 답하지 말고 선택한 근거를 짧게 materialize한 뒤 실행 | 모델/과제별 하락 폭이 달라 하나의 임계값을 제공하지 않음 |
| [Chroma Context Rot technical report](https://www.trychroma.com/research/context-rot) 및 [재현 코드](https://github.com/chroma-core/context-rot) — 확인 2026-07-21 | 18개 모델에서 길이가 늘 때 semantic needle, LongMemEval, repeated-word 과제의 신뢰성이 비균일하게 저하 | 길이뿐 아니라 context 구성·semantic ambiguity·history를 health signal로 사용 | peer-reviewed 논문이 아닌 기업 기술 보고서이고, Chroma는 retrieval 제품 이해관계가 있음 |
| [OpenAI GPT-5.6 long-context 공식 결과](https://openai.com/index/gpt-5-6/) — 확인 2026-07-21 | MRCR v2 8-needle에서 Sol/Terra는 256K–512K 91.5/89.6%, 512K–1M 73.8/72.5% | 큰 API window도 품질 보증이 아니며 coding session soft cap은 별도 운영값 | vendor retrieval eval이며 150K coding cliff를 입증하지 않음 |
| [Anthropic: Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — 확인 2026-07-21 | Anthropic은 hard cliff보다 performance gradient를 설명하고, smallest high-signal token set, compaction, structured notes, multi-agent architecture를 권고 | ledger + JIT retrieval + fresh spoke 구조를 지지하는 공식 실무 근거 | 통제 실험 논문이 아니라 vendor engineering guidance |
| [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — 확인 2026-07-21 | compaction만으로는 부족했고, feature list, progress file, git history, one-feature-at-a-time, end-to-end test를 사용한 fresh-session handoff가 효과적이었다고 보고 | checkpoint가 transcript summary가 아니라 검증 가능한 상태·progress·tests를 가져야 함 | 하나의 실험적 harness 사례이며 범용 최적해 증명은 아님 |

### 2.1 해외 포럼은 보조 증거로만 사용

**보조 관찰:** Chroma 보고서의 Hacker News 토론(260 points, 59 comments)에는 긴 세션/반복 compaction 뒤 품질 저하, 필요한 파일만 다시 읽힌 fresh context의 개선, `explore → plan → code → test → commit` 사이 context clear가 유용했다는 실무 경험이 반복된다. 동시에 Chroma가 retrieval 제품 공급자라는 이해관계를 지적하고, compaction에 의한 정보 손실과 순수한 context-length degradation을 구분해야 한다는 반론도 있다. 이는 경험담이며 임계값의 근거로 사용하지 않는다. [Hacker News discussion](https://news.ycombinator.com/item?id=44564248) — 확인 2026-07-21.

**보조 분류:** Simon Willison이 소개한 Drew Breunig의 practitioner taxonomy는 context poisoning(오류의 재사용), distraction(긴 history에 대한 과집중), confusion(불필요한 정보 사용), clash(상충 정보 누적)를 구분한다. 운영상 유용한 진단 어휘지만 peer-reviewed causal taxonomy는 아니다. [Simon Willison, “How to Fix Your Context”](https://simonwillison.net/2025/Jun/29/how-to-fix-your-context/) — 확인 2026-07-21.

## 3. 200K에 대한 올바른 해석

**사실:** 확인한 근거에는 모든 frontier model에 공통인 200K cliff가 없다. Anthropic도 long-context 성능을 hard cliff가 아닌 gradient로 표현한다. [Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — 확인 2026-07-21.

**설계 추론:** 다음 다섯 값을 섞지 않는다.

- `W_api_max`: vendor API maximum. Sol은 현재 1,050,000.
- `W_client_catalog`: 현재 client가 허용하는 maximum. Codex 0.144.6 snapshot은 272,000.
- `W_session_budget`: runtime이 session에 보고한 budget. 현재 snapshot은 258,400.
- `W_working_soft`: 운영자가 checkpoint/compaction을 원하는 soft cap.
- `W_quality_effective(task, model)`: 실제 project task에서 품질 기준을 만족하는 최대 길이. 아직 미측정.

따라서 “200K가 남았으니 계속”은 금지한다. token count는 refresh의 한 신호일 뿐이며, 상충 결정·잘못된 계약 회상·같은 탐색 반복과 같은 행동 신호가 더 이르면 즉시 refresh한다.

## 4. Calibration 없는 기본 운영과 150K profile

v0.1의 6–10개 gold slice, 8K–256K bucket, 0.5/0.7/0.85 비율,
16K/24K/32K 기본값은 실행 가능성이 낮은 미보정 정밀도였다. v0.4의 기본
운영에서는 모두 제거한다.

다음 행동 신호만 사용한다.

- phase가 바뀌면 atomic checkpoint 뒤 fresh context로 이동한다.
- compaction이 발생하면 summary를 정본으로 믿지 않고 ledger에서 재구성한다.
- 같은 탐색 반복, 폐기한 결정 재사용, contract 모순, stale input, tool output
  과점유가 나타나면 즉시 refresh한다.
- 아무 신호가 없으면 vendor window의 특정 비율만으로 refresh하지 않는다.

실제 반복 사용 중 길이 때문에 발생한 것으로 재현되는 실패가 쌓인 경우에만
별도 eval을 만든다. 이는 v0.4 사용의 전제조건이 아니다.

이 사용자의 Codex profile은 `model_auto_compact_token_limit=150000`, scope
`total`을 사용한다. 이는 258,400 session budget의 약 58%이며 “150K부터 모델이
망가진다”는 주장이 아니라 품질 우선 checkpoint 정책이다. 자동 compaction 뒤에는
summary를 정본으로 승격하지 않고 ledger에서 재구성한다. 해당 key는 공식 config가
지원한다. [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
— 확인 2026-07-21.

## 5. Ledger-based context architecture

### 5.1 Durable state와 disposable context

```text
Durable hub state (disk / git)
├─ contract: goal, scope, acceptance, authority boundaries
├─ ledger index: compact IDs and current statuses
├─ evidence records: source pointers, hashes, verification
├─ decisions: accepted/rejected alternatives and rationale
└─ checkpoints: last verified state and next action

Fresh spoke context (replaceable)
├─ contract fingerprint + current slice
├─ only relevant ledger records
├─ only relevant source/file excerpts
├─ current acceptance checks
└─ one explicit question or action
```

**설계 추론:** full transcript, 전체 repo dump, 오래된 tool output, 모든 ledger record를 새 세션에 넣지 않는다. spoke는 결과로 `ledger delta + artifact delta + verification evidence + next unknown`만 반환한다. coordinator도 매 phase 또는 hard-refresh 시 checkpoint에서 다시 생성할 수 있어야 한다.

### 5.2 Ledger record

```yaml
id: KU-012
class: KK | KU | UK | UU
statement: "The unresolved question or verified claim"
status: open | probing | verified | falsified | accepted-risk
impact: critical | high | normal | low
evidence:
  - source: "path, URL, commit, test, or user decision"
    fingerprint: "sha256 or immutable revision"
    verified_at: "2026-07-21T00:00:00+09:00"
owner: "coordinator or spoke ID"
next_probe: "Smallest action that can change this record"
blocks: ["decision-or-acceptance-id"]
```

- `KK / known-known`: 증거로 검증된 계약·사실. confidence만으로 KK가 되지 않는다.
- `KU / known-unknown`: 답이 다음 결정에 영향을 주는 명시적 질문. loop 한 회차는 가능하면 KU 하나를 닫는다.
- `UK / unknown-known`: repo, git history, tests, 사용자에게 이미 있으나 아직 surface되지 않은 지식. inventory/search/interview로 KU로 승격하거나 KK로 검증한다.
- `UU / unknown-unknown`: 내용을 안다고 주장할 수 없다. premortem의 blind-spot hypothesis, 누락 가능 영역, falsification probe만 기록하고 발견 즉시 KU/KK로 재분류한다.

**설계 추론:** giant append-only Markdown을 매번 읽지 않는다. active index는 ID·status·impact만 유지하고 상세 evidence는 ID별 record에서 JIT로 가져온다. source fingerprint는 오래된 file excerpt나 web claim을 조용히 재사용하는 것을 막는다.

### 5.3 Checkpoint capsule

각 fresh session은 raw summary가 아니라 아래의 최소 capsule로 시작한다. 필요한 evidence만 별도 로드한다.

```yaml
goal:
current_slice:
in_scope:
out_of_scope:
acceptance:
verified_facts: []
decisions: []
open_critical_unknowns: []
changed_artifacts: []
verification: []
failed_attempts: []
next_action:
source_fingerprints: []
```

Checkpoint를 만들기 전에는 atomic state를 만든다: 변경을 검증하거나 되돌리고, half-applied edit를 남기지 않으며, 실패한 시도와 test output을 ledger에 연결한다. Anthropic의 long-running harness도 incremental progress, progress file, git history, clean state, end-to-end testing을 핵심으로 보고했다. [Anthropic long-running harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — 확인 2026-07-21.

### 5.4 Context 배치와 evidence recitation

**설계 추론:** invariant contract를 앞에, current acceptance/question을 끝에 둔다. 중간에는 선택된 evidence만 두고, 실행 직전 모델이 사용할 evidence IDs와 핵심 사실을 짧게 다시 materialize하게 한다. 이는 beginning/end가 유리했던 positional 관찰과, answer 전 retrieved evidence recitation이 성능을 개선한 연구를 이용하되 중복 transcript를 만들지 않는 절충이다. [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/), [Du et al.](https://aclanthology.org/2025.findings-emnlp.1264/) — 확인 2026-07-21.

## 6. Refresh, fork, clean review 기준

### 6.1 언제 refresh하는가

다음 중 하나면 현재 atomic step을 정리한 뒤 fresh context로 재시작한다.

- 자동 compaction이 한 번 발생. compaction 결과는 참고 자료이며 canonical state가 아니다.
- research → plan → execute → review처럼 phase가 바뀜.
- 같은 파일/검색/명령을 이유 없이 다시 찾음.
- 이미 폐기한 결정이나 stale fingerprint를 다시 사용함.
- acceptance criterion을 잘못 회상하거나 서로 다른 두 결정을 동시에 참으로 취급함.
- tool output이 task capsule보다 커져 active context의 대부분을 차지함.
- 사용자가 목표·scope·권한을 실질적으로 변경함.

위 신호가 나타나면 새 일을 시작하지 않고 checkpoint부터 쓴다.

### 6.2 언제 fork하는가

Fork는 canonical state를 그대로 둔 채 별도의 fresh session이 독립 가설을 시험할 때 사용한다.

- irreversible/high-impact 결정에 critical KU가 남음.
- 두 개 이상의 plausible root cause가 있고 한 경로의 탐색이 다른 경로를 anchoring할 수 있음.
- premortem: 실행 transcript 없이 contract, ledger snapshot, plan만 제공.
- adversarial review: 작성자의 reasoning transcript 없이 contract, diff/artifact, test evidence만 제공.
- 한 bounded round가 measurable delta 없이 끝나 다른 접근이 필요함.

Reviewer는 종합 “87점” 같은 근거 없는 점수를 내지 않는다. 각 finding을 `blocking/non-blocking`, 위반한 acceptance ID, 재현 evidence, 최소 remediation으로 기록한다. 정반합은 coordinator가 finding별로 `accept / reject-with-evidence / convert-to-KU`를 판정한다.

## 7. 실제로 판정 가능한 loop stop conditions

### 7.1 상태 변수

| 변수 | 측정 방법 |
|---|---|
| `A_fail` | evidence가 연결되지 않았거나 실패한 acceptance criteria 수 |
| `KU_critical` | `impact: critical`, `status != verified/accepted-risk`인 KU 수 |

### 7.2 판정표

| 결과 | 판정 조건 | 조치 |
|---|---|---|
| `STOP_SUCCESS` | `A_fail=0 AND KU_critical=0` | 최종 checkpoint와 한국어 완료 보고 |
| `CONTINUE` | 미완료 acceptance 또는 critical KU가 있고 안전한 다음 probe가 있음 | 다음 KU 또는 acceptance 하나만 선택 |
| `STOP_BUDGET` | 명시한 iteration/deadline/budget 상한 도달 | 부분 성과와 재개 capsule 보존. scope 축소는 사용자 결정 |
| `STOP_SAFETY` | 권한 밖 변경, 데이터 손실, 보안/법적 위험이 감지됨 | 즉시 실행 중단, recoverable state 보존, 승인 요청 |
| `STALE_INPUT` | contract/verifier/artifact가 recorded evidence와 불일치 | 재검증 전 수정·완료 금지 |

상한은 사용자가 허용한 iteration 또는 deadline으로 명시한다. 반복 횟수나 token
비율을 보편 상수로 두지 않는다.

### 7.3 판정 순서

```text
if safety_or_authority_violation: STOP_SAFETY
elif recorded_evidence_is_stale:  STALE_INPUT
elif success_gates_all_pass:      STOP_SUCCESS
elif budget_cannot_fund_next:     STOP_BUDGET
else:                             CONTINUE
```

이 순서는 “끝날 때까지 계속”을 완료 기준으로 사용하지 않는다. 완료는 acceptance evidence가 결정하고, 반복은 새 evidence를 만들 수 있을 때만 정당화된다.
Refresh, recovery, uncertainty는 현재 machine enum이 아니다. 원인을 handoff에 남기고,
unsafe하면 `authority.blocked=true`로 안전 정지한다.

## 8. 한국어 실시간 monitoring report

Ledger와 capsule의 parser용 key/enum은 영어로 유지하되 free text 언어는 사용자 선호에 따른다. 매 loop 종료 시 coordinator가 아래 보고를 ledger에서 파생해 한국어로 보여준다. 한국어 보고 자체를 별도 truth source로 다시 입력하지 않는다.

```markdown
## Loop 07 — 실행 / CONTINUE

- 완료: AC-03 통과, KU-012를 verified로 전환
- 변경: src/x.py, tests/test_x.py
- 검증: test command와 결과, reviewer finding 0건
- 새 근거: EV-031 (source fingerprint 포함)
- 남은 불확실성: critical 0, high 2, normal 3
- 컨텍스트 건강: phase stable, compaction/반복/모순 없음
- 비용/시간: 사용량 / 잔여량 / 다음 loop 예상량
- 다음 한 단계: KU-014를 재현 테스트로 falsify
- 중단 상태: success gate 3/5, blocking reason AC-05
```

보고는 “진행률 73%” 같은 근거 없는 단일 수치를 쓰지 않는다. 대신 acceptance passed/total, open KU by impact, blocking findings, context band를 그대로 노출한다.

## 9. Loop 설계에 채택할 규칙

1. **Window capacity is not working memory.** 큰 context는 비상 용량이지 채우기 목표가 아니다.
2. **Fresh only on a signal.** phase, compaction/soft cap, 오염 또는 독립 검증이 필요할 때 context를 교체한다.
3. **Ledger is canonical; scratchpad is disposable.** scratchpad의 미검증 주장은 KK로 승격하지 않는다.
4. **Retrieve, materialize, act.** 관련 evidence만 JIT로 가져와 ID와 핵심 사실을 재진술한 뒤 행동한다.
5. **Checkpoint before compaction.** model-generated summary만으로 handoff하지 않는다.
6. **Risk-triggered clean review.** 위험한 plan/artifact만 작성 reasoning과 분리해 검토한다.
7. **Binary gates over decorative scores.** 완료·품질·불확실성은 evidence가 있는 gate로 판정한다.
8. **Stagnation is a stop signal.** 같은 실패를 더 오래 반복하는 것은 persistence가 아니다.
9. **Calibrate only after a reproduced need.** 모델별 length eval을 v0.4 선행조건으로 만들지 않는다.
10. **Korean visibility, portable schema.** 사용자 보고는 한국어로 하고, parser용 key/enum만 영어로 고정한다.

## 10. 남은 검증 항목

- Codex 0.144.6의 catalog/session budget과 config key는 확인했다. 150K 자동 compaction의 실제 handoff 품질은 UAT에서 확인해야 한다.
- Claude의 token counter, compaction, fork/session 차이는 실제 run에서 확인해야 한다.
- 영어 free text가 동일 내용의 한국어보다 성공률을 높이는지는 입증하지 않았다. 번역 오류나 비용이 보이면 한국어 단일 text로 전환한다.
- Multi-agent가 항상 single-agent보다 낫다는 결론도 근거가 없다. 독립성·병렬성·clean review가 필요한 slice에만 사용하고, 단순 작업은 triage에서 제외한다.

이 항목은 과장 없이 `KU`로 유지하고, 필요할 때 platform inspection이나 실제 작업 결과로 줄인다.
