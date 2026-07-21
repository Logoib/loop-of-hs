# Anthropic·CCA-F에서 추출한 Loop Engineering 원칙

> **문서 역할:** 연구 근거 부록이다. 현재 운영 규격은
> [05-loop-code-design.md](./05-loop-code-design.md)를 따른다.

- 조사일: 2026-07-21 (Asia/Seoul)
- 범위: 지정된 GeekNews 글·YouTube 발표, `D:\agentic_dev\CCA-F`, Anthropic/Claude 공식 문서
- 목적: Claude와 Codex 양쪽에서 사용할 loop skill family의 공통 운영 원칙 도출
- 표기: **[사실]** 출처가 직접 말하는 내용, **[추론]** 출처들을 결합한 해석, **[제안]** 이 프로젝트에 채택할 설계

## 결론

1. **Loop의 핵심 상태는 대화가 아니라 외부 ledger다.** 긴 대화의 요약이나 재개 기록을 정본으로 삼지 않고, 목표·검증 기준·결정·미해결 unknown·증거·다음 행동을 구조화 파일에 유지해야 한다.
2. **확률적 판단과 기계적 통제를 분리한다.** 모델은 모호성 발견, 분해, 대안 탐색, 합성에 쓰고, 명시된 완료 조건·fingerprint·상한은 스크립트와 테스트로 재현 가능하게 계산한다. 런타임별 hook이 없으면 호출 자체까지 비우회 강제된다고 주장하지 않는다.
3. **한 개의 오래된 200K 세션을 끝까지 끌고 가지 않는다.** 탐색→구현→독립 리뷰의 역할 경계마다 새 컨텍스트를 쓰고, continuity는 ledger와 파일 산출물로 전달한다. 단, 같은 문맥을 계속 참조해야 하는 짧고 밀접한 작업은 메인 세션에 남긴다.
4. **Hub-and-Spoke의 Hub는 일하는 곳이 아니라 상태를 통제하는 곳이다.** coordinator는 triage, 범위 분할, ledger, 충돌 조정, stop 판정만 맡고, 고용량 탐색·구현·검증은 좁은 계약을 받은 worker가 수행한다.
5. **Unknown 감소는 사전 계획 한 번으로 끝나지 않는다.** blind-spot pass, 인터뷰, 레퍼런스·프로토타입, implementation deviations, fresh-context review를 구현 전·중·후에 반복한다.
6. **완료는 모델의 느낌이 아니라 관찰 가능한 end state다.** 모든 성공 기준이 증거와 함께 통과하고, 치명적 unknown/리스크가 없으며, 독립 리뷰가 승인해야 성공 종료한다. 반복·시간·비용 상한에 닿으면 성공이 아니라 `blocked` 또는 `needs_human`으로 종료한다.

## 1. 조사 근거와 신뢰도

### 1.1 지정 자료

