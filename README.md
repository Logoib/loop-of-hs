# loop-of-hs

[English](./README.en.md) · **한국어**

복잡한 코드 변경을 **ledger 기반 loop**로 처리하는 Claude Code · Codex 공용 skill
(`loop-code`)과 그 설계 근거 문서를 담은 저장소다.

대화 요약이 아니라 저장소 안의 JSON ledger를 정본 상태로 두고, 완료 여부는 모델의
자기평가가 아니라 **명령 실행 증거(command evidence)** 와 **입력 fingerprint** 로
판정한다. 세션은 언제든 교체 가능한 작업 메모리로 취급한다.

- canonical source: [`.agents/skills/loop-code`](./.agents/skills/loop-code)
- 현재 버전: `loop-code` v0.4 (Claude Code / Codex 공용)
- 대상 작업: 대규모 웹앱의 cross-component 변경, 마이그레이션, 공유 계약 변경,
  NX·Flomaster 같은 외부 애플리케이션 제어 코드
- 상태: controller self-test 통과, **실제 프로젝트 UAT 미완료**
  (아래 [검증 상태](#검증-상태) 참고)

## 저장소 구조

```text
.agents/skills/loop-code/
├─ SKILL.md                      # 워크플로 본문 + Stop hook frontmatter
├─ agents/openai.yaml            # Codex 표시 메타데이터
├─ assets/
│  ├─ loop-ledger.template.json  # ledger 템플릿 (schema_version 4)
│  └─ task-packet.template.json  # 위임용 bounded task packet
├─ references/
│  ├─ ledger-contract.md         # ledger 초기화·복구 시에만 읽는 계약
│  ├─ runtime-routing.md         # Loop 선택 후에만 읽는 runtime/모델 라우팅
│  └─ v4-review.md               # v4 계약 변경 근거와 검증 범위
├─ scripts/loopctl.py            # 표준 라이브러리만 쓰는 controller
└─ tests/test_loopctl.py         # controller 회귀 테스트

docs/                            # 설계 결정과 조사 근거 (한국어)
```

## 설치

canonical source는 `.agents/skills/loop-code` 하나이고, 각 runtime의 discovery 경로는
junction으로 같은 디렉터리를 가리킨다. clone 후 또는 workspace를 옮긴 뒤 프로젝트
루트에서 실행한다.

```powershell
# 프로젝트 스코프 (Claude Code)
New-Item -ItemType Directory -Force -Path '.claude\skills' | Out-Null
New-Item -ItemType Junction -Path '.claude\skills\loop-code' -Target (Resolve-Path '.agents\skills\loop-code')

# 사용자 전역
New-Item -ItemType Junction -Path "$HOME\.claude\skills\loop-code" -Target (Resolve-Path '.agents\skills\loop-code')
New-Item -ItemType Junction -Path "$HOME\.codex\skills\loop-code" -Target (Resolve-Path '.agents\skills\loop-code')
```

Codex는 저장소의 `.agents/skills/loop-code`를 직접 discovery하므로 프로젝트 스코프
junction이 필요 없다. `.claude/skills/loop-code`와 `.loop/`는 `.gitignore`에 있다.
설치 확인:

```bash
python .agents/skills/loop-code/scripts/loopctl.py --self-test   # SELF_TEST_OK
```

## 호출

```text
Codex:       $loop-code <한 줄 목표>
Claude Code: /loop-code <한 줄 목표>
```

완성된 SPEC 문서가 아니라 **한 줄 목표**로 시작한다. 명세를 만드는 것은 사용자가
아니라 coordinator이고, 그 산출물은 별도 문서가 아니라 ledger다.

## 실행 흐름

```text
goal
→ Direct / Plan / Loop triage
→ (Loop) ledger 자동 생성
→ blocking unknown만 탐색
→ (Loop) blueprint 확인 게이트 1회
→ plan
→ (위험할 때만) fresh-context premortem
→ implement
→ command / human verification
→ round 카운터 갱신
→ six-state stop gate
```

## 1. 트라이지 — Direct / Plan / Loop

결과를 검증할 수 있는 **가장 작은 lane**을 고른다. 프로젝트 규모 자체는 Loop 선택
근거가 아니다. lane과 그 이유는 한국어로 알리고, 증거가 현재 lane을 무효화할 때만
상향한다.

| Lane | 조건 | 산출물 |
|---|---|---|
| **Direct** | 로컬·되돌릴 수 있음, 검증자가 하나로 명확 | 변경 + 검증 실행 |
| **Plan** | 한 세션이 끝낼 수 있는 여러 의존 단계 | 단계 계획 + 검증 |
| **Loop** | 세션·컴포넌트를 넘는 작업, 공유 계약, 외부 애플리케이션 상태, 반복 수렴, 롤백/silent corruption 위험 | ledger + 증거 + stop gate |

적용 예시:

- 문구/CSS 한 곳 → **Direct**
- 컴포넌트 내부 bounded bug → **Direct** 또는 **Plan**
- page + store + API + shared type → **Loop** 후보
- auth/schema/migration/persisted state → **Loop** + rollback/premortem/review
- NX·Flomaster write → **Loop** + 원본 복사, version/input hash, 단위·좌표·물성,
  run/export evidence, recovery 확인

이 세 갈래는 OmO의 분류를 단순화한 것이다
([docs/02 결론 1](./docs/02-loop-landscape-comparison.md)).

## 2. 블루프린트 인터뷰 게이트

Loop lane에만 있는 **1회** 게이트다. Loop이 예산을 쓰게 될 acceptance criteria는
합의된 것이 아니라 추론된 것이므로, 첫 mutation 전에 한 번 사용자에게 되돌린다.

동작 순서:

1. coordinator가 코드·테스트·이력·문서·안전한 probe로 ledger를 **먼저** 채운다.
   사용자에게 SPEC 작성을 요구하지 않는다.
2. 채운 초안을 출력한다 — objective, scope in/out과 interfaces, **각 acceptance
   criterion과 그 verifier 명령**, limits. 이 초안 자체가 사용자가 반응할
   blueprint이고 별도 mockup을 만들지 않는다.
3. 같은 라운드에서 저장소가 답하지 못한 것만 묻는다 — 의도, 우선순위, 제약,
   brownfield 동작. 질문마다 **그 답이 확정하는 ledger 필드**를 밝히고, 어떤 필드도
   바꾸지 않는 질문은 생략한다.
4. 접근법이 diff 모양 수준에서 갈릴 때는 후보 코드 조각을 선택지 안에 넣어
   (Claude Code에서는 질문 옵션의 `preview` 필드) 설명이 아니라 산출물을 비교하게
   한다.
5. scope·acceptance·limits가 확정되면 게이트가 닫힌다. LLM 자기채점 clarity 점수는
   통과 조건으로 쓰지 않는다.

인터뷰 phase가 아니라 **한 라운드**다. 최종 게이트의 `user_accepted`는 예산을 이미
쓴 뒤에 도착하므로 방향을 바꾸는 데 쓸 수 없다.

근거는 Ouroboros의 Socratic interview를 차용하되 자기채점 ambiguity 게이트는 버린
[docs/02 결론 2](./docs/02-loop-landscape-comparison.md), 그리고 자족적 spec이
"관련 파일·인터페이스 지목 / 범위 밖 명시 / end-to-end 검증으로 종료"여야 한다는
Anthropic best-practices의 "Let Claude interview you"다. 이 셋이 각각
`scope.in`·`scope.interfaces`, `scope.out`, acceptance verifier에 대응하므로 별도
SPEC 문서를 만들지 않고 ledger가 그 역할을 한다.

## 3. Unknown 관리와 KG lookup

유용한 불확실성만 기록한다.

| 분류 | 의미 |
|---|---|
| **KK** | provenance가 있는 검증된 사실 |
| **KU** | 명시적 질문 + 가장 싼 결정적 probe |
| **UK** | 코드·테스트·이력·문서·도구·사용자에게 있을 가능성이 큰 지식 |
| **UU** | blind-spot 가설 + 반증 probe |

부서 공용 KG wiki는 재사용 가능한 절차·용어·설계 근거·교훈의 source of truth이지만,
저장소 코드/테스트, 라이브 외부 상태, 현재 사용자 결정을 덮어쓰지 않는다. 사용자에게
묻거나 부서 규칙을 ledger에 옮기기 전에 `kg-lookup`을 **just in time**으로 호출한다.
coordinator가 모든 작업을 미리 검색하지 않고, KG 접근 권한이 있는 worker가 직접
호출한다. 아무것도 찾지 못하면 그 공백을 unknown으로 기록한다.

안전·frozen contract·병렬 작업 일관성에 필수인 KG 사실만 preload해서 task packet의
`facts`에 짧은 진술과 wiki 경로로 넣는다. 그 노트 스냅샷이 고정돼야 하면 노트 경로를
`fingerprint` scope에 포함시켜 SHA-256을 함께 잡는다. 노트 본문이나 검색 기록을
ledger에 복사하지 않고, retrieval manifest나 별도 KG-staleness 상태는 실제 run이
필요를 보여줄 때까지 추가하지 않는다.

## 4. Ledger

Loop은 `.loop/<yyyyMMdd-HHmmss>-<short-slug>/loop-ledger.json`을 만든다(충돌 시
`-2`, `-3`). 유지하는 필드는 objective, scope/interfaces, workspace/protected
input/rollback, authority, finite limits, acceptance, unknowns, decisions,
handoff뿐이다.

핵심 규칙:

- 새 ledger는 **schema_version 4**로 만든다. v3는 in-memory 정규화로 읽기만 하고,
  ledger를 바꾸는 명령은 v3를 거부한다. 원본 v3 파일은 다시 쓰지 않는다.
- `baseline.workspace`를 명시한다. `.loop/<task-id>/loop-ledger.json` 기준으로 보통
  `../..`가 프로젝트 루트다. 빈 템플릿은 의도적으로 불완전하다.
- `limits.max_iterations`와 `limits.deadline` 중 **최소 하나**는 null이 아니어야
  한다.
- verifier는 shell 문자열이 아니라 **argv 배열**이다.
- verifier가 쓰는 모든 정확한 source/test/config/고정 지식 노트를
  `baseline.protected_inputs`에 나열한다. 디렉터리와 선언되지 않은 의존성은
  의도적으로 freshness 경계 밖이다.
- critical unknown은 non-empty evidence 없이 `verified`/`falsified`/`resolved`가 될
  수 없고, `accepted-risk`는 `user_accepted: true`를 함께 요구한다.
- ledger writer는 coordinator 하나다. ledger를 바꾸는 `loopctl.py` 명령은 직렬
  실행한다. atomic replacement는 부분 파일을 막을 뿐 multi-writer lock이 아니다.

acceptance / unknown 레코드의 정확한 모양은
[ledger-contract.md](./.agents/skills/loop-code/references/ledger-contract.md)에 있다.

## 5. `loopctl.py`

Python 표준 라이브러리만 쓰는 controller. 기능은 네 가지다.

```bash
# 계약 + 정확한 파일 + (선택) Git HEAD 스냅샷
python <skill-root>/scripts/loopctl.py fingerprint capture \
  --ledger <ledger> --workspace <workspace> --scope <paths...> [--pin-head] [--output <snapshot>]
python <skill-root>/scripts/loopctl.py fingerprint verify \
  --ledger <ledger> --snapshot <snapshot> [--workspace <workspace>]

# acceptance 실행: exit/output/artifact SHA + workspace·protected-input fingerprint 기록
python <skill-root>/scripts/loopctl.py run <ledger> --acceptance <AC-ID> [--output <evidence.json>]

# bounded round 하나를 끝냈다고 표시: controller가 progress.iteration을 올린다
python <skill-root>/scripts/loopctl.py round <ledger>

# 현재 증거를 다시 확인하고 여섯 상태 중 하나 계산
python <skill-root>/scripts/loopctl.py stop <ledger> [--json]

python <skill-root>/scripts/loopctl.py --self-test
```

명령은 **argv 배열**로 정의하고 따옴표 없는 shell 문자열로 실행하지 않는다. `run`은
증거 파일을 `<ledger-dir>/evidence/`에 쓰고 ledger를 원자적으로 갱신한다. command
evidence는 손으로 편집하지 않는다.

출력과 종료 코드:

| 명령 | 출력 | 종료 코드 |
|---|---|---:|
| `fingerprint verify` | `MATCH` / `STALE_INPUT <mismatches>` (`--json`이면 differences) | 0 / 33 |
| `run` | `VERIFY_PASS`\|`VERIFY_FAIL` + AC-ID + 증거 경로 | 0 / 4 |
| `round` | `ROUND <iteration>/<max\|->` | 0 |
| `stop` | `STOP_SUCCESS` | 0 |
| `stop` | `CONTINUE` | 10 |
| `stop` | `WAITING_HUMAN` | 20 |
| `stop` | `STOP_BUDGET` | 31 |
| `stop` | `STALE_INPUT` | 33 |
| `stop` | `STOP_SAFETY` | 40 |
| 모든 명령 | `INVALID_INPUT <error>` (stderr) | 64 |

`run`은 declared artifact가 해시되지 않을 때뿐 아니라 **declared protected input이
더 이상 해시되지 않을 때**도 실패로 기록한다. 사라지거나 옮겨진 입력은 통과가 아니라
결측 입력이다.

## 6. 여섯 개 stop 상태

각 bounded round 뒤 `round`로 `progress.iteration`을 갱신하고 `stop --json`을 실행해
나온 상태를 따른다. iteration 한도는 `round`를 호출할 때만 강제되고, deadline과
명시적 `control.budget_exhausted`는 그와 무관하게 강제된다. 상태 우선순위는
`STOP_SAFETY` → `STALE_INPUT` → `STOP_SUCCESS` → `WAITING_HUMAN` → `STOP_BUDGET` →
`CONTINUE`다.

| state | 의미 |
|---|---|
| `STOP_SUCCESS` | 모든 acceptance에 current evidence가 있고 critical unknown 없음 |
| `WAITING_HUMAN` | 남은 acceptance가 전부 human gate라 모델이 더 진행할 수 없음 |
| `STOP_BUDGET` | 명시된 iteration/deadline 경계 도달 |
| `STOP_SAFETY` | 권한·data-loss·destructive·security 경계 |
| `STALE_INPUT` | contract/workspace/input/verifier/artifact가 증거와 불일치 |
| `CONTINUE` | 감당 가능한 다음 slice가 하나 남음 |

미해결 unknown 때문에 다음 행동이 안전하지 않으면 `authority.blocked`를 세우고
안전하게 멈춘다. 실제 run이 별도 처리를 요구하기 전에는 상태를 추가하지 않는다.

## 7. 증거와 freshness 경계

- command evidence의 freshness는 contract(workspace 포함), verifier 정의,
  `baseline.protected_inputs`, declared artifact를 덮는다.
- human verifier는 안전한 명령·파일·API·테스트로 결과를 관찰할 수 없을 때만 쓴다.
  `user_accepted: true`는 **사용자만** 설정할 수 있고 모델 관찰이 대체하지 않는다.
  protected input이나 검토 대상 artifact가 있으면 검토 후 그 합집합에 대해
  fingerprint를 한 번 잡아 `fingerprint_snapshot`에 저장한다. 그래야 이후의
  파일·계약·workspace 변경이 그 승인을 stale로 만든다.
- `stop`은 verifier를 다시 실행하지 않고, 라이브 외부 애플리케이션 상태를 관찰하지
  않으며, 선언되지 않은 입력을 해시하지 않는다. 선언 경계 밖 변경 뒤에는 해당
  acceptance를 다시 실행한다.
- lint와 정적 타이핑은 source-level 규칙을 볼 뿐 runtime JSON이나 workflow 상태를
  검증하지 않는다. controller는 ledger 모양과 상태 불변식을, 각 verifier는 산출된
  결과를 검증한다.
- NX·Flomaster 작업에는 version, input/output identity, 단위, 좌표·물성 semantics,
  외부 프로세스 결과, 원본 복구를 증거에 포함한다.

실패한 시도는 재시도 전에 분류한다 — stale contract/input, 결정적 verifier 실패,
일시적 인프라 실패. stale은 갱신하고, 결정적 실패는 구현을 바꾸고, 일시적 실패만
bounded하게 재시도한다. 무작정 재시도로 invalid를 pass로 바꾸지 않는다.

## 8. Premortem과 교차 리뷰

fresh-context premortem은 매 라운드가 아니라 되돌릴 수 없거나 영속되는 변경, 공유
마이그레이션, NX/Flomaster write, 단위·좌표·물성 semantics, 불명확한 rollback,
그럴듯한 silent corruption에만 수행한다.

하나의 frozen task packet을 두 파도로 나눠 fresh read-only 역할에 전달한다.

- **Thesis** — 최소 안전 계획과 그 불변식을 제안한다.
- **Anti-thesis** — 같은 packet을 받되 선호 계획과 그 논거는 받지 않고, 실패 사례와
  반증 probe를 나열한다.
- **Synthesis** — 둘 다 끝난 뒤 실행해 계약·verifier와 대조하고, 각 finding을
  수용 / 증거 기반 기각 / unknown 또는 acceptance criterion 전환 중 하나로 처리한다.

계획이나 계약이 실질적으로 바뀌었을 때, 또는 실패한 접근이 정말 다른 계획을 요구할
때만 premortem을 반복한다. candidate artifact가 생긴 뒤에는 **1회** 교차 provider
리뷰를 쓴다 — Codex에서 `$claude-adversarial-review`, Claude Code에서
`/codex:adversarial-review`. 저장소 내용을 다른 provider로 보내거나 상대 plan usage를
소비하기 전에 사용자 승인을 확인한다.

## 9. Host goal 메커니즘

skill을 명시적으로 호출하면 triage 전에 host의 goal 장치를 켠다. goal 활성화는 도구
권한·permission·안전 경계를 넓히지 않는다.

**Codex** — `get_goal`로 활성 goal을 확인해 재사용하고, 없으면 `create_goal`을
호출한다. `/goal`을 출력만 하거나 중첩 Codex CLI를 실행하지 않는다. 진짜 종료
상태에서 `update_goal`로 `complete`(또는 그 도구의 반복 blocker 규칙에 한해
`blocked`)를 기록한다.

**Claude Code** — `/goal`은 사용자 전용 내장 명령이라 assistant가 켤 수 없다. 설정
키·환경 변수·CLI 플래그·hook 어느 것도 대신 세워주지 않는다. 대신 두 장치를 쓴다.

1. `SKILL.md` frontmatter의 **prompt 기반 `Stop` hook**. 공식 문서상 `/goal` 자체가
   session-scoped prompt `Stop` hook의 wrapper이고, Claude Code는 skill 호출 시
   frontmatter hook을 등록해 그 세션 내내 유지한다(subagent hook만 컴포넌트 수명으로
   스코프된다). Loop은 여러 턴에 걸치므로 이 세션 스코프가 의도된 것이고
   `once: true`는 쓰지 않는다. hook은 `stop_hook_active`를 먼저 확인해 block cap에
   도달했으면 즉시 통과시키고, 그렇지 않으면 증거가 없을 때 같은 턴을 이어간다.
2. 사용자가 직접 거는 `/goal`. hook은 goal 객체가 아니라서 `◎ /goal active` 표시도,
   상태 조회도, `--resume` 복원도 없다. 그래서 triage가 Plan 또는 Loop을 고르면
   붙여넣기용 한 줄을 정확히 한 번 출력하고, 답을 기다리지 않고 진행한다. 두 장치가
   함께 있는 이유도 한 번만 말한다 — hook은 이 세션만 살고, 사용자가 건 `/goal`은
   턴을 넘어 지속되며 `--resume`을 견디고 multi-session Loop을 실제로 지탱한다.

goal 조건은 그것을 읽을 평가자를 위해 쓴다. 작고 빠른 모델이 매 턴 뒤에 실행되며
**대화가 이미 보여준 것만** 판단한다. 명령을 실행하거나 파일을 읽지 않는다. 따라서
관찰 불가능한 속성(`코드가 정확함`)이 아니라 이 세션이 출력해야 할 것
(`selftest.py 를 돌려 SELFTEST_PASS 를 출력`)으로 종료 상태를 적고, 도중에 바뀌면 안
되는 제약과 턴/시간 한계를 포함한다(최대 4,000자).

assistant는 goal이 켜졌는지 읽을 수 없다. 켜졌다고 주장하지 않는다. 신뢰할 수 없는
workspace, `disableAllHooks`, `allowManagedHooksOnly`에서는 `/goal`을 쓸 수 없고
ledger loop이 혼자 작업을 지탱한다.

출처: <https://code.claude.com/docs/en/goal> (확인: 2026-08-19)

## 10. Context 운영과 모델 라우팅

큰 API window를 작업 메모리 목표로 삼지 않는다. runtime이 주는 session budget과
사용자가 정한 soft cap을 따로 기록하고, phase boundary·compaction·반복 탐색·계약
모순·stale reuse·tool output 지배 시 ledger checkpoint에서 fresh context로 재개한다.
재개는 transcript 요약이 아니라 **ledger**에서 한다. 설정된 token cap은 운영 정책이지
보편적 품질 절벽이 아니다.

2026-07-21 확인값:

| 계층 | 값 |
|---|---:|
| GPT-5.6 Sol/Terra API maximum | 1,050,000 |
| Codex 0.144.6 client catalog | 272,000 |
| session reported budget (95%) | 258,400 |
| 사용자 soft cap | 150,000 |

역할별 권장 라우팅. 브랜드가 아니라 **역할**을 보존한다 — 가장 강한 coordinator,
위험이 클 때 독립 reviewer, bounded worker.

- **Codex** — coordination/plan/premortem/synthesis/final review에 GPT-5.6 Sol
  `xhigh`. acceptance가 명확하고 command로 검증 가능한 bounded 구현과 read-heavy
  탐색에는 Luna `max`(저비용 worker이지 low-latency worker가 아니다). 어렵거나 모호한
  구현, 약한 verifier, 외부·영속 상태, Luna의 결정적 실패에는 Sol `high`로 상향한다.
  독립적인 Sol `xhigh` 최종 게이트는 하나 남긴다. `ultra`는 기본 off.
- **Claude Code** — coordination에 Fable 5, 어려운 추론에 현재 Opus, bounded 구현·조사에
  현재 Sonnet(계정에서 사용 가능할 때). 직렬 수렴에는 scoped goal hook을 쓰고,
  dynamic workflow나 `ultracode`는 반복적인 fan-out/파이프라인에만 쓴다.

노이즈가 큰 탐색과 독립 리뷰에는 fresh subagent를, 동시 writer가 있을 때만 Git
worktree를 쓴다. 실제 run이 prompt 라우팅으로 부족함을 보이기 전에는 custom agent
profile을 추가하지 않는다.

## 설계 경계

hybrid harness다 — 스크립트는 기계적 증거를 검증하고, coordinator가 의미적 사실을
분류하고 그 스크립트를 호출한다. self-test는 controller를 검증할 뿐 workflow의
유용성을 증명하지 않는다.

- `standard/high` 모드, 별도 premortem/review state, ledger lock, triage 점수,
  user-acceptance 서명 체계를 두지 않는다. 실제 Vue/NX/Flomaster run이 반복되는
  실패를 드러내기 전에는 hook·state·framework layer를 추가하지 않는다.
- Ponytail(재사용 → stdlib/native → 설치된 의존성 → 최소 diff)은 runtime에서는
  acceptance가 frozen된 뒤 **코드 생성 단계에만** 적용한다. skill 유지보수에서는
  쓰이지 않는 요소를 제거하는 데 쓰되, runtime discovery·안전·검증·명시적 요구사항을
  줄이는 데는 쓰지 않는다.
- parser key와 enum은 영어로 유지한다. 자유 텍스트는 handoff가 가장 잘 되는 언어로
  쓰고, 사용자 보고는 한국어로 한다.
- triage 후와 각 게이트마다 보고한다 — 완료/현재 작업, acceptance 통과/전체,
  iteration/limit, blocking unknown, rollback 상태, 다음 증거. 완료 퍼센트를
  지어내지 않는다.

## 검증 상태

**확인됨** — Codex repository skill discovery, Claude `/loop-code` read-only
discovery, junction identity/hash, user-global Codex config, skill schema, JSON 파싱,
controller unit self-test, command evidence, stale artifact rejection,
source/workspace drift 재현, v4 schema 검증과 v3 read-only 정규화, six-state stop.

**미확인** — 실제 변경을 수행하는 Claude/Codex workflow UAT, worker별 model routing,
150K compaction 후 handoff 품질, 실제 Vue/NX/Flomaster task, 양 runtime의 user-global
discovery.

discovery smoke test나 controller self-test를 workflow correctness PASS로 부르지
않는다.

## 로드맵

- [x] `loop-code` controller 최소 구현
- [x] controller P0 freshness·ledger validation 보강
- [x] Loop lane blueprint 확인 게이트
- [ ] **P0** — 실제 Vue cross-component 변경 1건 UAT
- [ ] **P0** — 실제 NX/Flomaster 변경 1–2건 UAT
- [ ] **P1** — `loop-search` (로컬·KG·공식 web source 조사 loop)
- [ ] **P2** — `loop-report` (검증된 source bundle → 보고서/HTML/PDF/slide)
- [ ] **P3** — 필요가 확인되면 `loop-cae`

각 UAT run에서 사용된 gate, ceremony 시간, 발견한 오류, stale-input 발생, 재작업 감소,
쓰이지 않은 ledger field를 기록한다. 쓰이지 않은 field/state는 제거하고 반복된 실패를
막는 최소 장치만 추가한다. 실제 공통점이 확인되기 전에는 `loop-core` 추상화를 만들지
않는다. 자세한 내용과 보류 항목은
[08-loop-skill-roadmap.md](./docs/08-loop-skill-roadmap.md)에 있다.

## 문서

| 문서 | 역할 |
|---|---|
| [00-report-index.md](./docs/00-report-index.md) | 보고서 인덱스 |
| [05-loop-code-design.md](./docs/05-loop-code-design.md) | 현재 최소 설계 (운영) |
| [06-cross-runtime-skill-setup.md](./docs/06-cross-runtime-skill-setup.md) | runtime/config/junction (운영) |
| [08-loop-skill-roadmap.md](./docs/08-loop-skill-roadmap.md) | UAT-first TODO (운영) |
| [01-anthropic-cca-principles.md](./docs/01-anthropic-cca-principles.md) | Anthropic/CCA-F 원칙 조사 |
| [02-loop-landscape-comparison.md](./docs/02-loop-landscape-comparison.md) | 기존 loop framework 비교 |
| [03-ponytail-fingerprint-review.md](./docs/03-ponytail-fingerprint-review.md) | Ponytail 경계와 stale-input 원리 |
| [04-context-rot-and-stop-criteria.md](./docs/04-context-rot-and-stop-criteria.md) | context 연구와 runtime snapshot |
