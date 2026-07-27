# Ledger contract

Read this only when initializing or repairing a Loop ledger.

Set `baseline.workspace` explicitly. It may be an absolute project path or a
path relative to the ledger directory; for `.loop/<task-id>/loop-ledger.json`,
`../..` normally names the project root. The blank template is intentionally
incomplete; fill the workspace before invoking `loopctl.py`.

## Controller validation

Before fingerprint, acceptance, or stop decisions, the controller validates the
runtime ledger contract. Required fields include a non-empty task/objective,
scope arrays, workspace/environment/protected inputs/rollback, authority and
control booleans, a non-empty acceptance list, unique IDs, and valid verifier
arguments. `limits.max_iterations` may be null or a positive integer and
`limits.deadline` may be null or an ISO-8601 datetime, but not both null.

Lint and static typing remain useful source checks; they do not replace runtime
JSON validation. Runtime shape validation and semantic state rules are separate:
a critical unknown cannot use `verified`, `falsified`, or `resolved` without
non-empty evidence, and `accepted-risk` also requires user acceptance.
This fixed local contract uses a small standard-library validator; Pydantic is
not required unless multiple external schemas create enough duplication to
justify that dependency.

List every exact source, test, configuration, or fixed knowledge note used by a
verifier in `baseline.protected_inputs`. Directories and undeclared dependencies
are intentionally outside the controller's freshness boundary.

## Acceptance record

Use a command verifier whenever a repeatable executable check exists.

```json
{
  "id": "AC-01",
  "criterion": "The focused test passes and produces the expected artifact",
  "verifier": {
    "type": "command",
    "argv": ["npm", "test", "--", "feature-name"],
    "cwd": ".",
    "timeout_seconds": 300,
    "expected_exit_code": 0
  },
  "artifacts": ["dist/result.json"],
  "status": "open",
  "evidence_files": []
}
```

Use a human verifier only when the result cannot be observed through a safe
command, file, API, or test.

```json
{
  "id": "AC-02",
  "criterion": "The user confirms the NX model opens with correct geometry",
  "verifier": {
    "type": "human",
    "instructions": "Open the copied result, inspect geometry and units"
  },
  "artifacts": ["models/result.prt"],
  "status": "open",
  "user_accepted": false,
  "human_evidence": "",
  "fingerprint_snapshot": "evidence/AC-02-fingerprint.json"
}
```

Only the user can set `user_accepted: true`. A model observation is not a human
acceptance substitute. When protected inputs or reviewed artifacts exist,
capture a fingerprint over their union after review and save the snapshot at
`fingerprint_snapshot`. `stop` requires that snapshot to cover every declared
path and still match the contract, workspace, and files. The field may be
omitted only when neither set contains a path.

```text
python <skill-root>/scripts/loopctl.py fingerprint capture --ledger <ledger> --workspace <workspace> --scope <protected-inputs-and-artifacts...> --output <snapshot>
```

## Unknown record

```json
{
  "id": "KU-01",
  "class": "KU",
  "statement": "Does retry preserve idempotency?",
  "impact": "critical",
  "status": "open",
  "safe_probe": "Run the isolated timeout test",
  "user_accepted": false,
  "evidence": []
}
```

Closed statuses are `verified`, `falsified`, and `resolved`. `accepted-risk`
closes a critical unknown only with `user_accepted: true`.

## Evidence boundary

`loopctl.py run` creates command evidence and updates the ledger. Do not hand-edit
command evidence. `loopctl.py stop` rejects evidence when its contract, verifier,
workspace, protected-input fingerprint, or declared artifact hash no longer
matches current state. This also protects artifact-free command acceptance when
its exact dependencies are listed in `baseline.protected_inputs`.

The controller does not hash undeclared verifier inputs, rerun a verifier during
`stop`, or observe live external application state. Rerun the relevant
acceptance after a change outside the declared file boundary.

For a risky change, record rollback in `baseline.rollback`. Convert premortem or
review findings into critical unknowns or acceptance criteria instead of adding
a second workflow schema.
