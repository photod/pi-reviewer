---
name: pi-config
description: Configure the PI council — models, tier rosters, chairman, Kimi backend. Writes ~/.claude/pi.json; `doctor` verifies it against your live plan.
argument-hint: "[show|doctor|models] · [set tier|chairman|kimiCliModel <v>] · [model <family> <alias>] · [tier <name> <family...>] · [ondemand <alias> <stand-in>] · [reset]"
---

# /pi-config — the one door for council settings

Everything the council can be told lives in **one file, `~/.claude/pi.json`**, and one script owns
its shape: `${CLAUDE_PLUGIN_ROOT}/scripts/pi-config.sh`. You are a thin, friendly front end to that
script. **Do NOT edit `pi.json` by hand, and never edit the engine** — `/pi-review` force-copies the
plugin's `pi-council.js` over the installed one whenever they differ, so an engine edit is wiped on
the next run. Config, not sed.

## How to run it

Everything goes through the script — it owns validation, atomic writes, and the plan check:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/pi-config.sh" <args> < /dev/null
```

1. **No arguments** → run `show` and relay the output. Then offer, in one line, the three things
   people usually want: change a model, change who reviews at a tier, or move the Kimi leaf.
2. **Arguments that already match the script's own grammar** (`show`, `doctor`, `models`, `set …`,
   `model …`, `tier …`, `ondemand …`, `reset …`) → pass them through verbatim.
3. **Plain English** → translate to exactly one command, run it, and say what changed:
   - "use minimax 2.7" / "pin minimax" → `model minimax minimax-m2.7`
   - "use glm 5.3" → it already IS the med/high leaf (the `glm53` family). `glm` stays 5.2 because it
     is the default chairman — do not repoint it without saying so.
   - "use my own kimi CLI" / "add K3" → `tier <name> --kimi-cli on` (it is off in every tier by
     default). "turn the Go-plan kimi off" is a DIFFERENT thing → drop `kimicode` from that tier's
     family list. Never conflate the two: `kimicode` is Go-plan K2.7-Code, `--kimi-cli` is K3 on the
     operator's own subscription.
   - "drop minimax from high" → read `show` first, then `tier high <the remaining families>`
   - "make opus the chairman" → `set chairman opus`
   - "put deepseek in med" → read `show`, then `tier med <existing families> deepseek`
   - "why is everything broken" / "check my setup" → `doctor`
   - "start over" → `reset` (confirm first — it deletes the file)
4. **Never invent a model alias.** If the operator names a model you are not sure exists, run
   `models` first and pick from what their plan actually carries. The script refuses off-plan
   aliases anyway (that refusal is the typo guard — an off-plan alias does not error at the backend,
   it hangs the leaf for ten minutes), but a wrong guess wastes a round trip.

## What can be configured

| | |
|---|---|
| `set tier low\|med\|high` | which tier `/pi-review` uses when you do not name one |
| `set chairman <opus\|sonnet\|family\|alias>` | who reconciles the panel into one verdict |
| `set kimiCliModel <cli-alias>` | which model the Kimi CLI leaf runs (default `kimi-code/k3-256k` — the **CLI** spelling, not opencode's `kimi-for-coding/…`) |
| `model <family> <alias>` | pin a family to a model — this is how you bump a version |
| `tier <name> <family...>` | who reviews at that tier (`--kimi-cli on\|off`, `--effort <level>` too) |
| `ondemand <alias> <stand-in>` | mark a model opt-in-only and name its automatic stand-in |
| `reset [key]` | drop one key, or the whole file |

Tier NAMES are fixed at `low|med|high` — that is `/pi-review`'s input contract. Membership is not.

## On-demand models

One model is opt-in per run (`qwen3.8-max` by default — new flagships are never auto-adopted).
**Consent cannot be stored** — a config saying "always use the pricey
one" is exactly the automatic use the gate exists to prevent. So `pi.json` only holds the downgrade
map; to actually use one, the operator names it on the run:

```
/pi-review high --with qwen3.8-max
```

If an on-demand model is reached without that confirmation, the council runs its stand-in and says so
in the `coverage:` footer. Explain that if someone asks why they got 5.2 instead of 5.3.

## Barred vendors — stronger than on-demand

Two vendors never run on the Go plan, and **no `--with` unlocks them**: any `grok-*` (priced far above
what this council is for), `qwen3.7-plus` (benchmarked at 1 real bug in 10), and any `kimi-*` other
than `kimi-k2.7-code` (K3 is the `kimi-reviewer` CLI
leaf's job, on the operator's own subscription). They are SUBSTITUTED, not refused — the panel keeps
its width and the footer names the swap.

The rules key on the **vendor**, not the version, so a new `grok-5` is caught the day it ships. If
someone asks for Grok, say plainly that the plan bars it and offer `luna` — do not try to route around
it with `--with`, which is reported as REFUSED in the log.

## After a change

Say what changed in one line, and — if a model or roster moved — suggest `doctor` when anything looks
uncertain. Do NOT re-run the whole review to "test" a config change.
