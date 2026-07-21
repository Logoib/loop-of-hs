# Loop Skill Family 보고서 인덱스

- 작성일: 2026-07-21
- 현재 구현: Claude Code와 Codex 공용 `loop-code` v0.4
- 상태: controller 검증 완료, 실제 Vue/NX/Flomaster UAT 미완료

## 운영 문서

1. [05-loop-code-design.md](./05-loop-code-design.md) — 현재 최소 설계
2. [06-cross-runtime-skill-setup.md](./06-cross-runtime-skill-setup.md) — runtime/config/junction
3. [08-loop-skill-roadmap.md](./08-loop-skill-roadmap.md) — UAT-first TODO

## 조사 부록

| 문서 | 역할 |
|---|---|
| [01-anthropic-cca-principles.md](./01-anthropic-cca-principles.md) | Anthropic/CCA-F 원칙 조사 |
| [02-loop-landscape-comparison.md](./02-loop-landscape-comparison.md) | 기존 loop framework 비교 |
| [03-ponytail-fingerprint-review.md](./03-ponytail-fingerprint-review.md) | Ponytail 경계와 stale-input 원리 |
| [04-context-rot-and-stop-criteria.md](./04-context-rot-and-stop-criteria.md) | context 연구와 현재 runtime snapshot |

메타 비판 기록이었던 07과 재검토 prompt였던 09는 현재 설계에 반영한 뒤 제거했다.

## 현재 핵심

1. 한 줄 goal에서 Direct/Plan/Loop를 자동 triage한다.
2. Loop는 ledger, command evidence, fingerprint만 공통 core로 둔다.
3. Stop state는 `CONTINUE`, `STOP_SUCCESS`, `STOP_BUDGET`, `STOP_SAFETY`,
   `STALE_INPUT` 다섯 개다.
4. Rollback, premortem, independent review는 실제 위험이 있을 때 unknown 또는
   acceptance로 추가한다.
5. Ponytail은 runtime에서는 frozen acceptance 이후 코드 생성에만 적용하고,
   skill 유지보수에서는 사용되지 않은 framework 요소를 제거하는 데 적용한다.
6. 150K는 사용자 Codex soft cap이지 보편적인 context cliff가 아니다.

## 구현물

- [SKILL.md](../.agents/skills/loop-code/SKILL.md)
- [loop-ledger.template.json](../.agents/skills/loop-code/assets/loop-ledger.template.json)
- [task-packet.template.json](../.agents/skills/loop-code/assets/task-packet.template.json)
- [ledger-contract.md](../.agents/skills/loop-code/references/ledger-contract.md)
- [runtime-routing.md](../.agents/skills/loop-code/references/runtime-routing.md)
- [loopctl.py](../.agents/skills/loop-code/scripts/loopctl.py)

Controller unit self-test, JSON/schema, command evidence, stale artifact rejection,
five-state stop, junction identity는 확인했다. Workflow usefulness는 실제 UAT 뒤에만
판정한다.
