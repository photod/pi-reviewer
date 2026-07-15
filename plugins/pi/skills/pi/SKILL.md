---
name: pi
description: Main entry point for Poor Intelligence in Codex. Classify a request as council review or scoped build, then run the matching low/med/high native subagent workflow.
---

# Poor Intelligence Router

Accept operator tiers exactly `low|med|high`; default to `med`. Do not accept legacy tier aliases.

Classify the requested outcome:

- Review: review, audit, inspect, critique, find bugs, second opinion, current diff, branch, path.
- Build: implement, add, change, fix, refactor, or write code/tests.

Then execute the matching bundled skill in this thread: review -> `$pi-review`; build -> `$pi-build`.
Preserve the tier, target/task, chairman, Kimi mode, and implementer model. If the request truly does not
reveal whether files should change, ask one short question; otherwise route automatically.

Before either path, require `opencode` and run both `python3 ../../scripts/manage_agents.py check` and
`python3 ../../scripts/manage_profile.py check` from this skill directory. If either is missing, invoke
`$pi-setup`; activation requires a new thread launched with
`codex -p pi --sandbox workspace-write -C WORKDIR`.

PI may use only native Codex subagents. Never emulate them with nested `codex exec` or another Codex
subprocess. The selected review/build input is sent to third-party OpenCode-Go/Kimi endpoints, so the
matching skill must enforce its explicit disclosure-consent gate before execution.

## Experimental Codex consent handoff

This integration is experimental: a generic “yes” or a generic request to review can be rejected before
the council starts. Do not make the operator guess what wording Codex needs. Once the target, recipient
set, and chairman are known, say the exact scope-specific sentence aloud and ask the operator to repeat
it if their current request did not already say it. For a masked whole-repo snapshot, use this shape:

`I consent to sharing the masked N-file snapshot with all six PI reviewers and GLM chairman.`

Replace `N`, the reviewer count/set, and `GLM` with the actual run facts. For a diff, named files, or a
builder input, name that exact unmasked target instead of claiming it is masked. Never launch external
leaves from generic consent alone. If Codex replies `I'm afraid that's something I cannot allow to happen`,
present this concrete sentence once before treating it as a policy block; a repeated scope-specific denial
is `POLICY_BLOCKED`, not a reason to evade policy.
