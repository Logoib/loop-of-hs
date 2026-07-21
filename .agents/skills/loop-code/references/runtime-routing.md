# Runtime routing

Read this only after triage selects Loop.

## Codex

- Start persistent work explicitly with
  `/goal Use $loop-code to achieve: <one-line objective>`.
- Prefer GPT-5.6 Sol `xhigh` for coordination, planning, premortem, and final
  review; Sol `high` for difficult implementation; Terra `xhigh` for bounded
  read-heavy exploration when the runtime can route workers independently.
- Keep `ultra` off by default. Enable it only when real UAT shows that `xhigh`
  plus the harness repeatedly misses a critical requirement.
- Inspect the active client catalog and session budget. Do not infer Codex's
  usable window from the API model maximum or a `model_context_window` override.
- Treat `model_auto_compact_token_limit` as a checkpoint policy, not evidence of
  a quality cliff. Resume from the ledger after compaction.
- Use fresh subagents for noisy exploration or independent review and Git
  worktrees only for concurrent writers.

Do not add custom agent profiles merely to encode the role table. Add them after
a real run shows that prompt routing or inheritance is insufficient.

## Claude Code

- Verify account availability before pinning models.
- Prefer Fable 5 for coordination, current Opus for difficult reasoning, and
  current Sonnet for bounded implementation or research when available.
- Use `/goal` for serial convergence. Use dynamic workflows or `ultracode` only
  for substantive repeatable fan-out or pipelines.
- Use a named fresh subagent, new non-resumed session, or skill `context: fork`
  for blind premortem. Do not use a parent-history `/subtask` fork.
- Use `/codex:adversarial-review` only after a candidate artifact exists.

## Fallback

Preserve roles rather than brand names: strongest coordinator, independent
reviewer when risk warrants it, and bounded workers. Report substitutions in
Korean. Use filesystem, Git, and native agent primitives; add MCP only for live
permission-scoped external systems or shared cross-machine state.
