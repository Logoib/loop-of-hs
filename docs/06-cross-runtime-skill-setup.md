# Claude·Codex 공용 `loop-code` 구성

- canonical source: `.agents/skills/loop-code`
- Claude discovery: `.claude/skills/loop-code` junction
- local Claude version: `2.1.216`
- local Codex version: `0.144.6`

## 구조

```text
.agents/skills/loop-code/
├─ SKILL.md
├─ agents/openai.yaml
├─ assets/{loop-ledger,task-packet}.template.json
├─ references/{ledger-contract,runtime-routing}.md
└─ scripts/loopctl.py

.claude/skills/loop-code -> .agents/skills/loop-code
```

## Discovery scope

2026-07-21에 다음을 확인했다.

| Runtime | repository discovery | user-global install | 확인 수준 |
|---|---|---|---|
| Codex | `.agents/skills/loop-code` | 없음 | 현재 Codex session의 available skill로 노출 |
| Claude Code | `.claude/skills/loop-code` junction | 없음 | `/loop-code` read-only smoke test 통과 |

두 경로의 `SKILL.md` SHA-256은 같았다. `loop-code`는 아직 P0 실사용 전이므로
모든 repository에 영향을 주는 global junction은 만들지 않는다. 반복 사용 가치가
확인되기 전까지 repository-scoped skill로 유지한다.

Windows junction은 clone 또는 workspace 이동 뒤 project root에서 재생성한다.

```powershell
New-Item -ItemType Directory -Force -Path '.claude\skills' | Out-Null
New-Item -ItemType Junction `
  -Path '.claude\skills\loop-code' `
  -Target (Resolve-Path '.agents\skills\loop-code')
```

## Codex context 설정

API 모델 maximum과 Codex client/session budget을 구분한다.

| 계층 | 2026-07-21 확인값 |
|---|---:|
| GPT-5.6 Sol/Terra API maximum | 1,050,000 |
| Codex 0.144.6 client catalog | 272,000 |
| session reported budget (`95%`) | 258,400 |
| 사용자 soft cap | 150,000 |

이 환경에서는 `model_context_window=1050000`을 전역 config에 넣어도 최근 session
budget이 258,400이었다. 따라서 stale override를 제거하고 실제
`~/.codex/config.toml`을 다음처럼 설정했다.

```toml
model = "gpt-5.6-sol"
model_reasoning_effort = "xhigh"
plan_mode_reasoning_effort = "xhigh"
model_auto_compact_token_limit = 150000
model_auto_compact_token_limit_scope = "total"
```

위 다섯 값은 2026-07-21 실제 user-global config에서 다시 확인했다. Claude Code의
user-global 설정은 `effortLevel: "xhigh"`였으며, `loop-code` 자체는 양쪽 runtime
모두 global skill로 설치되어 있지 않다.

150K는 universal quality cliff가 아니라 사용자 선택 checkpoint/compaction
정책이다. 변경은 새 Codex session부터 확인한다. Current catalog와 `/status` 또는
session log가 config 주장보다 우선한다.

## 호출과 routing

Codex persistent run:

```text
/goal Use $loop-code to achieve: <한 줄 목표>
```

Claude Code:

```text
/loop-code <한 줄 목표>
```

권장 역할은 coordinator/plan/premortem/final review에 Sol `xhigh`, 어려운 구현에
Sol `high`, read-heavy worker에 Terra `xhigh`다. `ultra`는 기본 사용하지 않는다.
현재는 별도 custom agent profile을 만들지 않았으므로 worker별 모델 분리는 runtime
라우팅 요청이며 강제 설정이 아니다. 실제 UAT에서 상속 문제가 확인될 때만 agent
profile을 추가한다.

## 검증 수준

- 확인: Codex repository skill discovery, Claude `/loop-code` read-only discovery,
  junction identity/hash, user-global Codex config, skill schema, JSON parsing,
  controller unit self-test, command evidence, stale artifact rejection, five-state stop
- 미확인: 실제 변경을 수행하는 Claude/Codex workflow UAT, worker별 model routing,
  150K compaction 후 handoff 품질, real Vue/NX/Flomaster task

Discovery smoke test나 controller self-test를 workflow correctness PASS로 부르지
않는다. 특히 artifact 없는 command evidence는 source drift를 감지하지 못하는 현재
한계가 있다.
