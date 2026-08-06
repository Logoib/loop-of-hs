# Runtime routing

Read this only after triage selects Loop.

## Codex

- On explicit `$loop-code` invocation, use the runtime goal tools as specified
  in `SKILL.md`; the user should not need to prefix the request with `/goal`.
- If goal tools are unavailable in an older client, fall back to
  `/goal Use $loop-code to achieve: <one-line objective>` and report the
  fallback.
- Prefer GPT-5.6 Sol `xhigh` for coordination, planning, premortem, synthesis,
  and final review. Keep these roles on Sol unless repository-specific UAT
  shows that a cheaper model preserves semantic and safety decisions.
- Prefer Luna `max` for bounded implementation and read-heavy exploration when
  acceptance criteria are clear and command-verifiable. Treat it as a
  cost-optimized worker, not a low-token or low-latency worker.
- Escalate to Sol `high` for difficult or ambiguous implementation, weak
  verifiers, external or persisted state, or a deterministic Luna failure that
  needs stronger reasoning. Preserve one independent Sol `xhigh` final gate;
  do not route every role to Luna by default.
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

- The `SKILL.md` frontmatter installs a skill-scoped prompt `Stop` hook, the
  supported automatic equivalent of Claude Code's session-scoped `/goal`
  shortcut. Do not try to nest `/goal` inside the expanded skill prompt.
- Verify account availability before pinning models.
- Prefer Fable 5 for coordination, current Opus for difficult reasoning, and
  current Sonnet for bounded implementation or research when available.
- Use the scoped goal hook for serial convergence. Use dynamic workflows or
  `ultracode` only for substantive repeatable fan-out or pipelines.
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
