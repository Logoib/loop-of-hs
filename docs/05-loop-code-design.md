# Loop Code 최소 설계 v0.4

- 작성일: 2026-07-21
- 대상: 대규모 웹앱의 cross-component 변경, NX/Flomaster 제어 코드
- 상태: controller self-test 완료, 실제 프로젝트 UAT 미완료

## 1. 목표 우선 진입

사용자는 완성된 SPEC 대신 한 줄 목표로 시작한다. Coordinator가 아래 순서로
top-down 전개한다.

```text
goal
→ Direct / Plan / Loop triage
→ Loop이면 ledger 자동 생성
→ blocking unknown만 탐색
→ plan
→ 위험할 때만 fresh-context premortem
→ implement
→ command/human verification
→ five-state stop gate
```

검증이 plan을 무효화했을 때만 재계획한다. Premortem은 매 반복이 아니라
irreversible/persisted 변경, shared migration, NX/Flomaster write, 단위·좌표·물성,
silent corruption, 불명확한 rollback에만 수행한다. 이때 같은 frozen task packet을
받은 fresh Thesis와 Anti-thesis를 독립 실행한 뒤, Synthesis가 두 결과를 contract와
verifier에 대조한다. 살아남은 finding만 unknown 또는 acceptance criterion으로
흡수한다. Candidate artifact 이후에는 Codex에서 `$claude-adversarial-review`,
Claude Code에서 `/codex:adversarial-review`로 한 차례 교차 검토한다.

Codex의 한 줄 시작 예시는 다음과 같다.

```text
/goal Use $loop-code to achieve: <목표>
```

## 2. 최소 제어면

유지하는 것은 네 가지다.

1. Direct/Plan/Loop triage
2. durable ledger와 bounded task packet
3. command evidence
4. contract/scoped-file fingerprint

`standard/high` mode와 별도 premortem/review state를 두지 않는다. 위험한 변경에는
rollback을 기록하고, premortem/review 결과를 critical unknown 또는 acceptance
criterion으로 바꾼다. 실제 run이 별도 제어 상태의 필요성을 보여줄 때만 추가한다.

Ponytail의 runtime 적용 범위는 frozen acceptance 이후 코드 생성뿐이다. 다만 이
skill 자체를 유지보수할 때는 YAGNI를 적용해 사용되지 않은 상태·문서·hook을
제거한다.

## 3. Ledger

[ledger template](../.agents/skills/loop-code/assets/loop-ledger.template.json)은
objective, scope/interfaces, workspace/protected input/rollback, authority, finite limits,
acceptance, unknowns, decisions, handoff만 유지한다. Command verifier는 shell string이
아닌 argv array다. 자세한 record는
[ledger contract](../.agents/skills/loop-code/references/ledger-contract.md)에 있다.

## 4. `loopctl.py`

[loopctl.py](../.agents/skills/loop-code/scripts/loopctl.py)는 Python 표준 라이브러리로
세 기능만 제공한다.

- `fingerprint capture/verify`: contract, exact files, 선택적 Git HEAD 검증
- `run`: verifier 실행, exit/output/artifact SHA와 workspace/protected-input fingerprint 기록
- `stop`: current evidence를 다시 확인하고 아래 다섯 상태 계산

| state | 의미 |
|---|---|
| `STOP_SUCCESS` | 모든 acceptance의 current evidence가 통과하고 critical unknown 없음 |
| `STOP_BUDGET` | 명시된 iteration/deadline 도달 |
| `STOP_SAFETY` | 권한·data-loss·destructive·security 경계 |
| `STALE_INPUT` | contract/workspace/input/verifier/artifact가 evidence와 불일치 |
| `CONTINUE` | 검증 가능한 다음 slice가 남음 |

위험한 unknown 때문에 다음 행동을 할 수 없으면 `authority.blocked=true`로
`STOP_SAFETY`를 사용한다. Recovery, uncertainty, refresh를 별도 enum으로 만들지
않고 ledger handoff와 한국어 보고에 원인을 남긴다.

## 5. 적용 예

- 문구/CSS 한 곳: Direct
- component 내부 bounded bug: Direct 또는 Plan
- page + store + API + shared type: Loop 후보
- auth/schema/migration/persisted state: Loop + rollback/premortem/review
- NX/Flomaster write: Loop + 원본 복사, version/input hash, 단위·좌표·물성,
  run/export evidence, recovery 확인

## 6. Context 운영

큰 API window를 작업 메모리 목표로 삼지 않는다. Runtime이 제공하는 session budget과
사용자가 설정한 soft cap을 따로 기록하고, phase boundary·compaction·반복 탐색·모순
시 ledger checkpoint에서 fresh context로 재개한다. 2026-07-21 Codex runtime snapshot과
150K 설정은 [context 문서](./04-context-rot-and-stop-criteria.md)와
[cross-runtime setup](./06-cross-runtime-skill-setup.md)에 둔다.

## 7. 검증 경계와 다음 행동

현재 통과한 것은 controller unit self-test, JSON/schema, command evidence,
stale-artifact rejection, junction identity다. 이것은 workflow usefulness를 증명하지
않는다.

다음 개발 작업은 framework 기능 추가가 아니라 실제 Vue 변경 1건이다. 각 gate의
사용 여부, ceremony 시간, 발견한 오류, 재작업 감소를 기록한다. 이후 NX/Flomaster
변경을 수행하고, 반복해서 필요했던 상태나 adapter만 추가한다.
