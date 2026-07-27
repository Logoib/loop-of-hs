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
- For a high-risk premortem, run fresh read-only Thesis and Anti-thesis roles
  independently from the same frozen task packet, then pass both outputs to a
  fresh Synthesis role. Keep the preferred plan out of Anti-thesis context.
- After a candidate artifact exists and the user authorizes cross-provider
  review, invoke `$claude-adversarial-review`. It uses the authenticated
  Claude subscription and consumes Claude plan usage.

Do not add custom agent profiles merely to encode the role table. Add them after
a real run shows that prompt routing or inheritance is insufficient.

## Claude Code

- Verify account availability before pinning models.
- Prefer Fable 5 for coordination, current Opus for difficult reasoning, and
  current Sonnet for bounded implementation or research when available.
- Use `/goal` for serial convergence. Use dynamic workflows or `ultracode` only
  for substantive repeatable fan-out or pipelines.
- For a high-risk premortem, run fresh read-only Thesis and Anti-thesis roles
  independently from the same frozen task packet, then pass both outputs to a
  fresh Synthesis role. Use named fresh subagents, new non-resumed sessions, or
  skill `context: fork`; do not use a parent-history `/subtask` fork.
- After a candidate artifact exists and the user authorizes cross-provider
  review, invoke `/codex:adversarial-review`.

## Fallback

Preserve roles rather than brand names: strongest coordinator, independent
reviewer when risk warrants it, and bounded workers. Report substitutions in
Korean. Use filesystem, Git, and native agent primitives; add MCP only for live
permission-scoped external systems or shared cross-machine state.
