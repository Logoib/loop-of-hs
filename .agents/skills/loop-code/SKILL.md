---
name: loop-code
description: Triage and execute complex code changes through a small ledger-driven loop with command evidence, stale-input fingerprints, and just-in-time lookup of shared department knowledge. Explicit invocation arms a completion gate only after Plan or Loop triage on hosts that provide one. Use for cross-component or multi-session changes, migrations, shared interfaces, large web applications, external NX or Flomaster integrations, or code changes with rollback or silent-corruption risk. Do not use for research-only work, report generation, or a clearly one-step edit.
---

# Loop Code

Use the smallest lane that can verify the user's outcome. The ledger is durable
task state, not a general agent framework and not a replacement for host goals.

## 1. Triage before creating state

Choose and announce one lane:

- **Direct**: local, reversible, and one clear verifier. Create neither a goal
  nor a ledger.
- **Plan**: several dependent steps that one healthy session should finish.
  Draft observable acceptance and a bound; use the native goal after triage.
- **Loop**: cross-session/component work, shared contracts, external application
  state, or rollback/silent-corruption risk. Use a bounded v4 ledger and, when
  supported, the native goal after triage.

Project size alone does not force Loop. Escalate only when evidence invalidates
the current lane. If Plan needs durable recovery or the host has no goal
facility, use the same bounded ledger as Loop.

For Plan and Loop, write one completion condition containing:

- the exact verifier command as an argv-safe display;
- expected exit code and observable output;
- files/state that must be preserved; and
- a turn or time bound.

Then route by host:

- **Codex**: use native goal tools after triage. Reuse a matching active goal;
  otherwise create it from the condition. Mark it complete only at a true
  terminal state and follow the runtime's blocker rule.
- **Claude Code**: print one ready-to-paste line, `/goal <condition>`. The user
  must run it. Never claim that the assistant activated or inspected the goal;
  `/goal` with no arguments is the user's status check.
- **No goal/hook support**: state that once and rely on the bounded ledger.

Claude's `/goal` keeps the current or resumed session working; the ledger keeps
durable task state and evidence. It does not let the evaluator read files or run
commands. See `references/runtime-routing.md` only when Plan/Loop is selected or
runtime behavior is unclear.

## 2. Freeze the Loop contract

For Loop, copy `assets/loop-ledger.template.json` to
`.loop/<yyyyMMdd-HHmmss>-<slug>/loop-ledger.json`. Fill objective, scope,
interfaces, authority, exact workspace, acceptance, protected inputs, rollback,
and at least one deadline or iteration limit. Show the drafted contract once
before the first mutation; ask only questions that set a ledger field.

Use v4 for new ledgers. `loopctl.py` reads v3 by strict in-memory normalization
without rewriting it. Mutating commands reject v3. Read
`references/ledger-contract.md` when creating, repairing, or interpreting a
ledger.

Record only actionable uncertainty:

- **KK**: verified fact with provenance;
- **KU**: known question with the cheapest decisive probe;
- **UK**: likely knowledge in code, history, docs, tools, KG, or the user;
- **UU**: blind-spot hypothesis with a falsification probe.

Use `$kg-lookup` just in time for missing internal terminology, procedure,
rationale, or system context. KG evidence does not override code/tests, live
state, or the user's current decision and does not reveal unknown unknowns.

Create a task packet from `assets/task-packet.template.json` only for delegated
mutation or an independent review. Premortem is optional and justified only by irreversible or
persisted changes, shared migrations, unclear rollback, or plausible silent
corruption. Keep the coordinator as the only ledger writer.

## 3. Execute one bounded slice

Build the smallest plan that closes an open acceptance. Read independent inputs
in parallel; sequence overlapping writes or isolate them. Preserve source
NX/Flomaster files and confirm rollback before mutation.

Before a delegated slice, fingerprint the frozen ledger and exact inputs. On
`STALE_INPUT`, refresh and reissue the slice. Run ledger-mutating controller
commands serially; atomic replacement is not a multi-writer lock.

Classify failures before retrying: stale input/contract, deterministic verifier
failure, or transient infrastructure failure. Refresh stale state, change the
implementation for deterministic failures, and retry only bounded transient
operations.

After each v4 work round, advance the controller-owned counter:

```text
python <skill-root>/scripts/loopctl.py round <ledger>
```

The counter is enforced only when this command is used. Deadline and explicit
`control.budget_exhausted` remain independently enforceable; no scheduler or
daemon is implied.

## 4. Verify evidence

Define command verifiers as argv arrays and run without a shell string:

```text
python <skill-root>/scripts/loopctl.py run <ledger> --acceptance <AC-ID>
python <skill-root>/scripts/loopctl.py stop <ledger> --json
```

Exit 0 is evidence of the command's internal contract only. It is not proof of
external reality; a generator checking its own output is not independent
verification. NX, Flomaster, browser, and field acceptance require a live probe
or a human gate when the result cannot be observed safely by command/API.

For human evidence, record the required attestation and a fingerprint over all
reviewed artifacts plus protected inputs. `actor` is audit text, not
cryptographic identity. A changed contract, artifact, or fingerprinted input
makes the attestation stale.

Command freshness covers only declared protected inputs and artifacts. It does
not protect undeclared dependencies. Dirty Git state is reported; exact revision
mode separately compares the declared baseline to actual `HEAD`.

## 5. Stop on machine state

Use `stop --json` after every bounded round. Obey this precedence:

1. `STOP_SAFETY` -- authority or safety blocker;
2. `STALE_INPUT` -- contract, revision, protected input, artifact, or evidence changed;
3. `STOP_SUCCESS` -- all acceptance current and no critical unknown open;
4. `WAITING_HUMAN` -- every remaining acceptance is a human gate;
5. `STOP_BUDGET` -- deadline, iteration, or explicit budget boundary reached;
6. `CONTINUE` -- one concrete safe slice remains.

Do not hide an answerable human gate as `CONTINUE` or an unsafe blocker as a
budget stop. Resolve critical unknowns before success. Report state, acceptance
passed/total, stale reasons, blockers, limit, rollback, and the next action in
Korean; never invent a completion percentage.

## 6. Review and resume

Resume from ledger evidence, not transcript memory. A fresh non-forked subagent
does not automatically receive parent history or invoked skills; provide the
bounded packet or explicitly preload the skill when needed.

Detect optional cross-provider review locally. Before sending repository
content to another provider or consuming paid usage, obtain explicit user
approval. If unavailable or unapproved, perform a fresh local independent
review. Do not make a plugin, MCP service, settings change, dashboard, database,
telemetry service, or workflow engine for this fallback.

The controller self-test proves its state machine and evidence mechanics, not
workflow ROI. Stop when acceptance is current, safety blocks work, or the bound
is reached.
