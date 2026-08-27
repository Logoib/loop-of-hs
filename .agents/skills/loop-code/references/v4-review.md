# loop-code v4 empirical review

Review date: 2026-08-27. Canonical
repository and installed skill targets were resolved before testing. External
ledgers were read only and are not copied here.

## v3 failure to v4 change

| Observed v3 behavior | v4 change | Evidence |
|---|---|---|
| A ledger with only a human verifier open returned `CONTINUE` | added `WAITING_HUMAN` exit 20 after freshness/success and before budget | one real ledger changed state without byte changes |
| Unknown records used both `class/statement/safe_probe` and `type/q/probe` | one strict v4 shape; version-aware v3 aliases normalize in memory; conflicts reject | synthetic mixed/conflict fixtures and real read |
| Legacy evidence and handoff contained scalar or structured values | preserved as string or canonical JSON text with normalization diagnostics | two real parser failures found and fixed during regression |
| One protected input combined path and SHA-256 in a string | v4 uses `{path, sha256}`; exact legacy annotation splits; malformed form rejects | synthetic malformed fixture and real ledger read |
| `baseline.revision` was recorded but not always checked | v4 distinguishes `none`, `recorded`, and actual-HEAD-enforced `exact` | temporary Git repository mismatch fixture |
| Human evidence relied on `user_accepted` | v4 requires actor/time/statement/fingerprint attestation; actor is explicitly unauthenticated metadata | artifact-change-after-review fixture |
| Iteration could be hand-edited or skipped | `round` atomically increments v4; docs limit the claim to that entry point and retain deadline enforcement | round and expired-deadline fixtures |
| Stop output hid why individual acceptance was open or stale | `stop --json` emits per-acceptance reasons, hash differences, blockers, unknowns, and next action | deterministic JSON self-test and real stale facets |
| A skill-frontmatter Stop hook was described as a goal substitute | removed the hook; triage precedes Codex native goal or Claude user-run `/goal` line | frontmatter validation and official capability review |
| Task packets were routine ceremony despite no real JSON usage | packet remains optional only for delegated mutation or independent review | read-only search found no real task-packet JSON |

Command exit 0 remains internal-consistency evidence only. No v4 document calls
a generator checking its own output independent verification, or treats a file
check as live NX, Flomaster, browser, or field truth.

## Claude Code capability matrix

Verified against official Claude Code docs on 2026-08-27; installed CLI was
2.1.247.

| Capability | Official behavior | v4 contract |
|---|---|---|
| `/goal` | session-scoped prompt Stop hook; evaluator has conversation only and calls no tools | user runs one observable Plan/Loop condition; assistant never claims activation/status |
| Resume | active condition returns on supported resume routes; turn/time/token-spend baseline resets | ledger retains cumulative bounds and evidence |
| Skill hook | applies for the rest of the current session once invoked | not treated as a durable resume gate; no v4 frontmatter Stop hook |
| Stop re-entry | `stop_hook_active` signals a prior continuation; host overrides after 8 consecutive blocks | no false “flag means cap reached” claim |
| Subagent | non-fork gets fresh isolated context; fork inherits conversation; skills can be preloaded | use a bounded packet or explicit skill preload |
| Extension type | skills guide judgment, hooks enforce lifecycle events, subagents isolate context | no Claude-specific orchestration layer |

Sources are linked in `runtime-routing.md`. No paid `claude -p` smoke test and no
cross-provider review was run without user approval. That reference contains a
three-minute non-sensitive manual test.

## Existing-ledger regression

The pre-mutation freeze found seven external schema-v3 ledgers. The final search
found six external ledgers plus this task's ignored local ledger; one earlier
external `CONTINUE` ledger was no longer present in the search roots. loop-code
did not delete or write any external ledger. Each of the six still accessible
external files had its SHA-256 compared before and after `stop --json`.

| State | initial v3 scan (7) | paired final v4 scan (6) |
|---|---:|---:|
| `STOP_SUCCESS` | 1 | 1 |
| `STALE_INPUT` | 4 | 4 |
| `CONTINUE` | 2 | 0 |
| `WAITING_HUMAN` | 0 | 1 |
| invalid | 0 | 0 |

All 6 paired source hashes were unchanged. The existing success stayed successful.
Stale reports now identify facets such as contract, workspace, protected input,
artifact, and invalid fingerprint, including expected/actual hash fields where
applicable. The prior human-only continuation is now explicit human wait.

## Context cost and behavior coverage

| File | v3 lines | v4 lines | Reason |
|---|---:|---:|---|
| `SKILL.md` | 273 | 156 | runtime tables, schema detail, and examples moved to references |
| `loopctl.py` | 743 | 1457 | strict versioned validation, structured diagnostics, revision/human freshness, and focused fixtures |

The shorter skill retains triage, post-triage goal routing, contract freeze,
bounded execution, verification semantics, six stop states, resume, and review
approval. Controller growth is local stdlib code and fixtures; no schema
framework or service dependency was added.

## Direct versus Loop experiment design

No ROI claim is made from self-tests. To measure it, select at least ten matched
pairs of real changes with the same risk class and independent acceptance. For
each pair, randomly assign Direct or Loop before work and keep model/runtime,
repository state, and verifier fixed. Record wall time, model usage estimate,
human interruptions, ceremony files, stale-input catches, acceptance defects,
and seven-day rework. The primary outcome is independently verified success;
secondary outcomes are time and rework. Stop or narrow Loop if it adds cost
without fewer stale/acceptance failures.

## Not yet proved and v5 triggers

v4 proves controller behavior and compatibility, not productivity, defect
reduction, or economic ROI. It does not authenticate a human actor, discover
undeclared dependencies, observe external applications without a probe, or
force an operator to call `round`.

Defer to v5 only when evidence triggers it:

- add a non-overwriting migration command after repeated operational demand for
  writable v3-to-v4 conversion;
- add signed/host-backed identity only when audit policy requires actor
  authentication;
- validate/extend task packets after at least three real delegated uses expose a
  repeated shape failure;
- add a verifier type only when a live probe changes stop semantics rather than
  merely its command;
- revisit a persistent hook/plugin only if official goal resume cannot support a
  measured workflow, with explicit settings/provider authorization;
- split the controller only when maintenance or reuse data shows the single
  stdlib file is the bottleneck.
