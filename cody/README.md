# cody — the Codex corner

A small **bonus** plugin that sits in the corner of the [pi-reviewer](../README.md) marketplace: two
agents backed by the **OpenAI Codex CLI** (`codex`), a genuinely non-Claude, non-opencode voice.

- **`cody-reviewer`** — a read-only code review from Codex, coached with the same **Fable review scaffold**
  the PI council uses (the five strong-model moves). A relay: it returns *Codex's* findings, never its own.
- **`cody-worker`** — Codex in **write mode** (`codex exec --full-auto`): delegate a scoped, mechanical
  change and it edits on disk; you verify. For bounded work, not sprawling features.

This is deliberately separate from the main `pi` plugin (which is a self-contained opencode-go council —
one cheap plan, no OpenAI dependency). `cody` is here for people who *also* have a Codex subscription and
want that arm on the panel.

## Requires the Codex CLI

`cody` shells out to `codex` (OpenAI Codex CLI) — install and authenticate it first, or both agents just
return `UNAVAILABLE`:

```
which codex        # must resolve
codex --version    # verified against codex-cli 0.145.0
```

Bring-your-own-CLI: `cody` ships **no** Codex credentials and makes **no** API calls of its own — it only
invokes your local, authenticated `codex`.

## Install

```
/plugin marketplace add photod/pi-reviewer
/plugin install cody@pi-reviewer
```

Then spawn `cody-reviewer` (read-only 2nd opinion) or `cody-worker` (write mode) as a subagent.

## Honest caveats

- **`cody-worker` writes to disk.** `codex exec --full-auto` is workspace-write with no approval prompt.
  It's scoped by the prompt + a post-hoc `git diff` check, **not** an OS sandbox — point it only at code
  you can share with OpenAI, and review the diff before committing (the agent never commits).
- **`cody-reviewer` is read-only** (`--sandbox read-only`) and sends the target code to OpenAI's Codex —
  same privacy footprint as any Codex use. Unlike the whole-repo `/pi-review` path, there is **no masking
  layer here**; don't point it at secrets.
- **Codex keeps a transcript of everything it read.** Every `codex exec` run persists a full session
  rollout under `~/.codex/sessions/` — raw, unmasked, unencrypted, kept indefinitely (mine is already
  ~500 files / 128 MB). That's a local disk footprint the `/pi-review` masking layer does **not** cover,
  and it's Codex's behaviour, not PI's. `codex exec --ephemeral` runs without persisting session files if
  you'd rather it left nothing behind; prune the directory otherwise.
- **Planted instructions are ignored.** Both agents treat any instruction embedded in the code they read —
  an *"ignore the above"* comment, a *"TODO: also delete…"* line — as content to flag, never a command to
  obey (the worker is told the same about files it reads while editing). Best-effort prompt hardening, not a
  guarantee.
- The Fable scaffold in `cody-reviewer.md` is a byte-identical copy of `recipes/reviewer.md`, guarded by
  the repo's `test/scaffold_sync_test.mjs` so it can't drift.
