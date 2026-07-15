---
name: pi-review
description: Run PI's low/med/high multi-model code-review council through native Codex subagents and return one reconciled verdict with truthful coverage.
---

# PI Review for Codex

You orchestrate; external models review. Never write findings yourself or substitute for an unavailable
leaf. Read `../../references/pi-council.js` for the exact model registry, reviewer scaffold, lenses,
chairman scaffold, retry semantics, and coverage format before running a council.

Use Codex's native collaboration/subagent tool surface only. Never invoke `codex`, `codex exec`, the
Claude Workflow JS, or any shell-based Codex child as a fallback. If native subagent spawning is not
available in the current Codex surface/session, stop and say that PI requires a new interactive Codex
app, CLI, or IDE thread with subagents loaded. An unavailable native mechanism is not permission to
invent a subprocess implementation.

Read `${CODEX_HOME:-$HOME/.codex}/pi.json` if present. Supported defaults are `tier`, `chairman`, and
`kimiMode`. Per-call values override it. Built-ins: tier `med`, chairman `glm-5.2`, Kimi mode `opencode`.
Accept operator tiers exactly `low|med|high`; reject old aliases.

- low: MiniMax-M3, DeepSeek-V4-Pro, MiMo-V2.5-Pro; provider effort low.
- med: GLM-5.2, Qwen3.7-Max, Kimi K2.7-Code; provider effort medium. Default.
- high: all six; provider effort high.

Kimi mode is `opencode|cli|off`; it applies only to med/high. Chairman may be any registered OpenCode-Go
alias/family. Require `opencode`. Default target is `git diff HEAD` in the current repo.

PI sends the selected code/diff and review prompts to third-party model endpoints through OpenCode-Go
(or Kimi CLI). Before the first leaf, state exactly what target will be sent and ask for explicit consent
unless the operator's current request already explicitly approves that third-party disclosure. Merely
asking for a generic code review is not enough. If consent is absent, stop; do not test on another target
or route around the gate.

For a diff, branch, or named files, review that exact target as-is. For a whole repo or bare directory:

1. Explicit `mode=yolo|curated|list|pack` wins. Yolo is explicit-only and sends raw source.
2. Specific area -> curated list. Otherwise run `../../scripts/pi-filelist.sh WORKDIR [SUBPATH]`.
3. At most 50 files -> list. More -> offer repomix first; never run it without approval. Decline or
   unavailable -> capped list with a visible degrade note.
4. For list/curated, run `../../scripts/pi-stage.sh WORKDIR [SUBPATH]` and use the returned staged tree.
   It fails closed: on masking error abort, never send raw source. Pack relies on repomix secretlint.
5. Preserve file and dropped counts for the coverage footer.

Spawn one native `pi_oppy_reviewer` subagent per OpenCode leaf, in parallel. For Kimi CLI mode spawn
`pi_kimi_reviewer` instead. Give every child exactly one alias, provider variant, workdir, target, access
mode/file list, and the complete scaffolded prompt from the reference. Explicitly tell each child it is a
relay, must not self-review, and must return OK/PARTIAL/UNAVAILABLE. Use distinct snake_case task names.

Wait for every leaf. A failed spawn or call becomes visible UNAVAILABLE; do not abort the panel. Filter
status declarations at line starts, not a bare mention of the word. If zero leaves are usable, return the
records and coverage without synthesis.

After all leaves finish, spawn one `pi_oppy_reviewer` sequentially in RECONCILE mode using the selected
chairman and effort. Paste usable reviews, unavailable names, and the exact chairman scaffold. It may
verify cited lines in the same input tree, but must not fresh-review or broaden scope. If chairman fails,
return usable leaf reviews unreconciled; never discard them.

Relay only the external verdict. Always end with:
`coverage: MODE · OK/TOTAL leaves OK [· N UNAVAILABLE (...)] [· reviewed N file(s), dropped N]`.
