# Runtime routing

Official behavior below was verified on 2026-08-27 against Claude Code's
[`/goal`](https://code.claude.com/docs/en/goal),
[`hooks`](https://code.claude.com/docs/en/hooks),
[`commands`](https://code.claude.com/docs/en/slash-commands),
[`subagents`](https://code.claude.com/docs/en/sub-agents),
[`context window`](https://code.claude.com/docs/en/context-window), and
[`extension overview`](https://code.claude.com/docs/en/features-overview).

## Capability matrix

| Capability | Codex | Claude Code | loop-code rule |
|---|---|---|---|
| Goal activation | Native goal tool when exposed | User runs `/goal`; assistant has no activation/status tool | triage first; Plan/Loop only |
| Durable task/evidence | v4 ledger | v4 ledger | ledger remains authoritative across sessions |
| Goal resume | Host-defined | active condition restored on `--continue`, named/ID `--resume`, and picker | turn/time/token baselines can reset; ledger bounds remain durable |
| Completion evaluation | host goal contract | prompt Stop hook sees conversation only; it calls no tools | surface exact verifier result in conversation |
| Skill hook lifetime | host-defined | rest of current session once invoked | not a multi-session gate; v4 ships no skill Stop hook |
| Subagent context | host-defined | non-fork starts fresh; fork inherits conversation | pass a packet or preload skills explicitly |

## Claude Code contract

`/goal` is a built-in shortcut for a session-scoped prompt-based `Stop` hook.
Its evaluator cannot read files or run the verifier; it judges only facts Claude
already surfaced in the conversation. Therefore the ready-to-paste condition
must name the exact command, expected exit/output, preservation constraint, and
turn/time bound.

The user activates it. The assistant must not claim it ran `/goal` or inspected
active state. `/goal` without arguments is the user's status check. An active
condition is restored on supported resume routes, but turn count, timer, and
token-spend baseline reset on resume. The ledger is what preserves cumulative
task state and evidence.

Claude's hook reference says a skill-frontmatter hook lasts for the rest of the
current session once invoked; a subagent-frontmatter hook lasts only while that
subagent runs. Neither statement makes a skill hook a durable resume contract.
v4 therefore removes the skill `Stop` hook instead of installing settings or a
plugin.

For any Stop hook, `stop_hook_active: true` means Claude is already continuing
because a Stop hook blocked. It is a re-entry signal, not proof that a cap was
reached. Claude Code separately overrides the hook after 8 consecutive blocks.

A normal non-forked subagent starts with fresh isolated context and does not see
parent conversation, previously invoked skills, or previously read files.
Forks inherit parent conversation; named skills can be preloaded through the
subagent definition. Subagent lifetime and resume are independent of the main
ledger.

Skills are procedures that require model judgment, hooks are deterministic
lifecycle enforcement, and subagents isolate work context. Adding Claude
support does not require separate orchestration code.

## Cross-provider review

Detect optional review skills/plugins before use. Ask for explicit approval
before sending repository content to another provider or consuming paid plan
usage. If unavailable or unapproved, use a fresh local independent review. Do
not edit `settings.json`, create a plugin, or make a provider mandatory.

## Three-minute manual smoke test

No chargeable `claude -p` run is part of routine validation. To test manually
with a non-sensitive temporary fixture:

1. Start trusted Claude Code and invoke `$loop-code` with a two-step Plan task.
2. Confirm it chooses Plan before printing exactly one `/goal ...` line and does
   not claim activation; paste the line, then run `/goal` to inspect it.
3. Confirm the condition names an exact verifier result and bound. Resume the
   session with a supported route and check that the condition returns, while
   the ledger/evidence remains the durable cumulative record.

If hooks are disabled or unavailable, confirm the skill reports the limitation
once and continues with a bounded ledger.
