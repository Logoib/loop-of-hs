# loop-of-hs

**English** · [한국어](./README.md)

A repository holding `loop-code` — a shared Claude Code / Codex skill that drives
complex code changes through a **ledger-based loop** — together with the design
documents behind it.

The source of truth is a JSON ledger in the repository, not a conversation
summary, and completion is decided by **command evidence** and **input
fingerprints** rather than by the model's own assessment. The session is treated
as working memory that may be replaced at any time.

- canonical source: [`.agents/skills/loop-code`](./.agents/skills/loop-code)
- current version: `loop-code` v0.4 (shared by Claude Code and Codex)
- target work: cross-component changes in large web applications, migrations,
  shared contract changes, and control code for external applications such as
  NX and Flomaster
- status: controller self-test passes, **no real-project UAT yet**
  (see [Verification status](#verification-status))

## Repository layout

```text
.agents/skills/loop-code/
├─ SKILL.md                      # workflow body + Stop hook frontmatter
├─ agents/openai.yaml            # Codex display metadata
├─ assets/
│  ├─ loop-ledger.template.json  # ledger template (schema_version 4)
│  └─ task-packet.template.json  # bounded task packet for delegation
├─ references/
│  ├─ ledger-contract.md         # contract read only when creating/repairing a ledger
│  ├─ runtime-routing.md         # runtime/model routing, read only after Loop is chosen
│  └─ v4-review.md               # rationale and verification scope of the v4 contract
├─ scripts/loopctl.py            # controller, standard library only
└─ tests/test_loopctl.py         # controller regression tests

docs/                            # design decisions and research (Korean)
```

## Install

There is exactly one canonical source, `.agents/skills/loop-code`, and each
runtime's discovery path is a junction pointing at that same directory. Run this
from the project root after cloning or after moving the workspace.

```powershell
# project scope (Claude Code)
New-Item -ItemType Directory -Force -Path '.claude\skills' | Out-Null
New-Item -ItemType Junction -Path '.claude\skills\loop-code' -Target (Resolve-Path '.agents\skills\loop-code')

# user global
New-Item -ItemType Junction -Path "$HOME\.claude\skills\loop-code" -Target (Resolve-Path '.agents\skills\loop-code')
New-Item -ItemType Junction -Path "$HOME\.codex\skills\loop-code" -Target (Resolve-Path '.agents\skills\loop-code')
```

Codex discovers `.agents/skills/loop-code` in the repository directly, so it
needs no project-scope junction. `.claude/skills/loop-code` and `.loop/` are in
`.gitignore`. Verify the install with:

```bash
python .agents/skills/loop-code/scripts/loopctl.py --self-test   # SELF_TEST_OK
```

## Invocation

```text
Codex:       $loop-code <one-line goal>
Claude Code: /loop-code <one-line goal>
```

Start with a **one-line goal**, not a finished SPEC document. Writing the
specification is the coordinator's job, not the user's, and its output is the
ledger rather than a separate document.

## Flow

```text
goal
→ Direct / Plan / Loop triage
→ (Loop) ledger created automatically
→ probe blocking unknowns only
→ (Loop) one blueprint confirmation gate
→ plan
→ (only when risky) fresh-context premortem
→ implement
→ command / human verification
→ advance the round counter
→ six-state stop gate
```

## 1. Triage — Direct / Plan / Loop

Pick the **smallest lane** that can verify the outcome. Project size by itself is
not a reason to choose Loop. Announce the lane and the reason in Korean, and
escalate only when evidence invalidates the current lane.

| Lane | Condition | Output |
|---|---|---|
| **Direct** | local, reversible, one clear verifier | change + verification run |
| **Plan** | several dependent steps one session can finish | step plan + verification |
| **Loop** | work crossing sessions/components, shared contracts, external application state, iterative convergence, rollback or silent-corruption risk | ledger + evidence + stop gate |

Worked examples:

- one copy/CSS change → **Direct**
- a bounded bug inside one component → **Direct** or **Plan**
- page + store + API + shared type → **Loop** candidate
- auth/schema/migration/persisted state → **Loop** + rollback/premortem/review
- NX/Flomaster writes → **Loop** + source copy, version/input hash, units,
  coordinate and material semantics, run/export evidence, recovery check

These three lanes are a simplification of OmO's classification
([docs/02, conclusion 1](./docs/02-loop-landscape-comparison.md)).

## 2. Blueprint interview gate

A **one-time** gate that exists only in the Loop lane. The acceptance criteria a
Loop will spend its budget on are inferred rather than agreed, so they are
returned to the user once before the first mutation.

Order of operations:

1. The coordinator fills the ledger **first** from code, tests, history, docs,
   and safe probes. The user is never asked to write a SPEC.
2. The filled draft is printed — objective, scope in/out and interfaces, **each
   acceptance criterion with its verifier command**, and limits. That draft is
   itself the blueprint the user reacts to; no separate mockup is produced.
3. In the same round, ask only what the repository could not answer — intent,
   priority, constraints, brownfield behavior. Each question names **the ledger
   field its answer settles**, and any question that changes no field is dropped.
4. When approaches differ at the shape-of-the-diff level, put candidate code
   fragments into the options themselves (the `preview` field of a question
   option in Claude Code) so the user compares artifacts, not descriptions.
5. The gate closes once scope, acceptance, and limits are settled. An LLM
   self-scored clarity number is never a passing condition.

This is **one round**, not an interview phase. The final gate's `user_accepted`
arrives after the budget is already spent, so it cannot change direction.

The rationale borrows Ouroboros's Socratic interview while dropping its
self-scored ambiguity gate ([docs/02, conclusion
2](./docs/02-loop-landscape-comparison.md)), plus Anthropic's "Let Claude
interview you" best practice, which says a self-sufficient spec must name the
relevant files and interfaces, state what is out of scope, and end in end-to-end
verification. Those three map onto `scope.in`/`scope.interfaces`, `scope.out`,
and the acceptance verifier, so the ledger plays the SPEC's role and no separate
SPEC document is written.

## 3. Unknown management and KG lookup

Record only useful uncertainty.

| Class | Meaning |
|---|---|
| **KK** | verified fact with provenance |
| **KU** | explicit question + cheapest decisive probe |
| **UK** | knowledge likely held by code, tests, history, docs, tools, or the user |
| **UU** | blind-spot hypothesis + falsification probe |

The department's shared KG wiki is the source of truth for reusable procedures,
terminology, design rationale, and lessons learned, but it never overrides
repository code/tests, live external state, or the user's current decision. Call
`kg-lookup` **just in time** before asking the user or copying a department rule
into the ledger. The coordinator does not pre-search everything; the worker that
holds KG access calls it directly. If nothing is found, that gap is recorded as
an unknown.

Preload only KG facts that are essential to safety, a frozen contract, or
consistency across parallel work, and put them into the task packet's `facts` as
a short statement plus a wiki path. If that note snapshot must be pinned, include
the note path in the `fingerprint` scope so its SHA-256 is captured too. Note
bodies and search history are not copied into the ledger, and no retrieval
manifest or separate KG-staleness state is added until a real run shows the need.

## 4. Ledger

A Loop creates `.loop/<yyyyMMdd-HHmmss>-<short-slug>/loop-ledger.json` (with
`-2`, `-3` on collision). The only fields kept are objective, scope/interfaces,
workspace/protected input/rollback, authority, finite limits, acceptance,
unknowns, decisions, and handoff.

Core rules:

- New ledgers are created at **schema_version 4**. v3 is read through strict
  in-memory normalization only, mutating commands reject v3, and the original v3
  file is never rewritten.
- State `baseline.workspace` explicitly. Relative to
  `.loop/<task-id>/loop-ledger.json`, the project root is usually `../..`. The
  empty template is deliberately incomplete.
- **At least one** of `limits.max_iterations` and `limits.deadline` must be
  non-null.
- A verifier is an **argv array**, not a shell string.
- List every exact source/test/config/pinned knowledge note the verifier uses in
  `baseline.protected_inputs`. Directories and undeclared dependencies are
  deliberately outside the freshness boundary.
- A critical unknown cannot become `verified`/`falsified`/`resolved` without
  non-empty evidence, and `accepted-risk` additionally requires
  `user_accepted: true`.
- The coordinator is the only ledger writer. `loopctl.py` commands that mutate
  the ledger run serially. Atomic replacement prevents partial files; it is not a
  multi-writer lock.

The exact shape of acceptance and unknown records is in
[ledger-contract.md](./.agents/skills/loop-code/references/ledger-contract.md).

## 5. `loopctl.py`

A controller written with the Python standard library only. It does four things.

```bash
# contract + exact files + (optional) Git HEAD snapshot
python <skill-root>/scripts/loopctl.py fingerprint capture \
  --ledger <ledger> --workspace <workspace> --scope <paths...> [--pin-head] [--output <snapshot>]
python <skill-root>/scripts/loopctl.py fingerprint verify \
  --ledger <ledger> --snapshot <snapshot> [--workspace <workspace>]

# run an acceptance: records exit/output/artifact SHA + workspace and protected-input fingerprints
python <skill-root>/scripts/loopctl.py run <ledger> --acceptance <AC-ID> [--output <evidence.json>]

# mark one bounded round finished: the controller advances progress.iteration
python <skill-root>/scripts/loopctl.py round <ledger>

# re-check current evidence and compute one of the six states
python <skill-root>/scripts/loopctl.py stop <ledger> [--json]

python <skill-root>/scripts/loopctl.py --self-test
```

Commands are defined as **argv arrays** and never run as an unquoted shell
string. `run` writes its evidence file under `<ledger-dir>/evidence/` and updates
the ledger atomically. Command evidence is never hand-edited.

Output and exit codes:

| Command | Output | Exit code |
|---|---|---:|
| `fingerprint verify` | `MATCH` / `STALE_INPUT <mismatches>` (differences with `--json`) | 0 / 33 |
| `run` | `VERIFY_PASS`\|`VERIFY_FAIL` + AC-ID + evidence path | 0 / 4 |
| `round` | `ROUND <iteration>/<max\|->` | 0 |
| `stop` | `STOP_SUCCESS` | 0 |
| `stop` | `CONTINUE` | 10 |
| `stop` | `WAITING_HUMAN` | 20 |
| `stop` | `STOP_BUDGET` | 31 |
| `stop` | `STALE_INPUT` | 33 |
| `stop` | `STOP_SAFETY` | 40 |
| any command | `INVALID_INPUT <error>` (stderr) | 64 |

`run` records a failure not only when a declared artifact cannot be hashed but
also when a **declared protected input can no longer be hashed**. A missing or
moved input is a missing input, not a pass.

## 6. The six stop states

After each bounded round, advance `progress.iteration` with `round` and follow
the state returned by `stop --json`. The iteration limit is enforced only when
`round` is called; the deadline and an explicit `control.budget_exhausted` are
enforced independently of it. State precedence is `STOP_SAFETY` → `STALE_INPUT` →
`STOP_SUCCESS` → `WAITING_HUMAN` → `STOP_BUDGET` → `CONTINUE`.

| State | Meaning |
|---|---|
| `STOP_SUCCESS` | every acceptance has current evidence and no critical unknown is open |
| `WAITING_HUMAN` | every remaining acceptance is a human gate, so the model cannot advance |
| `STOP_BUDGET` | a declared iteration/deadline boundary was reached |
| `STOP_SAFETY` | authority, data-loss, destructive, or security boundary |
| `STALE_INPUT` | contract/workspace/input/verifier/artifact disagrees with the evidence |
| `CONTINUE` | exactly one manageable next slice remains |

If an unresolved unknown makes the next action unsafe, set `authority.blocked`
and stop safely. No state is added until a real run demands separate handling.

## 7. Evidence and the freshness boundary

- Command evidence freshness covers the contract (including workspace), the
  verifier definition, `baseline.protected_inputs`, and declared artifacts.
- A human verifier is used only when the result cannot be observed by a safe
  command, file, API, or test. `user_accepted: true` can be set **by the user
  only** and is never substituted by model observation. When protected inputs or
  reviewed artifacts exist, capture one fingerprint over their union after the
  review and store it in `fingerprint_snapshot`, so any later file, contract, or
  workspace change makes that approval stale.
- `stop` does not re-run verifiers, does not observe live external application
  state, and does not hash undeclared inputs. Re-run the affected acceptance
  after any change outside the declared boundary.
- Lint and static typing see source-level rules only; they do not validate
  runtime JSON or workflow state. The controller validates ledger shape and state
  invariants, and each verifier validates the produced result.
- For NX/Flomaster work, include version, input/output identity, units,
  coordinate and material semantics, external process results, and source
  recovery in the evidence.

Classify a failed attempt before retrying — stale contract/input, deterministic
verifier failure, or transient infrastructure failure. Refresh what is stale,
change the implementation on a deterministic failure, and retry only transient
failures within a bound. Never turn an invalid result into a pass by retrying.

## 8. Premortem and cross review

A fresh-context premortem runs not every round but only for irreversible or
persisted changes, shared migrations, NX/Flomaster writes, unit/coordinate/
material semantics, unclear rollback, or plausible silent corruption.

One frozen task packet is handed to fresh read-only roles in two waves.

- **Thesis** — proposes the minimum safe plan and its invariants.
- **Anti-thesis** — receives the same packet without the preferred plan or its
  reasoning, and lists failure cases and falsification probes.
- **Synthesis** — runs after both, compares against the contract and verifiers,
  and resolves each finding as accepted, rejected with evidence, or converted
  into an unknown or acceptance criterion.

Repeat the premortem only when the plan or contract changed materially, or when a
failed approach genuinely requires a different plan. Once a candidate artifact
exists, use **one** cross-provider review — `$claude-adversarial-review` in
Codex, `/codex:adversarial-review` in Claude Code. Confirm user approval before
sending repository content to another provider or consuming the other side's plan
usage.

## 9. Host goal mechanism

Explicit invocation of the skill arms the host's goal facility before triage.
Activating a goal does not widen tool permissions, permission prompts, or safety
boundaries.

**Codex** — check for an active goal with `get_goal` and reuse it; otherwise call
`create_goal`. Never print `/goal` as output and never spawn a nested Codex CLI.
At a true terminal state, record `complete` with `update_goal` (or `blocked`,
strictly per that tool's repeated-blocker rule).

**Claude Code** — `/goal` is a user-only built-in command that the assistant
cannot arm. No settings key, environment variable, CLI flag, or hook sets it on
the user's behalf. Two mechanisms are used instead.

1. The **prompt-based `Stop` hook** in `SKILL.md` frontmatter. Per the official
   docs, `/goal` itself is a wrapper around a session-scoped prompt `Stop` hook,
   and Claude Code registers frontmatter hooks on skill invocation and keeps them
   for that session (only subagent hooks are scoped to component lifetime). A
   Loop spans many turns, so this session scope is intended and `once: true` is
   not used. The hook checks `stop_hook_active` first and passes immediately if
   the block cap was reached; otherwise it continues the same turn while evidence
   is missing.
2. A `/goal` the user runs themselves. The hook is not a goal object, so there is
   no `◎ /goal active` indicator, no status query, and no `--resume` restoration.
   So when triage picks Plan or Loop, print the paste-ready line exactly once and
   proceed without waiting for an answer. Say once why both mechanisms exist —
   the hook lives only for this session, while a user-run `/goal` persists across
   turns, survives `--resume`, and is what actually sustains a multi-session Loop.

Write the goal condition for the evaluator that will read it. A small fast model
runs after each turn and judges **only what the conversation already showed**. It
runs no commands and reads no files. So write the terminal state as something
this session must print (`run selftest.py and print SELFTEST_PASS`) rather than
as an unobservable property (`the code is correct`), and include the constraints
that must not change mid-run plus a turn or time bound (4,000 characters max).

The assistant cannot read whether a goal is active, and never claims that it is.
`/goal` is unavailable in untrusted workspaces and under `disableAllHooks` or
`allowManagedHooksOnly`; there the ledger loop sustains the work alone.

Source: <https://code.claude.com/docs/en/goal> (checked 2026-08-19)

## 10. Context operations and model routing

A large API window is not the working-memory target. Record the runtime's session
budget and the user's soft cap separately, and resume from a ledger checkpoint
into fresh context at phase boundaries, on compaction, on repeated
re-exploration, on contract contradictions, on stale reuse, and when tool output
dominates. Resume from the **ledger**, not from a transcript summary. A
configured token cap is an operating policy, not a universal quality cliff.

Values checked on 2026-07-21:

| Layer | Value |
|---|---:|
| GPT-5.6 Sol/Terra API maximum | 1,050,000 |
| Codex 0.144.6 client catalog | 272,000 |
| session reported budget (95%) | 258,400 |
| user soft cap | 150,000 |

Recommended routing by role. Preserve the **role**, not the brand — strongest
coordinator, independent reviewer when risk is high, bounded worker.

- **Codex** — GPT-5.6 Sol `xhigh` for coordination, plan, premortem, synthesis,
  and final review. Luna `max` for bounded implementation with clear,
  command-verifiable acceptance and for read-heavy exploration (a cheap worker,
  not a low-latency one). Escalate to Sol `high` for hard or ambiguous
  implementation, weak verifiers, external or persisted state, and deterministic
  Luna failures. Keep one independent Sol `xhigh` final gate. `ultra` stays off
  by default.
- **Claude Code** — Fable 5 for coordination, the current Opus for hard
  reasoning, the current Sonnet for bounded implementation and research (when
  available on the account). Use a scoped goal hook for serial convergence, and
  dynamic workflows or `ultracode` only for repetitive fan-out or pipelines.

Use fresh subagents for noisy exploration and independent review, and a Git
worktree only when there are concurrent writers. Do not add custom agent profiles
until a real run shows prompt routing to be insufficient.

## Design boundaries

This is a hybrid harness — the script verifies mechanical evidence, while the
coordinator classifies semantic facts and calls that script. The self-test
validates the controller; it does not prove the workflow is useful.

- No `standard/high` modes, no separate premortem/review state, no ledger lock,
  no triage scoring, no user-acceptance signature scheme. No hook, state, or
  framework layer is added until real Vue/NX/Flomaster runs reveal repeated
  failures.
- Ponytail (reuse → stdlib/native → installed dependency → smallest diff) applies
  at runtime **only to the code-generation step** after acceptance is frozen. In
  skill maintenance it is used to remove what is unused, never to reduce runtime
  discovery, safety, verification, or explicit requirements.
- Parser keys and enums stay in English. Free text is written in whichever
  language hands off best, and user-facing reports are in Korean.
- Report after triage and at each gate — done/current work, acceptance
  passed/total, iteration/limit, blocking unknowns, rollback state, and the next
  evidence. Never invent a completion percentage.

## Verification status

**Confirmed** — Codex repository skill discovery, Claude `/loop-code` read-only
discovery, junction identity/hash, user-global Codex config, skill schema, JSON
parsing, controller unit self-test, command evidence, stale artifact rejection,
source/workspace drift reproduction, v4 schema validation with v3 read-only
normalization, six-state stop.

**Unconfirmed** — UAT of a Claude/Codex workflow that performs a real change,
per-worker model routing, handoff quality after 150K compaction, real
Vue/NX/Flomaster tasks, user-global discovery on both runtimes.

A discovery smoke test or a controller self-test is never called a workflow
correctness PASS.

## Roadmap

- [x] minimum `loop-code` controller
- [x] controller P0 freshness/ledger validation hardening
- [x] Loop lane blueprint confirmation gate
- [ ] **P0** — UAT on one real Vue cross-component change
- [ ] **P0** — UAT on one or two real NX/Flomaster changes
- [ ] **P1** — `loop-search` (research loop over local, KG, and official web sources)
- [ ] **P2** — `loop-report` (verified source bundle → report/HTML/PDF/slides)
- [ ] **P3** — `loop-cae` if a need is confirmed

For each UAT run, record the gates used, ceremony time, errors found, stale-input
occurrences, rework avoided, and ledger fields that went unused. Remove unused
fields and states, and add only the minimum device that prevents a repeated
failure. No `loop-core` abstraction is extracted before real commonality is
confirmed. Details and deferred items are in
[08-loop-skill-roadmap.md](./docs/08-loop-skill-roadmap.md).

## Documents

The documents under `docs/` are written in Korean.

| Document | Role |
|---|---|
| [00-report-index.md](./docs/00-report-index.md) | report index |
| [05-loop-code-design.md](./docs/05-loop-code-design.md) | current minimum design (operational) |
| [06-cross-runtime-skill-setup.md](./docs/06-cross-runtime-skill-setup.md) | runtime/config/junction (operational) |
| [08-loop-skill-roadmap.md](./docs/08-loop-skill-roadmap.md) | UAT-first TODO (operational) |
| [01-anthropic-cca-principles.md](./docs/01-anthropic-cca-principles.md) | Anthropic/CCA-F principles research |
| [02-loop-landscape-comparison.md](./docs/02-loop-landscape-comparison.md) | comparison of existing loop frameworks |
| [03-ponytail-fingerprint-review.md](./docs/03-ponytail-fingerprint-review.md) | Ponytail boundary and stale-input rationale |
| [04-context-rot-and-stop-criteria.md](./docs/04-context-rot-and-stop-criteria.md) | context research and runtime snapshot |
