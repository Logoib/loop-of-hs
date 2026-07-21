# Loop-engineering landscape comparison

> **문서 역할:** 비교 조사 부록이다. 여기서 추출한 운영 규격은
> [05-loop-code-design.md](./05-loop-code-design.md)를 따른다.

작성일: 2026-07-21 (Asia/Seoul)
조사 범위: 공식 GitHub README, 저장소 내 공식 문서와 공개 코드 구조를 우선 사용했다.
주의: 아래 star 수는 2026-07-21 조회 화면의 반올림된 근사값이다. 인기도의 신호일 뿐 품질이나 적합성의 증거로 쓰지 않는다.

## 결론 먼저

하나의 프레임워크를 통째로 이식하지 않는 것이 좋다. 이 프로젝트에 맞는 최소 조합은 다음과 같다.

1. **Triage는 OmO의 세 갈래 분류를 단순화해 사용한다.** 즉시 실행, 짧은 plan, durable loop 세 단계면 충분하다.
2. **초기 명세는 Ouroboros의 Socratic interview를 차용하되, LLM이 스스로 부여한 ambiguity 점수는 통과 게이트로 쓰지 않는다.** 점수 대신 unresolved critical unknown이 0인지 확인한다.
3. **상태는 GSD와 Ralph처럼 짧은 영어 artifact로 외부화한다.** 매 작업을 fresh-context worker가 처리하고, coordinator는 ledger와 증거만 유지한다.
4. **변경 계약은 OpenSpec의 current truth / proposed delta 분리를 차용한다.** 계약을 영원히 불변으로 만들지 말고 cycle baseline과 명시적 amendment를 구분한다.
5. **프리모템과 완료 리뷰는 gstack의 독립 Codex review, Superpowers의 spec-compliance → code-quality 순서를 차용한다.** 같은 세션의 자기평가는 보조 증거일 뿐이다.
6. **실행 모델 라우팅은 OmO의 category 개념만 차용한다.** 역할 이름과 hook 수십 개는 가져오지 않는다.
7. **루프 종료는 검증 가능한 acceptance criteria, 테스트/검사 증거, 미해결 blocker 부재, iteration budget을 함께 사용한다.** 문자열 completion promise 하나로 종료하지 않는다.
8. **MCP는 v1 핵심에서 제외한다.** 파일, Git, 기존 Claude/Codex skill 표면으로 충분하다. 여러 호스트가 하나의 live EventStore를 공유해야 할 때만 선택형 adapter로 추가한다.

## 한눈에 보는 비교

