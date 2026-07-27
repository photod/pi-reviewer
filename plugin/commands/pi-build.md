---
name: pi-build
description: PI's builder — bonus companion to /pi-review. Delegates a scoped TDD change to GLM-5.2; a second model augments tests, a cross-model pass reviews the diff.
argument-hint: "[low|med(default)|high] <task description and/or target files> [implement model: glm(default)|qwen|minimax|deepseek|mimo]"
---

# /pi-build — Poor Intelligence code builder (GLM-5.2 worker)

Delegate a **scoped implementation batch** to the `glm-worker` agent and relay its report. You
orchestrate; you do NOT write the product code yourself — GLM-5.2 (via opencode-go) authors it, a
different model augments the tests, and a cross-model pass reviews the diff. This is the build-side
companion to `/pi-review`: same cheap opencode-go plan, same Fable-5 discipline, applied to writing code.

> **Bonus, not the headline.** PI's one job is review (`/pi-review`). `/pi-build` is a bonus for the
> opencode-go plan you already bought — reach for it on well-scoped changes, not sprawling features.
>
> **Privacy:** `/pi-build` sends the target code to the model **as-is** — it does NOT stage a redacted
> copy the way whole-repo `/pi-review` does. Same rule as a diff review: don't point it at code you can't
> share. To check what a secret-masker would flag first, ask in chat ("what would PI mask in
> `<path>`?") or run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pi-mask.py --preview <path>` yourself.

## Resolve config — standing host config FIRST, then per-call overrides

1. **Standing config:** if `~/.claude/pi.json` exists, read it for defaults (keys shared with the council:
   `tier`; build-specific: `buildModel`). **No file → built-in defaults:** `tier=med`, `buildModel=glm`.
2. **Per-call overrides** from `$ARGUMENTS` (this run only): a tier keyword (`low`/`med`/`high`), the
   **task** (a description and/or the target files — everything that isn't a recognized keyword), and an
   optional implement-model family — `glm` (default) or **any** opencode-go family (`qwen` · `minimax` ·
   `deepseek` · `mimo`). The worker resolves its test-augmenter and diff-reviewer to a family DIFFERENT
   from the implementer, so any choice keeps cross-family review intact — no collision.

Tiers scale the backend reasoning hint, not the model: `low`→low · `med`→medium · `high`→high
(+ a TDD-plan-first pass at high). `max` / `ultra` are accepted as aliases for `high`. There is no cost gate.

## Execute — self-contained, single agent

0. **Preflight — `opencode` is REQUIRED.** Run `command -v opencode`. Missing → STOP (do not run the
   worker) and show the operator:
   > **PI needs the `opencode` CLI + an opencode-go plan** to run the builder (required prerequisite).
   > - https://opencode.ai/go?ref=RWGQD6Q9RA — **referral: you get $5 credit and PI's author gets $5** (disclosed; use it if you're happy to).
   > - https://opencode.ai/go — plain link, no referral.
   >
   > Install opencode, then re-run `/pi-build`.

1. **Assemble a task spec — the worker REFUSES without a checkable definition of done.** From the task +
   the repo, produce: (a) the goal as an *outcome* ("export must include all rows", not "fix export");
   (b) the target files (name them); (c) **explicit acceptance criteria** — the exact test/verify command
   that will prove it (`./run.sh test`, a pytest target, a build). If the task has no checkable done-state
   and you cannot derive one from the specs/tests, **do NOT invent it** — ask the operator for the
   acceptance command instead of guessing.

2. **Spawn the worker** with the Agent tool — `subagent_type: "pi:glm-worker"`. Installed as this plugin,
   Claude registers the worker under the `pi:` namespace; a manual install (the agent `.md` dropped into
   `~/.claude/agents/`) registers it BARE. Check YOUR available agent types and use whichever is listed —
   `pi:glm-worker` if present, plain `glm-worker` otherwise. The wrong one fails with "agent not found"
   before any model is contacted. Pass it: the **tier** (as a ceiling), the
   **task spec + acceptance criteria + scope/out-of-scope**, the **workdir**, and the **implement model**
   family if overridden. The worker runs its own pipeline: scout → implement (GLM) → verify → augment
   tests (a different model) → cross-model diff review — each leg sequential, none committed.

3. **Relay the worker's report** verbatim-ish: routing, status (done/partial/failed), diffstat +
   in-scope check, implemented-vs-task, tests (GLM TDD + augmenter + acceptance result), the cross-model
   diff-review findings (report-only), per-leg `OK|PARTIAL|UNAVAILABLE`, fix rounds, concerns. Surface any
   `UNAVAILABLE`/out-of-scope honestly.

4. **Never commit, never rubber-stamp.** The worker leaves the working tree for review. YOU (or the
   operator) run the gates and commit — a worker "done" plus your verification is done; the worker's word
   alone is a claim. For a heavyweight pre-commit check, hand the resulting diff to `/pi-review`.
