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

Before either path, require `opencode` and run `python3 ../../scripts/manage_agents.py check` from this
skill directory. If profiles are missing, invoke `$pi-setup`; activation requires a new thread.

PI may use only native Codex subagents. Never emulate them with nested `codex exec` or another Codex
subprocess. The selected review/build input is sent to third-party OpenCode-Go/Kimi endpoints, so the
matching skill must enforce its explicit disclosure-consent gate before execution.