| 프로젝트 | 조회 star | 실제 중심 루프 | 가장 가치 있는 차용점 | 주된 비용/위험 | 판단 |
|---|---:|---|---|---|---|
| [Q00/ouroboros](https://github.com/Q00/ouroboros) | 약 5.0k | Interview → Seed → Execute → Evaluate → Evolve | Socratic unknown reduction, explicit Seed/ledger, bounded failure signals | 자기평가 점수의 의사정밀성, EventStore/MCP/ontology까지 포함한 큰 런타임 | 개념 선별 채용 |
| [garrytan/gstack](https://github.com/garrytan/gstack) | 약 123k | Think → Plan → Build → Review → Test → Ship → Reflect | 역할별 사전검토, 독립 Codex adversarial review, 안전 guard | skill 수가 많고 제품/브라우저/배포까지 범위가 넓음 | review 패턴 채용 |
| [obra/superpowers](https://github.com/obra/superpowers) | 약 258k | Brainstorm → worktree → plan → fresh subagents/TDD → review → finish branch | 짧은 task, fresh worker, spec/quality 2단계 검토 | 모든 작업에 강제하면 의식과 TDD 비용이 큼 | complex lane에 채용 |
| [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done) | 약 64.8k | Discuss → Plan → Execute → Verify → Ship | phase artifact, fresh 200k context executor, wave 실행 | 명령·상태 파일·옵션이 많아짐 | 구조의 중심으로 채용 |
| [open-gsd/gsd-core](https://github.com/open-gsd/gsd-core) | 약 6.9k | 위 GSD의 현재 개발 계보 | current source, cross-runtime installer | 이전 저장소와 문서 계보 혼동 가능 | 구현 참조는 이쪽 |
| [code-yeongyu/lazycodex](https://github.com/code-yeongyu/lazycodex) | 약 2.9k | OmO를 Codex에 설치하는 배포판 | Codex 설치/호환 표면, `$ulw-plan`·`$start-work`·`$ulw-loop` 구분 | OmO와 별도 방법론으로 중복 도입하기 쉬움 | 배포 참고만 |
| [code-yeongyu/oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent) (OmO) | 약 66.3k | Sisyphus/Prometheus/Atlas와 specialist fan-out | triage, planner/executor 분리, category model routing | hook·agent·fallback 복잡성, token burn, promise-loop 과신 | 라우팅만 선별 채용 |
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | 약 86.6k | 구현 전 YAGNI/reuse/stdlib/native ladder | 작은 diff, 기존 코드 재사용, root-cause fix | 탐색과 프리모템까지 켜면 조기 축소 편향 | 실행 단계에 조건부 채용 |
| [RimuruW/pi-hashline-edit](https://github.com/RimuruW/pi-hashline-edit) | 약 138 | read의 line+hash anchor를 edit 전 검증 | stale state를 조용히 덮지 않는 compare-and-swap 원리 | host 편집 도구를 바꾸면 이식성 하락, 짧은 hash 충돌 | 원리만 채용 |

## 1. Ouroboros

### 실제 workflow

공식 README가 정의하는 cycle은 `Interview → Seed → Execute → Evaluate`, 그리고 평가 결과를 다음 generation에 넣는 `Evolve`다. Interview는 Socratic 질문으로 goal, constraints, success criteria, brownfield context를 명확히 하고, 답을 frozen Pydantic Seed로 만든다. 실행은 Double Diamond(Discover → Define → Design → Deliver), 평가는 mechanical → semantic → multi-model consensus의 세 단계다. 상태 변경은 SQLite append-only EventStore에 기록되어 resume/replay/retrospective를 지원한다. [README](https://github.com/Q00/ouroboros#the-loop), [architecture](https://github.com/Q00/ouroboros/blob/main/docs/architecture.md)

공식 종료 규칙은 다음과 같다.

- Interview: LLM이 각 clarity dimension을 0~1로 평가한 뒤 `ambiguity <= 0.2`이면 Seed 생성.
- Evolve: 연속 ontology schema의 weighted similarity가 `>= 0.95`이면 수렴.
- 병적 loop 감지: 3회 stagnation, 2주기 oscillation, 3세대에 걸친 질문 70% 이상 반복, hard cap 30 generations. [README의 수식과 stop rules](https://github.com/Q00/ouroboros#the-loop)

### 장점

- 사용자의 모호한 요구를 구현 전에 드러내는 데 가장 직접적이다.
- Seed, acceptance criteria, exit conditions, ledger를 모델 대화와 분리해 재실행·감사·handoff가 쉽다.
- 무한 루프를 convergence, repetition, oscillation, hard cap의 여러 신호로 막으려는 점이 좋다.
- runtime adapter로 Claude/Codex 등 실행 호스트와 workflow contract를 분리한다.

### 단점과 검증 한계

- `ambiguity <= 0.2`와 ontology similarity `>= 0.95`는 공식 문서에 수식은 있으나 실제 task 성공 확률에 대해 교정되었다는 외부 검증은 제시되지 않는다. 특히 clarity 자체를 LLM이 채점하므로 숫자는 재현 가능한 측정치라기보다 **형식화된 자기평가**다.
- ontology field 이름의 유사성은 소프트웨어가 맞게 동작하는지, 사용자의 가치가 충족됐는지와 동일하지 않다. 잘못된 ontology도 안정적으로 반복될 수 있다.
- 불변 Seed는 drift를 막지만, 조사 중 드러난 사실을 받아들일 때 Seed를 새 generation으로 복제해야 한다. 작은 개인 workflow에는 ceremony가 크다.
- full EventStore, checkpoint, runtime adapters, MCP hub까지 들이면 loop를 쓰기보다 loop platform을 유지하는 일이 생긴다.

### 채용 / 배제

채용:

- 질문을 `known-known`, `known-unknown`, `unknown-known`, `unknown-unknown probe`로 ledger에 기록.
- critical unknown마다 `owner`, `resolution_method`, `evidence`, `deadline/gate`를 둠.
- oscillation, repetitive failure, hard iteration/cost/time cap을 종료 또는 escalation 신호로 사용.
- cycle마다 contract baseline을 freeze하고 변경은 amendment로 남김.

배제:

- LLM ambiguity 숫자를 build/no-build 단일 게이트로 사용.
- ontology similarity를 완료 조건으로 사용.
- v1에서 EventStore, SQLite, TUI, MCP hub를 재구현.

대체 게이트는 단순하다: **critical unknown이 없고, 각 acceptance criterion에 실행 가능한 verification method가 있으면 실행한다.** 중요하지 않은 unknown은 `accepted-risk`로 명시한다.

### Ouroboros에 MCP가 있는 이유

Ouroboros는 MCP를 양방향 hub로 사용한다. server mode는 `execute_seed`, `session_status`, `query_events` 같은 stateful runtime 기능을 Claude Desktop 등 여러 client에 노출하고, client mode는 filesystem/GitHub/database 같은 외부 tool을 실행에 합친다. 즉 MCP의 이유는 인터뷰 자체가 아니라 **호스트 간 공통 control plane과 tool transport**다. [MCP integration](https://github.com/Q00/ouroboros/blob/main/docs/architecture.md#integration-points)

우리 loop의 v1에는 MCP가 필요하지 않다.

- Claude와 Codex 모두 SKILL.md, Git, shell, 파일 artifact를 읽을 수 있다.
- ledger와 task packet이 저장소에 있으면 session resume와 clean-room review가 가능하다.
- MCP server는 설치·권한·버전·프로세스 수명·보안 경계를 추가한다.
- 사용자의 핵심 목표는 live remote service가 아니라 context freshness와 결정론적 handoff다.

추후 다음 조건이 실제로 생기면 optional MCP adapter를 추가한다.

1. Claude/Codex/Pi가 동시에 같은 live run을 조회·claim해야 한다.
2. append-only event stream과 server-side atomic claim이 파일 lock보다 중요해진다.
3. IDE 밖의 dashboard가 실시간 상태를 구독해야 한다.
4. Jira/GitHub/DB 같은 외부 system을 permission-scoped tool로 표준화해야 한다.

## 2. gstack

### 실제 workflow

gstack은 역할별 skill collection이면서 `Think → Plan → Build → Review → Test → Ship → Reflect` sprint를 명시한다. `/office-hours`가 여섯 forcing question과 design doc을 만들고, CEO/engineering/design/DX plan review가 이를 구체화한다. 구현 후 `/review`, 실제 브라우저 `/qa`, `/ship`, `/retro`로 이어진다. 현재 README에는 Codex host 설치와 `/codex` 독립 review도 들어 있다. `/codex`는 pass/fail review, adversarial challenge, open consultation의 세 모드를 제공하며 Claude review와 결과를 교차 비교한다. [sprint와 role map](https://github.com/garrytan/gstack#the-sprint), [Codex second opinion](https://github.com/garrytan/gstack#power-tools)

### 장점

- 제품 가치, 설계, architecture, DX를 서로 다른 질문 세트로 분리한다.
- 구현 전 plan review와 구현 후 live QA를 대칭으로 둔다.
- 다른 모델의 clean second opinion을 명시적인 gate로 쓰는 방식이 프리모템에 잘 맞는다.
- `/careful`, `/freeze`, `/guard`처럼 scope와 destructive action을 제어하는 작은 안전장치가 실용적이다.
- continuous checkpoint가 WIP commit body에 decisions, remaining work, failed approaches를 기록하는 방식은 crash recovery에 유용하다.

### 단점

- 현재 표면이 수십 개 skill, browser daemon, 배포, design, document, analytics까지 포함해 개인 loop core로는 넓다.
- 역할이 많다고 관점이 독립적인 것은 아니다. 같은 context와 같은 모델 family가 역할 prompt만 바꿔 읽으면 상관된 오류가 남는다.
- 모든 feature에 CEO/design/DX/eng review를 연속 적용하면 latency와 token cost가 커진다.

### 채용 / 배제

채용:

- 프리모템을 새 session/다른 model의 adversarial review로 실행.
- review output을 `blocker`, `needs-decision`, `non-blocking` 세 종류로 제한.
- 변경 범위 freeze와 destructive-action guard를 task packet에 포함.
- UI가 있는 작업만 실제 browser QA를 acceptance evidence로 요구.

배제:

- gstack 전체를 core dependency로 설치.
- 모든 역할을 모든 task에 실행.
- reviewer의 점수 평균으로 승인. 근거와 재현 절차가 없는 score는 쓰지 않는다.

## 3. Superpowers

### 실제 workflow

공식 기본 흐름은 `brainstorming → using-git-worktrees → writing-plans → subagent-driven-development/executing-plans → TDD → requesting-code-review → finishing-a-development-branch`다. 계획은 2~5분 단위의 구체적인 task로 쪼개고, subagent-driven development는 매 task에 fresh subagent를 쓰며 spec compliance를 먼저, code quality를 다음으로 검토한다. [official workflow](https://github.com/obra/superpowers#the-basic-workflow)

### 장점

- fresh worker가 이전 task의 불필요한 대화를 상속하지 않는다.
- spec compliance와 code quality를 분리해 “좋은 코드로 잘못된 기능”을 잡는다.
- worktree 격리와 branch finishing 절차가 병렬 작업 충돌과 미완료 선언을 줄인다.
- 테스트를 완료 주장보다 앞에 두는 `evidence over claims` 원칙이 명확하다.

### 단점

- strict TDD와 2~5분 task는 모든 변경에 적합하지 않다. 문서, 설정, exploratory spike에는 과하다.
- 매 task마다 subagent와 두 단계 review를 쓰면 아주 작은 변경보다 orchestration 비용이 커진다.
- 자동 skill trigger가 host별 설치·hook 동작에 의존할 수 있다.

### 채용 / 배제

채용:

- durable-loop lane에만 fresh worker per task.
- `spec check → correctness/quality check` 순서.
- 각 non-trivial task에 최소 하나의 runnable verification.
- 병렬 write가 필요할 때 worktree 또는 명시적 file ownership.

배제:

- simple lane의 worktree/subagent/reviewer ceremony.
- 모든 변경의 strict TDD. 대신 위험도에 따라 테스트, typecheck, lint, build, browser evidence 중 최소 충분한 것을 계약에 둔다.

## 4. GSD / GSD Core

### 현재 계보

사용자가 지정한 `gsd-build/get-shit-done`은 2026-06-26 archive되었고 현재 개발은 [open-gsd/gsd-core](https://github.com/open-gsd/gsd-core)로 이동했다. 이전 저장소의 약 64.8k star와 새 저장소의 약 6.9k star는 합산하면 안 된다. 구현과 최신 문서는 새 저장소를 기준으로 삼아야 한다. [migration notice](https://github.com/gsd-build/get-shit-done)

### 실제 workflow

현재 공식 설명은 milestone의 각 phase마다 `Discuss → Plan → Execute → Verify → Ship`을 반복하는 구조다. 무거운 research/planning/execution은 fresh-context subagent에 보내고 main session을 가볍게 유지한다. 계획은 한 fresh context에 맞도록 쪼개며 execution은 parallel wave로 수행한다. [GSD Core README](https://github.com/open-gsd/gsd-core#how-it-works)

공식 configuration에는 plan check 반복 상한, discuss pass 상한, node repair budget, subagent timeout, worktree isolation, cross-AI review/execution, context-linked artifact 같은 bounded controls가 있다. [configuration](https://github.com/gsd-build/get-shit-done/blob/main/docs/CONFIGURATION.md)

### 장점

- context rot을 workflow 구조의 문제로 보고 fresh subagent와 durable `.planning/` artifact로 해결한다.
- phase/plan/task 계층과 wave 실행이 큰 작업을 context-sized unit으로 만드는 데 적합하다.
- research, plan verification, execution, UAT가 별도 artifact를 남겨 resume가 쉽다.
- quick path와 full phase path가 분리되어 있다.

### 단점

- roadmap, requirements, context, research, plans, summaries, state 등 artifact가 누적되면 읽어야 할 문서 자체가 context tax가 된다.
- command와 toggle 수가 많아 framework 운영이 목적이 되기 쉽다.
- 계획을 잘게 쪼갠 것만으로 cross-phase integration risk가 사라지지 않는다.

### 채용 / 배제

채용:

- main coordinator에는 ledger index와 현재 gate만 둔다.
- research/plan/execute/review를 각각 fresh session에서 수행.
- task packet은 한 context 안에 조사·수정·검증이 끝나는 크기로 제한.
- parallel wave는 file ownership과 dependency가 명확한 task에만 사용.
- phase close 때 통합 검증을 별도로 수행.

배제:

- 모든 GSD artifact와 command를 복제.
- 상태 문서를 무기한 append. active ledger에는 current facts만 두고 history는 archive로 이동한다.

## 5. LazyCodex

### 실제 정체와 workflow

LazyCodex는 독립 orchestration engine이 아니라 공식 README가 명시하듯 OmO를 Codex에 설치하는 thin distribution이다. `npx lazycodex-ai install`은 `oh-my-openagent ... --platform=codex`의 shorthand다. 표면은 `/init-deep`, `$ulw-plan`, `$start-work`, `$ulw-loop`를 제공하고, loop는 Oracle-verified completion을 주장하며 normal 100 / ultrawork 500 iteration cap을 둔다. [official README](https://github.com/code-yeongyu/lazycodex)

### 장점

- Codex에서 OmO의 command, agent, hook, model routing을 한 번에 설치한다.
- plan-only, plan execution, open-ended loop의 사용자 표면이 명확하다.
- AGENTS.md 계층화와 durable progress가 큰 codebase onboarding에 도움 된다.

### 단점

- OmO와 함께 두 개의 독립 프레임워크로 설계하면 같은 시스템을 이중으로 감싸게 된다.
- 100/500 iteration은 safety valve일 뿐 비용 대비 가치나 품질 수렴을 보장하지 않는다.
- “Oracle verified”도 Oracle이 읽은 evidence와 independent test가 없으면 자기평가다.

### 판단

LazyCodex에서 가져올 것은 **Codex adapter와 명령 naming 참고**뿐이다. loop semantics와 model routing은 OmO 항목에서 한 번만 다룬다. 자체 skill은 Claude/Codex 공통 SKILL.md core와 얇은 host adapter로 구성해 설치 의존성을 줄인다.

## 6. OmO (oh-my-openagent)

### 실제 workflow

공식 orchestration guide 자체에 triage가 있다.

- simple/quick/single-file: 그냥 prompt.
- complex but context 설명이 번거로움: `ulw`/`ultrawork`.
- precise, multi-step, verifiable: Prometheus plan → `/start-work` Atlas execution. [decision flow](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/orchestration.md#tldr---when-to-use-what)

정밀 경로에서는 Prometheus가 interview와 research를 반복하고, core objective, scope boundary, critical ambiguity, technical approach, test strategy가 명확한지 검사한다. Metis가 mandatory gap analysis를 하고, 선택된 high-accuracy path에서는 Momus와 Oracle이 둘 다 승인할 때까지 plan을 고친다. Atlas가 plan을 읽어 category-routed worker와 specialist에게 작업을 보낸다. [planning flow](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/orchestration.md#planning-prometheus--metis--momus--oracle)

`ralph-loop`는 `<promise>DONE</promise>`, max iterations(기본 100), cancel 중 하나로 끝나며 `ulw-loop`는 여기에 ultrawork의 병렬 탐색을 더한다. [feature reference](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/reference/features.md#commands)

### 장점

- 사용자가 원한 triage → plan → goal/ultrawork escalation과 가장 가까운 사례다.
- planner, plan critic, orchestrator, worker, read-only consultant 역할이 분리되어 있다.
- category가 “어떤 model/tool이 필요한가”를 task 성격에 맞춰 배정한다.
- explore/librarian 같은 read-only research와 executor를 분리한다.

### 단점

- agent 11개, hook 54개 이상, 여러 MCP와 fallback chain은 기능 간 상호작용과 장애 표면을 크게 만든다.
- `ultrawork`는 편하지만 문제 정의가 틀린 상태에서 parallel exploration을 크게 증폭할 수 있다.
- completion promise는 모델이 출력할 수 있는 문자열이므로 독립적인 완료 증거가 아니다.
- task category와 role 이름이 많으면 실제 책임보다 routing configuration 유지가 커진다.

### 채용 / 배제

채용:

- 세 단계 triage.
- planner read-only, executor write-capable, reviewer clean-session/read-only의 권한 분리.
- `quick`, `execute`, `deep-reason`, `research`, `adversarial-review` 정도의 작은 category set.
- coordinator는 최고 reasoning model, 반복 worker는 cost/quality에 맞는 model이라는 원칙.

배제:

- 역할별 신화 이름과 전체 agent inventory.
- hook 기반 자동 continuation을 완료의 주된 보장으로 사용.
- 검증 실패 원인이 같은데 iteration만 100/500회 반복.

## 7. 추가로 볼 가치가 큰 사례

### GitHub Spec Kit — 약 123k stars

핵심은 `Specify → Plan → Tasks → Implement`이며 각 단계의 Markdown artifact가 다음 단계의 입력이 된다. project constitution으로 architectural principles를 고정하고, 여러 coding agent integration을 같은 process에 연결한다. [official docs](https://github.github.com/spec-kit/), [repository](https://github.com/github/spec-kit)

- 차용: artifact pipeline, constitution/guardrails, cross-artifact consistency check.
- 주의: greenfield와 큰 feature에 강하지만 사소한 brownfield 수정에는 artifact가 무겁다. constitution을 코드보다 상위 truth로 지나치게 두면 실제 code/runtime drift를 늦게 반영할 수 있다.

### OpenSpec — 약 61.8k stars

핵심은 현재 truth인 `openspec/specs/`와 proposed delta인 `openspec/changes/`를 분리하고, `explore → propose → apply → archive`로 변경을 합치는 것이다. brownfield에서 현재 규칙과 이번 변경을 구분하는 점이 좋다. [official repository](https://github.com/Fission-AI/OpenSpec)

- 차용: baseline contract와 amendment/delta 분리, 변경별 proposal/tasks/evidence 묶음.
- 주의: archive했다고 implementation이 자동으로 맞는 것은 아니다. archive 전 runtime verification gate가 필요하다.

### BMad Method — 약 50.9k stars

Analysis(optional) → Planning → Solutioning → Implementation의 4단계에서 산출물을 다음 단계 context로 넘기며, project scale에 따라 planning depth를 조절한다. PM, architect, developer, UX 등 specialist persona와 quick flow도 제공한다. [workflow map](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/workflow-map.md), [repository](https://github.com/bmad-code-org/BMAD-METHOD)

- 차용: task 규모에 따른 workflow depth 조절, optional discovery, quick flow.
- 주의: persona와 agile ceremony를 그대로 가져오면 solo workflow에 역할극과 문서가 과다해진다.

### snarktank/Ralph — 약 21.2k stars

PRD를 small user stories가 든 `prd.json`으로 바꾼 뒤 매 iteration에 fresh AI process가 최고 우선순위의 `passes:false` story 하나만 처리한다. 통과하면 commit, story status, append-only `progress.txt`를 갱신한다. 모든 story가 `passes:true`이거나 max iterations에 도달하면 끝난다. memory는 Git, progress, PRD 세 가지뿐이다. [official repository](https://github.com/snarktank/ralph)

- 차용: **fresh context per small task**, Git + compact progress + task state의 최소 memory, hard cap.
- 주의: `passes:true`를 agent가 자기 선언하지 않도록 acceptance command와 artifact를 coordinator가 확인해야 한다. append-only progress가 길어지면 active summary를 재생성해야 한다.

## 8. 종합 설계에 반영할 패턴

### 가져올 것

| 설계 문제 | 차용 원천 | 우리 loop에 넣을 최소 형태 |
|---|---|---|
| 시작 경로 선택 | OmO, BMad | `simple / planned / durable-loop` 3단계 |
| 모호성 축소 | Ouroboros, gstack office-hours | critical unknown 중심의 Socratic questions; 점수 없음 |
| 계약 표현 | Ouroboros Seed, OpenSpec delta | cycle baseline + explicit amendments + acceptance checks |
| context rot 억제 | GSD, Ralph, Superpowers | task마다 fresh worker; compact task packet; result artifact |
| 계획 검토 | Superpowers, OmO | spec compliance 먼저, execution feasibility 다음 |
| 프리모템 | gstack Codex adversarial | 새 session/다른 model, read-only, evidence-required |
| 병렬화 | GSD waves, OmO category | dependency와 file ownership이 독립일 때만 fan-out |
| 완료 | Ralph + verification-before-completion | acceptance별 runnable evidence + no blockers + hard budgets |
| 간결성 | Ponytail | execution 단계의 implementation policy |
| stale state | pi-hashline-edit | contract/ledger/base commit fingerprint precondition |

### 가져오지 않을 것

- 근거가 교정되지 않은 ambiguity/quality score.
- ontology stability를 사용자 가치 또는 correctness와 동일시하는 종료 규칙.
- 초기 버전의 DB EventStore, MCP daemon, TUI, dashboard.
- 역할 하나당 agent 하나를 만드는 persona explosion.
- 모든 task에 strict TDD, worktree, 다중 reviewer를 강제하는 ceremony.
- `DONE` 문자열이나 todo checkbox만으로 완료를 선언하는 loop.
- 실패 원인이 변하지 않은 상태에서 계속 재시도하는 “persistence”.

## 9. 현재 채택한 loop 종료 원칙

Landscape의 다양한 recovery 상태는 실제 UAT 전에는 채택하지 않는다.

정상 완료는 모두 만족해야 한다.

1. 모든 required acceptance criterion이 `verified`이고 각 항목에 command/output 또는 사람이 확인한 evidence가 있다.
2. ledger에 unresolved `critical` unknown/blocker가 없다.
3. delegated input이나 accepted artifact의 fingerprint가 current state와 같다.

다음 중 하나면 성공이 아니라 정지·보고한다.

- task iteration, wall-clock, token/cost budget 중 하나 소진.
- contract amendment가 필요하지만 사용자의 authority가 필요한 경우.
- 외부 서비스, credential, hardware 등 현재 session에서 해소할 수 없는 blocker.

Machine state는 `CONTINUE`, `STOP_SUCCESS`, `STOP_BUDGET`, `STOP_SAFETY`,
`STALE_INPUT`만 둔다. Premortem/review가 필요한 변경은 finding을 unknown 또는
acceptance로 변환한다. 별도 recovery state는 실제 run이 구분 필요성을 보일 때 추가한다.

## 주요 근거 링크

- [Ouroboros README](https://github.com/Q00/ouroboros)
- [Ouroboros architecture](https://github.com/Q00/ouroboros/blob/main/docs/architecture.md)
- [gstack README](https://github.com/garrytan/gstack)
- [Superpowers README](https://github.com/obra/superpowers)
- [GSD legacy repository and migration notice](https://github.com/gsd-build/get-shit-done)
- [GSD Core current repository](https://github.com/open-gsd/gsd-core)
- [LazyCodex README](https://github.com/code-yeongyu/lazycodex)
- [OmO orchestration guide](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/orchestration.md)
- [OmO feature reference](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/reference/features.md)
- [GitHub Spec Kit](https://github.com/github/spec-kit)
- [OpenSpec](https://github.com/Fission-AI/OpenSpec)
- [BMad workflow map](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/workflow-map.md)
- [Ralph](https://github.com/snarktank/ralph)
