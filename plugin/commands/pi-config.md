---
name: pi-config
description: Configure the PI council — models, tier rosters, chairman, Kimi backend. Writes ~/.claude/pi.json; `doctor` verifies it against your live plan.
argument-hint: "[show|doctor|models] · [set tier|chairman|kimiMode <v>] · [model <family> <alias>] · [tier <name> <family...>] · [ondemand <alias> <stand-in>] · [reset]"
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
   - "use glm 5.3" → `model glm glm-5.3`, then warn that 5.3 is **on-demand**: normal runs will use
     glm-5.2 unless they confirm it per run with `--with glm-5.3`
   - "turn kimi off" → `set kimiMode off` · "use my own kimi CLI" → `set kimiMode cli`
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
| `set kimiMode opencode\|cli\|off` | where the Kimi leaf runs (opencode-go, your own `kimi` CLI, or nowhere) |
| `model <family> <alias>` | pin a family to a model — this is how you bump a version |
| `tier <name> <family...>` | who reviews at that tier (`--kimi on\|off`, `--effort <level>` too) |
| `ondemand <alias> <stand-in>` | mark a model opt-in-only and name its automatic stand-in |
| `reset [key]` | drop one key, or the whole file |

Tier NAMES are fixed at `low|med|high` — that is `/pi-review`'s input contract. Membership is not.

## On-demand models

Some models are opt-in per run (`glm-5.3`, `qwen3.8-max`, `kimi-k3`, `grok-4.5` by default — `glm-5.3`
is priced well above the flat plan, hence the gate). **Consent cannot be stored** — a config saying "always use Grok" is exactly the automatic use the gate exists to prevent.
So `pi.json` only holds the downgrade map; to actually use one, the operator names it on the run:

```
/pi-review high --with grok-4.5
```

If an on-demand model is reached without that confirmation, the council runs its stand-in and says so
in the `coverage:` footer. Explain that if someone asks why they got Luna instead of Grok.

## After a change

Say what changed in one line, and — if a model or roster moved — suggest `doctor` when anything looks
uncertain. Do NOT re-run the whole review to "test" a config change.
