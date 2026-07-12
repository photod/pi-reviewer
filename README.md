# Poor Intelligence

PI, not AI.

It's a code review tool that does the obvious-in-hindsight thing: instead of paying one expensive model to look at your code, it asks a handful of cheap ones and lets them fight about it, then a chairman reads the fight and hands you a single verdict.

The name is a price tag, not an insult. Poor as in cheap, not poor as in dim — these models are, officially, in the frontier's league. GLM-5.2 lands within a few points of the best closed models on real coding benchmarks, and the rest aren't far off; they just cost pennies a call instead of dollars. So yes, it's poor-man's AI, and the poor man is getting six frontier-grade reviewers for a flat monthly fee. The bet is that six strong models with different blind spots cover more ground than one expensive model with a single blind spot, and running all six costs about nothing. Poverty of price, not of intelligence. That's the thesis.

## Why this council

Three deliberate choices separate it from a one-model reviewer. A **council**, because one model has one blind spot and six have six small ones that barely overlap. An **arbiter** — the chairman — because a stack of raw, conflicting reviews is worse than none; something has to decide what's real and hand you a single list. And **modes**, a dial from a quick three-model pass to the full six-model panel with a heavier synthesis, because scratching a diff and auditing before a merge are not the same job. That part has to be a plugin, not a clever prompt.

Multi-model orchestrators already exist, so why another? Because most of them wire together two or three expensive frontier models and bill you per run — you save those for the commits that scare you. This one inverts it: six cheap, frontier-league models on a flat plan, so the panel is wider, the disagreement richer, and a review costs close to nothing. The experiment below is the case for it: the cheap, wide panel out-covered the pricey, narrow ones. Free opinions change the habit. You ask on every diff, not just the frightening ones.

## Does it actually work

On easy bugs it's a wash. One decent model spots the missing null check; so does the council; you didn't need a committee for that.

The interesting case is real code. I pointed it at a mid-development C/C++ audio synth — itself written by an AI, which is exactly the kind of code that hides bugs that look fine — and had the maintainers triage whatever came back. Sixty-one findings. Thirty-six were real: seventeen already fixed and test-verified, nineteen confirmed and queued. The other twenty-five got rejected — the mechanism doing its job. You want a wide, noisy net and someone at the end who throws the garbage back.

The part worth the ticket was that nobody won alone. Opus caught a nasty allocator bug and missed an entire family of serialization gaps. The Codex models owned the serialization gaps and walked straight past the concurrency ones. A two-cent Qwen run turned up eight allocator races that no other reviewer — frontier, Codex, or otherwise — caught. The edge is that cheap models go blind in different places: their blind spots barely overlap, and everything they *do* see stacks up.

Numbers are in [EXPERIMENT.md](EXPERIMENT.md).

## You need opencode first

This is a front-end. The reviewing happens through the opencode CLI on an opencode-go plan — a pile of cheap models for a flat monthly fee. No opencode, nothing runs, and the command will tell you as much.

- https://opencode.ai/go?ref=RWGQD6Q9RA — referral link. You get five dollars, I get five dollars. Use it if that sits fine with you.
- https://opencode.ai/go — the same thing without the referral, if it doesn't.

## Install

```
/plugin marketplace add photod/pi-reviewer
/plugin install pi@pi-reviewer
```

Restart the session so the command registers, then run `/pi-review high <target>`. It installs its own review engine the first time you use it.

## Running it

```
/pi-review                     review the current diff, default settings
/pi-review ultra src/engine    the whole council, on a path
/pi-review med diff opus       cheaper panel, Opus in the chair
```

The three tiers, spelled out:

- **med** — MiniMax-M3, DeepSeek-V4-Pro, MiMo-V2.5-Pro. Cheap and quick, for a routine diff.
- **high** *(default)* — GLM-5.2, Qwen3.7-Plus, Kimi K2.7-Code. The one you'll reach for most days.
- **ultra** — all six of the above, plus a heavier reconciliation pass. For a pre-merge audit, or when the change scares you.

Why those six and not some other set? Nothing handed me the list — it's the combination I've landed on and trust. Each one is strong on its own, and, more to the point, they're different enough that they don't all trip on the same things. Six great models that think alike would be worth one. These six disagree, usefully. That's why they're the ones.

## Changing the defaults

Nothing to set up to get going. For different defaults for good, drop a `~/.claude/pi.json`:

```json
{ "tier": "high", "chairman": "glm-5.2", "kimiMode": "opencode" }
```

The chairman defaults to GLM-5.2 — an affordable smarty: cheap to run, frontier-league in ability, and reconciling a stack of reviews is well within it. Point it at `opus` or `sonnet` if you specifically want a closed frontier model in the chair. Command-line arguments still win for a single run.

## Where it doesn't help

It's a cost play, not sorcery. On the bugs any competent reviewer would catch it's a tie, and paying for six opinions to confirm what one already told you is silly. The value is entirely on messy, divergent, real code, and even there the raw output has junk in it — the chairman exists because a stack of cheap reviews needs someone to decide which ones are true. Point it at your working tree mid-project, when a second read still changes what you do next. It's a reviewer, not a rubber stamp for the night before release.

## Built and reviewed by

Opus 4.8 did most of the building. GPT-5.6, GPT-5.5, and GLM-5.2 reviewed the code. And PI reviewed itself — a full ultra-tier pass of the council over its own source.

Not AI. PI.
