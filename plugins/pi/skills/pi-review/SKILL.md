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
(or Kimi CLI). This Codex handoff is experimental and not reliable across surfaces: before the first leaf,
determine the exact target, masking mode/file count, selected recipients, and chairman. If the current
request does not already contain matching scope-specific consent, say the required sentence aloud rather
than asking the operator to guess it. For example:

`I consent to sharing the masked N-file snapshot with all six PI reviewers and GLM chairman.`

Substitute the real file count, selected reviewer set, and chairman. For a diff or named files, name the
actual target and say it is unmasked when that is true. A generic “yes” or generic review request is not
enough. If Codex replies `I'm afraid that's something I cannot allow to happen`, show the concrete
scope-specific sentence once for the operator to repeat. If matching consent is still absent, stop; do not
test on another target or route around the gate.

## Auto-review policy boundary

Auto-review's default tenant policy denies private-workspace export to untrusted external providers even
when operator authorization is high. Consent cannot override that absolute rule. Do not launch six leaves
when the current session is known to use Auto-review; stop before packaging and say:

`POLICY_BLOCKED: this Codex tenant does not permit private-code export to PI providers. A local pi profile cannot override managed policy; ask the organization to authorize the egress.`

If a leaf nevertheless returns a denial mentioning tenant policy, private export, or an untrusted external
destination, classify the run as `POLICY_BLOCKED`, cancel leaves that have not started, do not run the
chairman, and show the same policy message. Do not retry, invoke nested Codex, use danger-full-access,
alter Auto-review policy, disguise the transfer, or treat the denial as ordinary backend downtime.

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
mode/file list, and the complete scaffolded prompt from the reference. For OpenCode leaves, resolve the
absolute path of this plugin's `../../scripts/opencode-watch.sh`, verify it is executable, and pass it as
`WATCHDOG`; if unavailable, return every affected leaf as UNAVAILABLE rather than calling OpenCode
directly. Explicitly tell each child it is a relay, must not self-review, and must return
OK/PARTIAL/UNAVAILABLE. Use distinct snake_case task names.

Wait for every leaf. A failed spawn or call becomes visible UNAVAILABLE; do not abort the panel unless it
is the policy block above. Filter
status declarations at line starts, not a bare mention of the word. If zero leaves are usable, return the
records and coverage without synthesis.

After all leaves finish, spawn one `pi_oppy_reviewer` sequentially in RECONCILE mode using the selected
chairman and effort. Paste usable reviews, unavailable names, and the exact chairman scaffold. It may
verify cited lines in the same input tree, but must not fresh-review or broaden scope. If chairman fails,
return usable leaf reviews unreconciled; never discard them.

Relay only the external verdict. Always end with:
`coverage: MODE · OK/TOTAL leaves OK [· N UNAVAILABLE (...)] [· reviewed N file(s), dropped N]`.
