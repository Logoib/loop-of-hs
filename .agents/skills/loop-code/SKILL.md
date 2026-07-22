---
name: loop-code
description: Triage and execute complex code changes through a small ledger-driven loop with command evidence, stale-input fingerprints, and just-in-time lookup of shared department knowledge. Use for cross-component or multi-session changes, migrations, shared interfaces, large web applications, external NX or Flomaster integrations, or code changes with rollback or silent-corruption risk. Do not use for research-only work, report generation, or a clearly one-step edit.
---

# Loop Code

Start from the user's goal, not a requested specification ceremony. Treat the
ledger as durable state and each session as replaceable working memory.

## 1. Triage the goal

Choose the smallest lane that can verify the result:

- **Direct**: local, reversible, one clear verifier.
- **Plan**: several dependent steps that one healthy session can finish.
- **Loop**: cross-session or cross-component work, shared contracts, external
  application state, iterative convergence, or rollback/silent-corruption risk.

Project size alone does not force Loop. Announce the lane and reason in Korean.
Escalate only when evidence invalidates the current lane.

## 2. Bootstrap the ledger

For Loop, create
`.loop/<yyyyMMdd-HHmmss>-<short-slug>/loop-ledger.json` from
`assets/loop-ledger.template.json`; append `-2`, `-3`, and so on for collisions.
Fill objective, `baseline.workspace`, scope, authority, at least one acceptance
criterion, and an iteration or deadline limit. Add rollback when persisted or
external state can change. Read `references/ledger-contract.md` when needed.

Create the ledger without asking the user to write a full spec. Ask only for a
decision-changing unknown that local code, tests, docs, tools, or a safe probe
cannot resolve.

Keep parser keys/enums in English. Use free text in the language that makes the
handoff most reliable; report progress to the user in Korean.

## 3. Reduce unknowns and plan

Record only useful uncertainty:

- **KK**: verified fact with provenance;
- **KU**: explicit question with the cheapest decisive probe;
- **UK**: likely knowledge in code, tests, history, docs, tools, or the user;
- **UU**: blind-spot hypothesis plus a falsification probe.

Treat the curated shared KG wiki as the source of truth for reusable department
procedures, terminology, design rationale, lessons learned, and tacit knowledge.
It does not override repository code/tests, live external state, or a current
user decision.

Before asking the user or copying a department rule into the ledger, run
`kg-lookup` with the original objective and current slice. Let a worker with KG
access call it directly, just in time; do not make the coordinator pre-search
every task. If lookup finds nothing useful, record the gap as an unknown.

Preload only a KG fact that is mandatory for safety, the frozen contract, or
consistent parallel work. Put its short statement and KG-relative wiki path in
the existing task-packet `facts`. If that exact note snapshot must remain fixed,
include the note path in the existing `loopctl.py fingerprint` scope so its
SHA-256 is captured with the other inputs. Do not copy note bodies or search
transcripts into the ledger, and do not add a retrieval manifest, index revision,
or separate KG-staleness state until a real run demonstrates the need.

Build the smallest plan that closes acceptance criteria. Use a fresh-context
premortem only for irreversible or persisted changes, shared migrations,
NX/Flomaster writes, units/coordinate/material semantics, unclear rollback, or
plausible silent corruption. Hide the preferred plan during the blind pass.
Convert surviving findings into unknowns or acceptance criteria.

Do not repeat premortem every round. Repeat it only after a material plan or
contract change, or when a failed approach requires a genuinely different plan.
Use `/codex:adversarial-review` only after an artifact exists.

## 4. Execute a bounded slice

Keep the coordinator as the only ledger writer. Create a task packet only for a
delegated mutation or independent review. Before delegated work, capture and
verify the frozen ledger and exact input files with `loopctl.py fingerprint`.
On `STALE_INPUT`, re-read and reissue the packet.

Run ledger-mutating `loopctl.py` commands serially. Atomic replacement prevents
partial files; it is not a multi-writer lock.

Run independent reads in parallel. Sequence overlapping writes or isolate them
in Git worktrees. Preserve source NX/Flomaster files and confirm rollback before
mutation.

Apply Ponytail only while generating code after acceptance is frozen: reuse
repository patterns, then stdlib/native features, then installed dependencies,
and make the smallest diff that satisfies the contract. Ponytail may simplify
this skill during maintenance, but must not reduce runtime discovery, safety,
verification, or explicit requirements.

## 5. Produce evidence

Resolve the installed skill root and define command verification as an argv
array. Run without an unquoted shell string:

```text
python <skill-root>/scripts/loopctl.py run <ledger> --acceptance <AC-ID>
```

The runner records exit code, bounded output, output hashes, artifact hashes,
and contract hash, then atomically updates the ledger. Use a human verifier only
when no safe command, file, API, or test can observe the result; only the user
may set `user_accepted: true`.

For NX/Flomaster work, include applicable version, input/output identity, units,
coordinate or material semantics, external process result, and source recovery.

## 6. Stop through five states

After each bounded round, update `progress.iteration` and run:

```text
python <skill-root>/scripts/loopctl.py stop <ledger>
```

Obey the emitted state:

- `STOP_SUCCESS`: every acceptance has current evidence and no critical unknown remains;
- `STOP_BUDGET`: the declared iteration/deadline boundary is reached;
- `STOP_SAFETY`: authority, data-loss, destructive, or security boundary is hit;
- `STALE_INPUT`: accepted evidence no longer matches the contract or artifacts;
- `CONTINUE`: one concrete affordable slice remains.

If an unresolved unknown makes the next action unsafe, set `authority.blocked`
and stop safely. Do not add a new state until a real run needs distinct handling.

## 7. Refresh and report

Run `plan -> optional premortem -> implement -> verify`; repeat only for an open
acceptance criterion or evidence that invalidates the plan. Checkpoint at phase
boundaries, compaction, a configured runtime soft cap, repeated exploration,
contract contradiction, stale reuse, or tool-output domination. Resume from the
ledger, not a transcript summary. A configured token cap is an operating policy,
not a universal quality cliff.

After triage and each gate, report in Korean: completed/current work, acceptance
passed/total, iteration/limit, blocking unknowns, rollback state, and next
evidence. Never invent a completion percentage.

Read `references/runtime-routing.md` only after selecting Loop or when runtime
routing is unclear.

## Boundaries

This is a hybrid harness: scripts verify mechanical evidence; the coordinator
still classifies semantic facts and must invoke them. The self-test validates the
controller, not workflow usefulness. Do not add hooks, states, or new framework
layers until a real Vue/NX/Flomaster run exposes a repeated failure.

Command-evidence freshness currently covers the contract, verifier definition,
and declared artifact hashes. `stop` does not rerun the verifier or hash
undeclared source files. After a merge, rebase, or relevant source/test change,
rerun acceptance immediately before `stop` until scoped fingerprints are wired
into the stop gate.
