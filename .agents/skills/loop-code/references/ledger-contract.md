# Ledger contract v4

Read this when creating, repairing, or interpreting a Loop ledger. New ledgers
use schema v4. The controller is a strict stdlib validator: unknown keys, enum
values, missing required fields, duplicate IDs, and malformed hashes fail with
`INVALID_INPUT` (exit 64).

## Root and baseline

The exact root keys are `schema_version`, `task_id`, `objective`, `scope`,
`baseline`, `authority`, `limits`, `control`, `progress`, `acceptance`,
`unknowns`, `decisions`, and `handoff`.

Set `baseline.workspace` explicitly. It may be absolute or ledger-relative; for
`.loop/<task>/loop-ledger.json`, `../..` normally names the project root.

Protected inputs are exact files, never directories or annotated strings:

```json
{"path": "src/config.json", "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
```

Every v4 protected input requires a 64-character lowercase SHA-256. Missing
files are reported as `missing`; directories as `not_file`; changed bytes as
`changed`. Undeclared dependencies are outside the freshness boundary.

Revision is structured:

```json
{"mode": "exact", "value": "<git commit>"}
```

- `none`: value is null; no revision contract.
- `recorded`: value is audit context only; this preserves historical v3
  behavior.
- `exact`: when workspace is a Git repository, actual `HEAD` must equal value.
  A mismatch is stale; a non-Git workspace is `revision:non_git`.

Git dirty state is reported independently. It is not itself stale because
protected file hashes and verifier evidence define the declared byte boundary.
Use `exact` plus protected inputs when both commit identity and file bytes are
contractual.

## Acceptance

Use an argv command when a repeatable executable observation exists:

```json
{
  "id": "AC-01",
  "criterion": "Focused test exits 0 and emits VERIFY_OK",
  "verifier": {
    "type": "command",
    "argv": ["py", "-3", "tests/test_feature.py"],
    "cwd": ".",
    "timeout_seconds": 300,
    "expected_exit_code": 0
  },
  "artifacts": ["build/result.json"],
  "status": "open",
  "evidence_files": []
}
```

`run` refuses an authority/safety blocker or stale exact revision/protected
input before starting the subprocess. Otherwise it executes `argv` with
`shell=False`, records bounded output, contract and workspace identity,
protected-input hashes, and artifact hashes, then updates the v4 ledger
atomically. A passed command must reference generated evidence.
Exit 0 proves only that verifier's internal contract. It does not guarantee
external reality, and a generator validating its own output is not independent
verification.

Use a human verifier only when command, file, API, or safe live probe cannot
observe the result:

```json
{
  "id": "AC-02",
  "criterion": "The reviewed model has correct geometry and units",
  "verifier": {
    "type": "human",
    "instructions": "Open the copied result and inspect geometry and units"
  },
  "artifacts": ["models/result.prt"],
  "status": "open",
  "evidence_files": [],
  "attestation": {
    "accepted": false,
    "actor": "",
    "attested_at": null,
    "statement": "",
    "fingerprint_snapshot": null
  }
}
```

When accepted, set status `passed`, `accepted: true`, a non-empty actor,
ISO-8601 `attested_at`, a review statement, and a ledger-relative fingerprint
snapshot. Capture the snapshot after review over the union of every reviewed
artifact and protected input. `actor` is audit metadata, not cryptographic
identity. Contract, workspace, artifact, or protected-input change makes the
attestation stale.

NX, Flomaster, browser, and field acceptance cannot pass solely from generated
files. Require a live probe or this human gate.

## Unknowns and decisions

The only v4 unknown shape is:

```json
{
  "id": "KU-01",
  "class": "KU",
  "statement": "Does retry preserve idempotency?",
  "impact": "critical",
  "status": "open",
  "safe_probe": "Run the isolated timeout test",
  "evidence": []
}
```

Enums are:

- `class`: `KK`, `KU`, `UK`, `UU`;
- `impact`: `critical`, `noncritical`;
- `status`: `open`, `verified`, `falsified`, `resolved`, `accepted-risk`.

A closed critical unknown requires evidence. `accepted-risk` is a recorded
decision, not identity authentication. Decisions use exactly `id`, `statement`,
`rationale`, and string-array `evidence`.

## v3 compatibility

`stop` and fingerprint reads normalize schema v3 in memory and never rewrite
the source. `run` and `round` reject v3 before subprocess execution or writes.
No migration command exists because it would add a second mutation path without
being required for compatibility.

Normalization accepts observed v3 forms:

- unknown aliases `type/q/probe` become `class/statement/safe_probe`;
- conflicting alias values are rejected rather than guessed;
- noncritical legacy impact names become `noncritical` with diagnostics;
- structured legacy evidence is preserved as canonical JSON text;
- `path (SHA256 <64 hex>)` is split into path/hash;
- plain paths have unknown hashes and remain readable; malformed annotations
  are rejected with the expected format;
- legacy revision becomes `recorded`, not retroactively `exact`;
- a human verifier's legacy `user_accepted` becomes an unauthenticated
  compatibility attestation;
- an unknown's legacy `accepted-risk` closes only when `user_accepted` was true.
  The normalizer records an explicit unauthenticated compatibility marker when
  no evidence existed; false acceptance is reopened even if a note was present.

Legacy evidence contract digests are evaluated against the original v3 view,
so a historical `STOP_SUCCESS` does not fail merely because it was normalized.
All normalization notes appear in `stop --json`.

## State and machine output

`stop --json` emits a stable object containing state, exit code, source schema,
acceptance passed/total and per-item state/reasons, stale facets with expected
and actual hashes, critical unknowns, authority/safety blockers, budget,
workspace Git/revision/dirty information, normalization diagnostics, and next
action.

Precedence and exits:

| State | Exit | Meaning |
|---|---:|---|
| `STOP_SAFETY` | 40 | authority or safety blocker |
| `STALE_INPUT` | 33 | declared evidence/input/revision changed |
| `STOP_SUCCESS` | 0 | all acceptance current; no critical unknown |
| `WAITING_HUMAN` | 20 | every remaining item is an open human gate |
| `STOP_BUDGET` | 31 | deadline/iteration/explicit budget reached |
| `CONTINUE` | 10 | a safe executable slice remains |

`round` atomically increments `progress.iteration` for v4. It cannot prevent an
operator from skipping the command, so iteration is enforced only through this
entry point. Deadline and explicit budget flags remain independently checkable;
there is no scheduler or daemon.
