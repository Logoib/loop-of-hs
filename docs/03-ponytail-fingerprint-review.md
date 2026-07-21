# Ponytail and fingerprint review for the loop

> **문서 역할:** 도구 선택 근거 부록이다. 현재 구현은
> [05-loop-code-design.md](./05-loop-code-design.md)를 따른다.

작성일: 2026-07-21 (Asia/Seoul)
결론: **Ponytail은 구현 단계의 policy로 조건부 채용하고, pi-hashline-edit는 dependency가 아니라 stale-state 방지 원리만 채용한다.**

## 1. Ponytail은 loop에서 무슨 의미가 있는가

[Ponytail](https://github.com/DietrichGebert/ponytail)은 별도의 planner나 autonomous loop가 아니다. 코드를 쓰기 직전에 다음 ladder의 첫 번째 성립 지점에서 멈추게 하는 implementation policy다.

1. 이 기능 자체가 필요한가.
2. codebase에 이미 있는가.
3. standard library가 하는가.
4. native platform 기능이 하는가.
5. 이미 설치된 dependency가 하는가.
6. 한 줄로 충분한가.
7. 그때에만 최소 구현을 쓴다.

공식 규칙은 validation, data-loss prevention, security, accessibility를 축소하지 않고, bug에서는 모든 caller를 읽은 뒤 공통 root cause를 한 번 고치라고 한다. [README의 ladder와 safety boundary](https://github.com/DietrichGebert/ponytail#how-it-works)

2026-07-21 GitHub 조회 기준 약 86.6k stars다. 저장소 자체 benchmark는 FastAPI + React 실제 repo의 12개 feature task, Haiku 4.5, arm당 n=4에서 baseline 대비 평균 LOC 54%, token 22%, cost 20%, time 27% 감소와 safety 100%를 보고한다. 그러나 이는 저자 측 단일 benchmark suite이고 model/repo/task 유형이 제한되어 있으므로 일반 법칙으로 받아들이면 안 된다. README도 이전 single-shot의 80~94% 수치는 conversational padding 영향이 있었다고 정정한다. [benchmark summary와 한계](https://github.com/DietrichGebert/ponytail#numbers)

## 2. 장점

### Context budget을 직접 줄인다

작은 diff는 worker가 읽고 쓰는 token뿐 아니라 reviewer가 다시 읽을 code, test surface, integration risk를 함께 줄인다. context rot을 막는 가장 싼 방법은 더 좋은 compression보다 불필요한 code/artifact를 만들지 않는 것이다.

### 기존 codebase를 먼저 읽게 한다

Ponytail의 두 번째 rung인 “already in this codebase?”는 loop의 ledger와 잘 맞는다. worker는 새 helper를 만들기 전에 existing pattern을 evidence로 ledger에 올려야 한다. 이는 GSD/OmO류의 무분별한 parallel generation에서 흔한 중복 구현을 줄인다.

### root-cause fix를 선호한다

여러 caller에 guard를 복사하는 대신 shared function을 고치는 원칙은 diff와 future maintenance를 동시에 줄인다. 단, 이를 위해 caller search를 생략하지 않는다는 조건이 중요하다.

### deliberate shortcut에 ceiling을 남긴다

Ponytail의 `ponytail:` comment는 global lock, naive scan 같은 의도적인 한계와 upgrade trigger를 가까운 코드에 남긴다. 이것은 ledger의 accepted-risk 항목과 연결하기 좋다.

## 3. 단점과 실패 모드

### discovery를 너무 일찍 닫을 수 있다

프리모템, Socratic interview, architecture option generation은 일부러 가능성을 넓히는 단계다. 이때 “첫 번째 되는 최소해”를 강제하면 important unknown과 장기 failure mode를 찾기 전에 결론을 닫는다.

### non-functional requirement를 YAGNI로 오인할 수 있다

observability, migration path, compatibility, recovery는 지금 보이는 happy path의 최소 코드보다 길다. contract에 명시된 reliability/security/operability는 speculative abstraction이 아니므로 Ponytail이 삭제하면 안 된다.

### 작은 local diff가 작은 system change는 아니다

공통 function 한 줄 변경은 diff는 작아도 blast radius가 클 수 있다. caller search와 integration check를 생략하면 “lazy”가 아니라 검증 부족이다.

### Loop 판단에 섞으면 under-building 편향이 생길 수 있다

Ponytail을 triage·설계·검증에 사용하면 요구나 failure mode가 일찍 잘릴 수 있다.
따라서 acceptance criteria를 먼저 freeze하고, Ponytail은 **그 계약을 충족하는
코드를 생성하는 동안의 최소해**만 찾게 해야 한다.

## 4. 단계별 사용 결정

| Loop 단계 | Ponytail | 이유 |
|---|---|---|
| Triage | 끔 | loop 필요성은 blast radius와 검증 위험으로 판정 |
| Socratic interview / unknown reduction | 끔 | 질문 공간을 넓혀야 함 |
| Ledger 작성 | 끔 | known/unknown을 성급히 생략하지 않음 |
| Architecture option 탐색 | 끔 | alternatives와 failure mode를 먼저 봄 |
| Plan 확정 | 끔 | 구현 절약 정책이 계약 범위를 축소하지 않게 함 |
| Premortem / adversarial review | 끔 | 의도적으로 pessimistic하고 expansive해야 함 |
| Worker implementation | full | 최소 diff, reuse, root-cause fix의 주 무대 |
| Correctness/security review | 끔 | 누락을 찾는 reviewer가 축소 편향을 공유하지 않게 함 |
| 독립 complexity review | 끔 | 별도 loop ceremony로 만들지 않음 |
| Bug-fix code generation | full, caller search 필수 | 증상 patch 대신 공통 root cause 한 번 수정 |

## 5. Loop에 넣을 최소 규칙

Ponytail package 전체에 loop의 제어권을 주지 말고 executor task packet에 다음 네 줄의 policy를 넣으면 핵심 효과를 얻는다.

```text
Implementation policy:
- Satisfy the frozen acceptance criteria with the smallest correct diff.
- Reuse repository patterns, then stdlib/native features, then installed dependencies.
- For bugs, search all callers and fix the shared root cause when one exists.
- Do not simplify away validation, security, accessibility, recovery, or explicit requirements.
```

따라서 판단은 **조건부 채용**이다. 설치가 이미 되어 있거나 host가 plugin을 지원하면 execution worker에 `full`로 활성화할 수 있다. 자체 loop skill이 동작하기 위해 Ponytail을 필수 dependency로 만들 필요는 없다.

위 제한은 실행 중 사용자 요구와 검증 범위를 성급히 줄이지 않기 위한 것이다.
반대로 `loop-code` 자체를 유지보수할 때는 Ponytail을 적용해 실제 UAT에서 쓰이지
않은 state, schema, 문서를 제거한다.

## 6. pi-hashline-edit의 핵심 아이디어

[pi-hashline-edit](https://github.com/RimuruW/pi-hashline-edit)은 pi-coding-agent의 `read`와 `edit`를 교체한다. 2026-07-21 조회 기준 약 138 stars다.

`read` 결과의 각 줄은 `LINE#HASH:content` 형태다. 기본 hash는 2문자이며 최대 4문자로 설정할 수 있다. edit는 line number만 믿지 않고 hash anchor가 현재 내용과 맞는지 검증한다. 한 edit call의 모든 변경은 같은 pre-edit snapshot에서 검증한 뒤 아래쪽부터 적용된다. [README의 protocol](https://github.com/RimuruW/pi-hashline-edit#how-it-works)

중요한 세부사항은 다음과 같다.

- hash input에 `previous + current + next line`을 포함해 동일 문장이 다른 위치에 있어도 구분한다.
- 변경된 N번째 줄은 N-1, N, N+1 anchor만 무효화한다.
- stale anchor이면 3-way snapshot merge를 `fuzzFactor 0`으로 시도하고, 실패하면 조용히 relocation하지 않고 `E_STALE_ANCHOR`로 재읽기를 요구한다.
- 성공한 edit는 새 anchor를 돌려줘 다음 edit가 전체 파일을 다시 읽지 않게 한다.
- 같은 no-op edit가 세 번 반복되면 `E_NOOP_LOOP`로 막는다.
- temp-file + rename으로 atomic write하며 symlink/hardlink와 permission을 보존한다. [design decisions](https://github.com/RimuruW/pi-hashline-edit#design-decisions)

핵심은 hash 함수 자체가 아니라 다음 불변식이다.

> **An action may mutate state only if the state it read is still the state being mutated. Otherwise fail visibly and re-read.**

이는 optimistic concurrency control 또는 compare-and-swap과 같은 사고방식이다.

## 7. 우리 loop에 literal hashline을 넣을 가치가 있는가

**없다.** 이유는 다음과 같다.

- Claude Code와 Codex의 편집 tool surface가 다르므로 read/edit를 교체하면 공통 skill의 이식성이 떨어진다.
- line마다 짧은 hash를 prompt에 붙이면 모든 code read의 token tax가 된다.
- 2문자 hash는 context를 함께 쓰더라도 암호학적 identity가 아니다. 도구 내부 stale guard에는 충분할 수 있지만 durable contract identity로 부적합하다.
- 우리 문제는 주로 “줄 위치가 바뀜”보다 “다른 agent가 contract, plan, worktree를 바꿈”이라는 artifact/session 수준의 stale state다.
- 현재 host가 이미 patch precondition과 Git conflict를 제공한다면 같은 기능을 다시 만드는 것은 중복이다.

## 8. 차용한 fingerprint 설계

line fingerprint 대신 SHA-256과 선택적 Git HEAD로 **task packet 수준 precondition**만 둔다. 새 daemon이나 MCP는 필요 없다. v0.1에는 실행 코드가 없었고, 현재는 [loopctl.py](../.agents/skills/loop-code/scripts/loopctl.py)의 fingerprint command로 구현했다.

### Task packet 예시

```yaml
task_id: T-014
run_id: 20260721-001
fingerprint_snapshot: .loop/T-014/worker-fingerprint.json
scope:
  - src/payments/settle.py
  - tests/test_settle.py
dirty_input_allowed: false
acceptance:
  - id: AC-2
    verify: "pytest -q tests/test_settle.py"
```

최소 검증 절차:

1. coordinator가 frozen contract와 exact scoped file의 SHA-256을 capture한다. Git revision이 입력 계약의 일부일 때만 `--pin-head`를 쓴다.
2. worker는 시작 직전에 같은 값을 다시 계산한다.
3. 하나라도 다르면 edit하지 않고 `STALE_INPUT`과 현재 fingerprint를 반환한다.
4. coordinator가 최신 artifact로 packet을 재발행하거나 충돌 없는 새 worktree를 배정한다.
5. worker result에는 `observed_base`, `result_head`, changed paths, verification evidence를 기록한다.
6. clean-room reviewer는 result가 가리키는 동일 commit/diff와 동일 contract digest를 읽었는지 먼저 확인한다.
7. review 뒤 fingerprint가 바뀌었으면 이전 승인은 무효다.

### Git 유무와 scope 처리

전체 repository나 directory를 매번 hash하지 않는다.

- Git이 없어도 exact scoped file과 contract projection의 SHA-256으로 동작한다.
- Git commit까지 고정해야 할 때만 `--pin-head`로 `HEAD`를 추가한다.
- dirty/untracked file도 같은 SHA-256으로 식별한다.
- directory 전체를 scope로 받지 않는다. 실제로 읽고 수정할 파일만 열거한다.

이 정도면 stale handoff와 review-after-change를 잡으면서 token과 구현 비용을 작게 유지한다.

## 9. Fingerprint와 ledger의 연결

fingerprint는 ledger 내용을 대체하지 않는다. 역할이 다르다.

| Artifact | 답하는 질문 |
|---|---|
| Ledger | 무엇을 알고/모르고, 어떤 결정을 왜 했는가? |
| Contract | 무엇을 완료해야 하는가? |
| Fingerprint | worker/reviewer가 본 입력이 아직 같은가? |
| Evidence | 결과가 acceptance criterion을 실제로 통과했는가? |

권장 ledger entry는 사람이 읽는 stable ID를 쓰고, artifact 전체에는 digest를 둔다. 모든 문장이나 ledger row를 content-addressed ID로 만들 필요는 없다. row 내용이 조금 바뀔 때 참조가 전부 깨지는 비용이 더 크다.

```yaml
- id: KU-007
  class: known-unknown
  question: "Does settlement retry remain idempotent after timeout?"
  criticality: blocking
  status: resolved
  evidence:
    - path: docs/evidence/T-014-pytest.txt
      sha256: 9c7a...34bb
```

## 10. 최종 채용안

### Ponytail

- **채용 범위:** contract freeze 후 worker의 코드 생성과 bug root-cause 수정.
- **비채용 범위:** triage, interview, ledger discovery, architecture/plan, premortem,
  verification, security/correctness/complexity review.
- **필수 dependency:** 아님. 네 줄 policy로 핵심을 재현하고, plugin은 host별 선택 사항.

### Fingerprint

- **채용 범위:** task packet, frozen contract/scoped-artifact handoff, clean-room review의 stale-input gate.
- **구현:** SHA-256 + 선택적 Git HEAD; [loopctl.py](../.agents/skills/loop-code/scripts/loopctl.py)가 mismatch 시 `STALE_INPUT`으로 fail closed.
- **비채용:** line마다 hash prefix, Claude/Codex edit tool 교체, 별도 MCP/daemon.

이 조합의 의미는 단순하다. Ponytail은 **만들 양을 줄이고**, fingerprint는 **오래된 이해로 잘못 만들지 못하게 한다.** 둘 다 loop의 본체가 아니라 작고 독립적인 guardrail이어야 한다.

## 주요 근거 링크

- [Ponytail repository](https://github.com/DietrichGebert/ponytail)
- [Ponytail benchmark write-up](https://github.com/DietrichGebert/ponytail/blob/main/benchmarks/results/2026-06-18-agentic.md)
- [pi-hashline-edit repository](https://github.com/RimuruW/pi-hashline-edit)
- [pi-hashline-edit README: protocol and design decisions](https://github.com/RimuruW/pi-hashline-edit#how-it-works)
