# Ledger contract

Read this only when initializing or repairing a Loop ledger.

Set `baseline.workspace` explicitly. It may be an absolute project path or a
path relative to the ledger directory; for `.loop/<task-id>/loop-ledger.json`,
`../..` normally names the project root. An empty value intentionally makes the
run directory the workspace and is unsuitable for normal repository checks.

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
  "artifacts": [],
  "status": "open",
  "user_accepted": false,
  "human_evidence": ""
}
```

Only the user can set `user_accepted: true`. A model observation is not a human
acceptance substitute.

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
or declared artifact hash no longer matches current state.

For a risky change, record rollback in `baseline.rollback`. Convert premortem or
review findings into critical unknowns or acceptance criteria instead of adding
a second workflow schema. Capture and verify a final fingerprint when another
agent reviews mutable artifacts.
