---
name: pi-build
description: Run PI's low/med/high scoped external-model TDD builder through one native Codex worker, with independent tests and report-only review.
---

# PI Build for Codex

This is the bonus small-change builder. It sends target code raw; warn when that matters. Read
`../../references/glm-worker.md` before spawning the worker; its relay, TDD, scope, fallback, and report
contracts are authoritative.

Use native Codex subagent spawning only. Never invoke `codex`, `codex exec`, or a shell-based Codex child.
If native spawning is unavailable, stop and require a new interactive Codex app, CLI, or IDE thread.
Before the worker sends raw code to OpenCode-Go/Kimi, obtain explicit current-request consent to that
third-party disclosure; naming `$pi-build` alone is not informed consent unless the request says so.

Read `${CODEX_HOME:-$HOME/.codex}/pi.json` if present (`tier`, `buildModel`). Per-call overrides win.
Defaults: tier `med`, model `glm`. Accept tiers exactly `low|med|high` and implementer families exactly
`glm|qwen|minimax|deepseek|mimo`.

Map tiers to provider variants low->low, med->medium, high->high. High also requires a read-only TDD plan.
Require `opencode`. Derive a checkable spec: outcome, named scope, out-of-scope, acceptance criteria, and
exact verification command. If no defensible pass/fail command can be derived, ask; do not invent one.

Spawn exactly one native `pi_glm_worker` subagent. Pass the full spec, tier, resolved alias, workdir, and
bundled worker contract. The worker runs write legs sequentially and never commits. Wait, then independently
inspect status/diff and run final acceptance in the main thread. Relay its report plus your verification.
Never commit unless separately asked. Recommend `$pi-review` for a heavyweight review of the result.