| 자료 | 확인 내용 | 판정 |
|---|---|---|
| [GeekNews: Fable 필드 가이드 — 나의 미지 찾기](https://news.hada.io/topic?id=31107) (확인: 2026-07-21) | 지도/영토, unknown 4분면, 구현 전·중·후 발견법의 한국어 요약 | 2차 요약. 원문 확인용 길잡이로 사용 |
| [Anthropic 공식 원문: A field guide to Claude Fable 5](https://claude.com/blog/a-field-guide-to-claude-fable-finding-your-unknowns) (확인: 2026-07-21) | unknown 분류, blind-spot pass, brainstorm/prototype, interview, reference, plan, implementation notes, explainer, quiz | 핵심 1차 출처 |
| [YouTube: Field Guide to Fable — Thariq Shihipar, Anthropic](https://www.youtube.com/watch?v=9fubhllmsBU) (확인: 2026-07-21) | 영상 제목과 발표자, Field Guide 발표 | 지정 영상. 이 환경에서 본문/자막 직접 fetch는 제한됨 |
| [Latent Space 발표 요약](https://www.traeai.com/articles/3211d659-4693-459b-8d60-177976f44912) (확인: 2026-07-21) | 발표 구간: unhobbling, unknowns, productivity grief, unreasonable ambition | 영상 구간을 보조 확인한 2차 출처. 기술 규칙의 단독 근거로 쓰지 않음 |

**[사실]** 지정 GeekNews 글은 이후 공개된 Anthropic 공식 글과 핵심 내용이 일치한다. 공식 글은 “프롬프트·스킬·컨텍스트”를 map, 실제 코드베이스·현실 제약을 territory로 보고 그 차이를 unknowns라 정의한다. 계획만으로는 충분하지 않으며 unknown은 구현 중에도 발견된다고 명시한다.

**[제한]** YouTube 자동 자막 URL은 이 조사 환경의 프록시에서 직접 가져오지 못했다. 따라서 발표의 구간 구성은 위 2차 recap으로만 보조 확인하고, 세부 작업 규칙은 내용이 공개된 Anthropic 공식 글과 공식 기술 문서를 기준으로 삼았다.

### 1.2 CCA-F에서 직접 확인한 문서

다음 로컬 문서를 전문 또는 관련 절 전체를 읽었다(확인: 2026-07-21).

- `D:\agentic_dev\CCA-F\wikidocs-revised\chapters\02-domain1-agentic\05_1_hub_spoke.md`
- `D:\agentic_dev\CCA-F\wikidocs-revised\chapters\02-domain1-agentic\05_2_coordinator_subagent.md`
- `D:\agentic_dev\CCA-F\wikidocs-revised\chapters\02-domain1-agentic\05_3_context_passing.md`
- `D:\agentic_dev\CCA-F\wikidocs-revised\chapters\02-domain1-agentic\06_3_task_decomposition.md`
- `D:\agentic_dev\CCA-F\wikidocs-revised\chapters\02-domain1-agentic\06_4_session_management.md`
- `D:\agentic_dev\CCA-F\wikidocs-revised\chapters\06-domain5-context\15_2_lost_middle.md`
- `D:\agentic_dev\CCA-F\wikidocs-revised\chapters\06-domain5-context\15_3_summarization.md`
- `D:\agentic_dev\CCA-F\wikidocs-revised\chapters\06-domain5-context\16_3_large_codebase.md`
- `D:\agentic_dev\CCA-F\wikidocs-revised\chapters\06-domain5-context\16_4_provenance.md`
- `D:\agentic_dev\CCA-F\wikidocs-revised\study_materials\11_핵심_교훈_의사결정원칙.md`

**[사실]** CCA-F는 학습 저장소이며 원문과 로컬 보충 노트가 함께 있다. 현행 제품 문법은 저장소 자체도 Anthropic 공식 문서로 다시 검증하도록 구분한다. 따라서 아래 설계에서 CCA-F는 원칙을 발견하는 자료로 사용하고, 현재 Claude 기능은 공식 문서로 재검증했다.

### 1.3 주요 1차 기술 출처

- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (Anthropic, 확인: 2026-07-21)
- [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) (Anthropic, 확인: 2026-07-21)
- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) (Anthropic, 확인: 2026-07-21)
- [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) (Anthropic, 확인: 2026-07-21)
- [How we contain Claude across products](https://www.anthropic.com/engineering/how-we-contain-claude) (Anthropic, 확인: 2026-07-21)
- [Loop engineering: Getting started with loops](https://claude.com/blog/getting-started-with-loops) (Claude by Anthropic, 확인: 2026-07-21)
- [Claude Code: subagents](https://code.claude.com/docs/en/sub-agents), [skills의 `context: fork`](https://code.claude.com/docs/en/skills#run-skills-in-a-subagent), [sessions](https://code.claude.com/docs/en/sessions), [how Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) (확인: 2026-07-21)

## 2. Unknowns를 ledger로 바꾸는 법

### 2.1 네 분면은 점수가 아니라 발견 경로다

**[사실]** Anthropic의 Field Guide는 다음 네 범주를 쓴다.

| 범주 | 실무 의미 | 값싼 발견법 |
|---|---|---|
| Known Knowns | 사용자가 이미 명시한 목표·제약 | 명세와 성공 기준으로 고정 |
| Known Unknowns | 미결정임을 알고 있는 질문 | 영향이 큰 질문부터 인터뷰·조사 |
| Unknown Knowns | 사용자는 보면 알지만 말로 쓰지 않은 선호·관례 | 레퍼런스, 서로 다른 프로토타입, 예시 비교 |
| Unknown Unknowns | 누구도 아직 고려하지 않은 함정·대안 | blind-spot pass, 코드·문서 탐색, premortem, 독립 리뷰 |

**[추론]** 이 분류를 `clarity_score: 83` 같은 단일 점수로 축약하면 어떤 불확실성이 남았는지, 누가 무엇으로 해결해야 하는지 알 수 없다. 점수는 작업을 멈추거나 계속할 근거가 되기 어렵다.

**[제안]** unknown 하나마다 다음을 기록하고, `resolved`는 증거가 있을 때만 허용한다.

```json
{
  "id": "U-014",
  "class": "known_unknown",
  "question": "Must retry requests remain idempotent across process restarts?",
  "impact": "architecture",
  "owner": "research-auth-retry",
  "status": "open",
  "resolution_method": "inspect existing persistence and confirm product requirement",
  "resolution": null,
  "evidence": []
}
```

`confidence: 0.8`처럼 근거 없는 자기 점수는 넣지 않는다. 대신 `status`, `evidence`, `contested`, `accepted_by`처럼 감사 가능한 필드를 쓴다.

### 2.2 Unknown 발견은 구현 전·중·후의 반복 작업이다

**[사실]** 공식 Field Guide는 다음 흐름을 제시한다.

- 구현 전: blind-spot pass → brainstorm/prototype → interview → reference → implementation plan
- 구현 중: 계획 이탈과 새 edge case를 `implementation-notes`에 기록
- 구현 후: explainer로 검토 맥락을 전달하고 quiz로 사용자의 실제 이해 확인

**[제안]** loop에서는 이를 다음 세 개의 gate로 줄인다.

1. **Discovery gate:** 아키텍처를 바꿀 수 있는 known unknown이 열려 있으면 구현하지 않는다.
2. **Deviation gate:** 구현 중 계획 이탈은 숨기지 않고 ledger에 `decision` 또는 `unknown`으로 추가한다. 안전한 보수 선택으로 계속할 수 없는 사안만 사람에게 올린다.
3. **Understanding gate:** 완료 전 사용자용 한국어 보고서와 fresh reviewer의 반대 관점 검토를 통과한다.

## 3. 결정론적 AI-native 작업법

### 3.1 모델에게 맡길 것과 코드로 고정할 것

**[사실]** CCA-F의 반복 원칙은 고위험 순서·권한·정확한 상태 보존을 프롬프트에만 맡기지 말고 hook, prerequisite, 구조화 fact block, 도구 권한으로 강제하는 것이다. Anthropic도 에이전트 오류에 적응적 모델 판단을 쓰되 retry logic과 checkpoints 같은 결정적 safeguard를 함께 쓴다고 설명한다([multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system), 확인: 2026-07-21). 보안 경계는 모델이 “하려는 것”보다 환경이 “할 수 있는 것”을 제한해야 한다([How we contain Claude](https://www.anthropic.com/engineering/how-we-contain-claude), 확인: 2026-07-21).

**[제안]** 역할 분할은 다음과 같다.

| 확률적 모델이 맡음 | 결정적 harness가 맡음 |
|---|---|
| 모호성·blind spot 발견 | 허용 경로·도구·권한 |
| 작업 분해와 대안 생성 | 필수 선행조건·의존성 |
| 증거 탐색과 의미 합성 | JSON schema와 필수 필드 |
| 실패 원인 추론과 다음 시도 제안 | 재시도·턴·시간·비용 상한 |
| 코드·문서 생성 | 테스트 실행과 exit code 수집 |
| 충돌 설명 | 성공/실패/blocked 상태 전이 |

이 구분은 “AI-native = 모든 결정을 AI에 맡김”이 아니라, AI가 잘하는 적응적 판단을 결정적 경계 안에서 반복하게 한다.

### 3.2 완료는 end-state로 검증한다

**[사실]** Anthropic은 상태를 변경하는 장기 에이전트의 평가는 매 턴의 경로보다 최종 상태를 보고, 복잡한 작업은 명시적 checkpoint로 나누는 것이 효과적이었다고 보고한다([multi-agent research system appendix](https://www.anthropic.com/engineering/multi-agent-research-system), 확인: 2026-07-21). 장기 harness 실험에서는 모든 기능을 처음에 failing으로 두고, 실제 end-to-end 테스트 뒤에만 passing으로 바꾸었다([long-running harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), 확인: 2026-07-21).

**[제안]** ledger의 success criterion은 설명이 아니라 실행 가능한 verifier와 evidence를 가져야 한다.

```json
{
  "id": "SC-03",
  "description": "Existing authentication flows remain functional",
  "verifier": "npm test -- auth",
  "status": "failing",
  "evidence": null,
  "verified_at": null
}
```

모델은 `passing`을 선언할 수 있지만, coordinator는 verifier의 관찰 결과가 없으면 상태 변경을 거부한다.

## 4. Scratchpad·ledger 설계

### 4.1 왜 대화 요약이 정본이 될 수 없는가

**[사실]** Claude Code context에는 대화, 파일, 명령 출력, 규칙, 로드한 스킬이 함께 쌓이고, 자동 compaction 때 오래된 세부 지시가 손실될 수 있다([How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works), 확인: 2026-07-21). Anthropic은 context가 길어질수록 recall이 저하되는 context rot을 지적하고, 장기 작업의 대응으로 compaction, structured note-taking, multi-agent architecture를 함께 제안한다([Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), 확인: 2026-07-21).

**[사실]** CCA-F도 정확한 금액·날짜·ID·결정 상태는 손실 요약 바깥의 구조화 fact block에 두고, scratchpad에는 확인한 흐름·파일 위치·미확인 항목을 남기도록 설명한다.

**[추론]** “항상 200K까지 채운 뒤 compact”는 최상의 context를 유지하는 정책이 아니다. Anthropic의 Research 설계가 200K를 넘을 때 계획이 잘릴 수 있어 Memory에 저장한 사실은 있지만, 모든 모델·과제에 적용되는 200K 성능 절벽 임계값을 제시한 것은 아니다. 토큰 수 하나보다 **상태가 재구성 가능한가, 관련 없는 출력이 주의를 점유하는가, 기준점이 낡았는가**를 봐야 한다.

### 4.2 하나의 canonical ledger

**[제안]** 중복 상태 파일을 늘리지 말고 `loop-ledger.json` 하나를 정본으로 둔다. 보고서·코드·테스트 결과는 별도 산출물 경로로 참조한다. JSON을 권하는 이유는 외부 의존성 없이 검증할 수 있고, Anthropic 장기 harness에서도 status 파일을 Markdown보다 모델이 임의 수정하기 어려운 JSON으로 정착시킨 경험이 있기 때문이다.

```json
{
  "schema_version": 1,
  "objective": "One sentence, observable outcome",
  "baseline": {
    "workspace": "absolute path",
    "revision": "git commit or explicit snapshot id",
    "started_at": "ISO-8601"
  },
  "phase": "triage",
  "success_criteria": [],
  "unknowns": [],
  "decisions": [],
  "tasks": [],
  "risks": [],
  "artifacts": [],
  "handoff": {
    "current_focus": null,
    "changed_paths": [],
    "blockers": [],
    "next_action": null
  },
  "limits": {
    "max_iterations": null,
    "deadline": null,
    "budget": null
  }
}
```

Parser가 읽는 field와 enum은 영어로 고정한다. free text는 cross-runtime handoff와 사용자 선호에 맞춰 영어 또는 한국어를 쓴다. 영어가 더 높은 성공률을 준다는 직접 근거는 없다. 한국어 진행 보고는 별도 상태 파일로 복제하지 않고 이 ledger를 매번 읽어 렌더링한다.

```text
[진행 4/9] 구현 단계
- 방금 완료: 인증 경로 caller 6곳 확인, U-014 해결
- 현재 작업: 재시도 idempotency 구현
- 막힘: 없음
- 다음: 통합 테스트 후 독립 리뷰
- 컨텍스트 상태: 구현 세션 fresh / 기준 commit abc1234
```

### 4.3 갱신 규칙

**[제안]**

1. coordinator만 canonical ledger를 갱신한다. 병렬 worker는 자신의 산출물만 쓰고, ledger patch 요청을 결과로 반환한다.
2. 기존 사실과 새 사실이 충돌하면 덮어쓰지 않는다. 양쪽 evidence를 보존하고 `contested`로 바꾼다.
3. raw tool log는 ledger에 넣지 않는다. 재현 명령, exit code, 핵심 결과, artifact path만 넣는다.
4. 작업 시작 전 `baseline.revision`과 변경 파일을 재확인한다. 달라졌으면 관련 사실을 `stale`로 바꾸고 다시 조사한다.
5. 각 session 종료 전 `handoff.next_action`이 하나의 실행 가능한 문장인지 확인한다.

## 5. Session, fork, fresh context를 구분하는 규칙

### 5.1 용어 충돌 주의

**[사실]** 현재 Claude 문서에서 서로 다른 두 기능이 “fork”라는 말을 쓴다.

- CLI `claude --resume <id> --fork-session` 또는 `/branch`: 기존 대화 기록을 복제해 새 session ID로 분기하며 원본은 유지한다([sessions](https://code.claude.com/docs/en/sessions), 확인: 2026-07-21).
- 스킬 frontmatter `context: fork`: 스킬을 격리된 subagent에서 실행하고 메인 conversation history를 주지 않는다. 스킬 본문이 task가 되며 결과 요약만 돌아온다([skills](https://code.claude.com/docs/en/skills#run-skills-in-a-subagent), 확인: 2026-07-21).

Claude Code의 일반 subagent도 fresh isolated context에서 시작하며, forked subagent만 부모 history를 상속한다([subagents](https://code.claude.com/docs/en/sub-agents), 확인: 2026-07-21).

**[제안]** skill 문서에서는 혼동을 피하도록 기능명을 다음처럼 쓴다.

| 내부 이름 | 실제 의미 | 사용할 때 |
|---|---|---|
| `continue_main` | 같은 session을 계속 사용 | 짧고 상호 의존적인 탐색→수정→테스트 |
| `fresh_worker` | history 없는 좁은 subagent | 조사 로그가 크거나 독립 작업·독립 리뷰 |
| `branch_session` | 공통 history에서 대안 분기 | 같은 기준선에서 A/B 접근을 실제로 비교 |
| `new_phase_session` | ledger+artifact만 전달한 새 session | 탐색→구현, 구현→adversarial review 전환 |

### 5.2 선택 규칙

**[제안]**

- **메인 유지:** 다음 단계가 이전 대화의 세부 reasoning을 자주 참조하고 출력량이 작다.
- **fresh worker:** 작업이 self-contained이고, 원문 로그를 coordinator가 볼 필요가 없으며, 한 페이지 수준의 결과 계약으로 환원 가능하다.
- **branch session:** 동일한 base reasoning 자체가 두 대안 모두에 필요하고, 두 경로를 서로 오염시키지 않은 채 비교해야 한다.
- **new phase session:** 이전 reasoning이 bias가 되거나, 계획·spec·ledger가 이미 continuity를 충분히 담고 있다. Anthropic Field Guide도 계획 승인 뒤 artifacts를 전달해 새 구현 session을 시작한다고 설명한다.
- **resume 금지:** baseline이 바뀌었거나 ledger와 session의 사실이 충돌한다. 새 session이 현재 파일과 ledger를 다시 읽게 한다.

### 5.3 Context refresh trigger

**[추론·제안]** 보편적인 토큰 퍼센트 하나를 hard code하지 않는다. 다음 이벤트 중 하나면 context를 새로 연다.

- phase가 exploration→implementation 또는 implementation→independent review로 바뀜
- compaction이 발생했는데 ledger로 보존되지 않은 결정·unknown이 있음
- 대용량 테스트·검색·로그가 main context의 주된 내용이 됨
- 기준 revision 또는 핵심 입력 파일이 바뀜
- agent가 ledger에 이미 있는 결정을 반복해서 재조사함
- 독립성 자체가 검증 조건임(premortem, adversarial review)

새 context는 `objective`, `baseline`, 관련 success criteria, 담당 범위, 필요한 artifact path, 열린 unknown, output schema만 받는다. 전체 transcript 복사는 금지한다.

## 6. Hub-and-Spoke와 context passing

### 6.1 역할 경계

**[사실]** Anthropic Research는 lead agent가 전략 수립·분해·합성을 맡고, 전문 subagent가 서로 다른 영역을 병렬 탐색하는 orchestrator-worker 구조다. 각 worker의 task에는 objective, output format, 도구·source 지침, 명확한 boundary가 필요하며, 모호한 지시는 중복과 공백을 만들었다([multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system), 확인: 2026-07-21).

**[사실]** CCA-F의 Hub-and-Spoke 기본형도 worker끼리 암묵적 공유 상태를 수정하지 않고 coordinator가 전역 진행·충돌·합성을 관리하도록 한다.

**[제안]** 기본 토폴로지는 다음과 같다.

```text
User
  ↕ Korean monitoring report
Coordinator / Hub
  ├─ owns triage, ledger, task boundaries, synthesis, stop decision
  ├─ Fresh discovery worker(s) ──> artifacts + ledger patch request
  ├─ Implementation worker(s) ──> code + verifier evidence
  └─ Fresh adversarial reviewer ─> findings + pass/block verdict
```

worker 간 직접 메시지와 공유 ledger 쓰기는 기본적으로 금지한다. 먼저 완성된 artifact를 Hub가 등록하고 다음 worker에게 path로 전달한다. 실시간 peer coordination이 실제 병목으로 측정될 때만 확장한다.

### 6.2 최소 충분 delegation packet

**[제안]** 모든 worker 호출은 같은 계약을 쓴다.

```text
ROLE: one narrow specialty
OBJECTIVE: one observable outcome
BASELINE: revision/snapshot and workspace
SCOPE: included paths/questions
OUT OF SCOPE: explicit exclusions
INPUTS: approved facts and artifact paths
TOOLS/PERMISSIONS: least privilege
SUCCESS CRITERIA: IDs from the ledger
OUTPUT: artifact path + concise summary + evidence + unresolved items
FAILURE: attempts, partial result, blocker, recommended next action
```

**[사실]** Anthropic은 subagent가 수만 토큰을 탐색하더라도 lead에는 보통 1,000~2,000 token의 distilled summary만 반환하는 패턴을 설명한다([Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), 확인: 2026-07-21). 더 큰 구조화 결과는 파일에 직접 쓰고 coordinator에는 경량 reference만 전달하면 “game of telephone”과 토큰 복사를 줄일 수 있다고 보고한다([multi-agent appendix](https://www.anthropic.com/engineering/multi-agent-research-system), 확인: 2026-07-21).

### 6.3 언제 multi-agent를 쓰지 않는가

**[사실]** Anthropic은 multi-agent가 chat 대비 많은 토큰을 쓰며, 모든 agent가 같은 context를 공유해야 하거나 의존성이 많은 작업에는 맞지 않는다고 명시한다. 특히 일반적인 코딩 작업은 연구보다 실제 병렬 영역이 적다([multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system), 확인: 2026-07-21).

**[제안]** 다음이면 subagent를 만들지 않는다.

- 한 파일의 명백한 소규모 수정
- 앞 단계 출력에 강하게 의존하는 짧은 순차 작업
- worker 결과를 설명하는 비용이 직접 수행보다 큼
- 별도 context가 새로운 검증 독립성이나 출력 격리를 제공하지 않음

## 7. Loop-engineering 초안에 적용할 실행 규칙

### 7.1 Triage

**[제안]** 가장 단순한 rung에서 멈춘다.

| 등급 | 조건 | 실행 |
|---|---|---|
| `direct` | 범위가 명확하고 작은 수정, 검증 1개로 충분 | 같은 session에서 읽기→수정→검증 |
| `planned` | 여러 단계지만 의존성이 선형이고 unknown 영향이 낮음 | 짧은 plan, 같은 session 또는 한 번의 phase refresh |
| `loop` | 장기·병렬·고위험·불명확, 또는 독립 리뷰 필요 | canonical ledger + Hub-and-Spoke + hard limits |

단순 작업에 ledger·premortem·다중 worker를 강제하지 않는다. Anthropic의 공식 loop 가이드도 모든 작업에 복잡한 loop가 필요한 것은 아니며 가장 단순한 해법에서 시작하라고 한다([Getting started with loops](https://claude.com/blog/getting-started-with-loops), 확인: 2026-07-21).

### 7.2 전체 loop

```text
TRIAGE
  └─ if loop:
       INIT LEDGER
         → REDUCE UNKNOWNS
         → FREEZE SUCCESS CRITERIA + BASELINE
         → FRESH PREMORTEM / ADVERSARIAL PLAN REVIEW
         → EXECUTE ONE VERIFIED SLICE
         → UPDATE LEDGER + KOREAN MONITOR
         → FRESH RESULT REVIEW
         → STOP or NEXT SLICE
```

**[제안]** 각 반복에서 한 개의 검증 가능한 slice만 완료한다. Anthropic 장기 harness 실험도 한 번에 전체 앱을 만들려는 실패를 막기 위해 한 feature씩 진행하고, session 말에 progress와 clean state를 남겼다.

### 7.3 Premortem과 독립 리뷰

**[사실]** Anthropic 공식 loop 가이드는 code review에 fresh context의 두 번째 agent를 쓰면 주 agent의 reasoning에 덜 영향받는다고 권한다([Getting started with loops](https://claude.com/blog/getting-started-with-loops), 확인: 2026-07-21).

**[제안]** premortem/reviewer에는 main agent의 장황한 reasoning이나 자기평가를 전달하지 않는다. 전달물은 다음뿐이다.

- 원래 objective와 success criteria
- 현재 baseline과 실제 diff/artifacts
- 확인된 제약·accepted decisions
- 실행 가능한 verifier

리뷰 결과는 `finding_id`, severity, evidence location, violated criterion, reproduction/verifier, recommendation으로 반환한다. `looks good`은 승인 증거가 아니다.

### 7.4 Stop criteria

**[사실]** Anthropic은 loop를 stop condition까지 반복하는 구조로 정의한다. goal-based loop는 goal 달성 또는 turn cap에서 멈추며, deterministic criterion과 명시적 시도 상한을 권한다([Getting started with loops](https://claude.com/blog/getting-started-with-loops), 확인: 2026-07-21).

**[제안]** 성공 종료는 아래 조건의 논리곱이다.

```text
SUCCESS =
  every success criterion has executable passing evidence
  AND no critical/high review finding remains open
  AND no architecture/safety unknown remains open
      unless explicitly accepted by the user
  AND required artifacts exist at the recorded baseline
  AND fresh reviewer returns pass
```

안전 종료는 별도로 둔다.

```text
BLOCKED / NEEDS_HUMAN =
  iteration, deadline, or budget cap reached
  OR one bounded round produces no measurable ledger delta and one clean recovery also stalls
  OR required authority/input is unavailable
  OR the next action would exceed granted permissions
```

상한 도달을 성공으로 포장하지 않는다. 부분 결과·시도·열린 unknown·다음 선택지를 ledger와 한국어 모니터에 남긴다.

## 8. Claude/Codex 공용 skill에 대한 구체적 설계 방향

**[제안]** 공통 core는 제품 명령어가 아닌 상태 기계와 계약으로 작성한다.

- 공통 `SKILL.md`: triage, ledger schema, unknown workflow, delegation packet, review contract, stop rules
- Claude adapter: fresh subagent, `context: fork`, `/branch`/`--fork-session`, `/goal` 같은 현재 primitive에 매핑
- Codex adapter: 같은 의미의 goal/session/subagent primitive에 매핑하되 core 상태 값은 바꾸지 않음
- 한국어 monitor: canonical English ledger를 읽어 사용자에게만 한국어로 요약

Claude 전용 frontmatter를 공통 의미로 오해하지 않는다. 특히 `context: fork`와 session branch를 platform-neutral 문서에서는 각각 `fresh_worker`, `branch_session`으로 표현한다.

## 9. 채택·보류 판정

### 즉시 채택

- 영어 canonical ledger와 evidence 기반 상태 전이
- unknown 4분면을 점수가 아닌 작업 queue로 사용
- 탐색→구현→리뷰 phase별 fresh context
- Hub 단일 ledger writer + worker artifact handoff
- deterministic verifier, hard cap, least privilege
- fresh-context premortem/adversarial review
- ledger에서 생성하는 한국어 실시간 monitor

### 조건부 채택

- 여러 worker 병렬화: 독립 범위가 실제로 있을 때만
- session branch: 공통 history 전체가 두 대안에 필요할 때만
- compaction: 같은 대화를 유지해야 할 때만; ledger를 대체하지 않음
- MCP: 외부 서비스·원격 공용 상태 접근이 필요할 때만. 로컬 ledger와 repo 작업만이라면 파일·기존 CLI가 더 단순함

### 채택하지 않음

- 근거 없는 종합 점수로 unknown 해소/완료 판정
- 전체 transcript를 모든 worker에게 복사
- coordinator가 탐색·구현·리뷰를 모두 직접 수행
- 단순 작업에도 multi-agent와 premortem 강제
- 모델의 “완료했습니다” 또는 self-confidence만으로 loop 종료
- 200K 같은 단일 토큰 숫자만으로 context refresh 결정

## 10. 최종 설계 원칙 요약

> **Keep the task state outside the conversation, keep worker context narrow and fresh, let models discover and decide, let deterministic evidence control transitions, and stop only on an observable end state.**

이 원칙은 CCA-F의 사전 예방·최소 권한·구조화 사실·Hub 조정 철학, Anthropic의 unknown discovery·structured note-taking·fresh subagents·long-running harness·end-state evaluation을 하나의 최소 loop로 결합한다.
