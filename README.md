# Poor Intelligence

PI, not AI.

> **Claude Code + Codex plugin.** PI needs the `opencode` CLI and an opencode-go plan (about $10/month)
> on either host; no opencode, nothing happens. Claude runs the council through its Workflow API. Codex
> uses native custom subagents — no nested `codex exec`, no Codex-in-Codex subshell matryoshka.

It's a code review tool that does the obvious-in-hindsight thing: instead of paying one expensive model to look at your code, it asks a handful of cheap ones and lets them fight about it, then a chairman reads the fight and hands you a single verdict.

The name is a price tag, not an insult. Poor as in cheap, not poor as in dim — these models are, officially, in the frontier's league. GLM-5.2 lands within a few points of the best closed models on real coding benchmarks, and the rest aren't far off; they just cost pennies a call instead of dollars. So yes, it's poor-man's AI, and the poor man is getting six frontier-grade reviewers for a flat monthly fee. The bet is that six strong models with different blind spots cover more ground than one expensive model with a single blind spot, and running all six costs about nothing. Poverty of price, not of intelligence. That's the thesis.

## Why this council

Three deliberate choices separate it from a one-model reviewer. A **council**, because one model has one blind spot and six have six small ones that barely overlap. An **arbiter** — the chairman — because a stack of raw, conflicting reviews is worse than none; something has to decide what's real and hand you a single list. And **modes**, a dial from a quick three-model pass to the full six-model panel with a heavier synthesis, because scratching a diff and auditing before a merge are not the same job. That part has to be a plugin, not a clever prompt.

Multi-model orchestrators already exist, so why another? Because most of them wire together two or three expensive frontier models and bill you per run — you save those for the commits that scare you. This one inverts it: six cheap, frontier-league models on a flat plan, so the panel is wider, the disagreement richer, and a review costs close to nothing. The experiment below is the case for it: the cheap, wide panel out-covered the pricey, narrow ones. Free opinions change the habit. You ask on every diff, not just the frightening ones.

## Does it actually work

On easy bugs it's a wash. One decent model spots the missing null check; so does the council; you didn't need a committee for that.

The interesting case is real code. I pointed it at a mid-development C/C++ audio synth — itself written by an AI, which is exactly the kind of code that hides bugs that look fine — and had the maintainers triage whatever came back. Sixty-one findings. Thirty-six were real: seventeen already fixed and test-verified, nineteen confirmed and queued. The other twenty-five got rejected — the mechanism doing its job. You want a wide, noisy net and someone at the end who throws the garbage back.

The part worth the ticket was that nobody won alone. Opus caught a nasty allocator bug and missed an entire family of serialization gaps; the Codex models owned those gaps and walked straight past the concurrency ones. The same divergence held inside the cheap panel — GLM alone caught the codegen error that aborts the build, MiMo alone the loudness gate: real bugs each found that the others, frontier included, missed. The cheap models are also *noisier* — and here's an honest miss: we ran **Qwen3.7-Plus**, the wrong model. It flagged eight allocator concerns nobody else did but landed only one real bug in ten. We left it in the table below as a caution (**use `qwen3.7-max`, not `qwen3.7-plus`** — production now does); it's also exactly the kind of noise the chairman exists to filter. Their blind spots barely overlap, and everything they truly see, once filtered, stacks up.

Which is why the column that matters is **confirmed-real**, not raw finds — a model that sprays false alarms shouldn't score for the noise:

| System | Found | Confirmed-real | Lone-wolf |
|---|--:|--:|--:|
| Codex gpt-5.6-sol (solo, high) | 11 | 11 | 1 |
| Kimi | 17 | 15 | 6 |
| GLM-5.2 | 15 | 9 | 7 |
| Opus 4.8 (solo) | 7 | 6 | 1 |
| MiMo-V2.5-Pro | 13 | 6 | 7 |
| Sonnet 5 (solo) | 6 | 5 | 1 |
| DeepSeek-V4-Pro | 6 | 3 | 4 |
| **Qwen3.7-Plus** | 10 | **1** | 8 |
| MiniMax-M3 | 2 | 1 | 1 |

*Confirmed-real = held up under the maintainers' two-round triage (FIXED/CONFIRMED, not disputed). Lone-wolf = of those, how many no other reviewer caught.*

> ⚠️ **The Qwen3.7-Plus row is our own mistake, kept honest.** We benchmarked the wrong model: `qwen3.7-plus` is noise — one real bug in ten. Production runs **`qwen3.7-max`** instead — and a rerun against the same code validated it as a real reviewer: it independently re-found the panel's headline save/load bug. (Like every cheap model it also emitted false positives — a couple of its "findings" didn't survive a source check — which is precisely why the chairman and triage exist, not a mark against it.) **Don't use `qwen3.7-plus` for review** — use `qwen3.7-max`.

One repo, one run — not a benchmark claim, just what happened here. Full breakdown, including which finds actually held up under triage, in [EXPERIMENT.md](EXPERIMENT.md).

**qwen3.7-max — validation rerun** *(2026-07, same tree `cb89a77` — a raw solo run, NOT the maintainer-triaged union above, so not comparable to it)*

| Reviewer | Raw findings | Held up so far | False positives | Status |
|---|--:|--:|--:|---|
| Qwen3.7-Max | 30 † | ≥1 — re-found the FmParams save/load bug | 2 (caught on a source check) | ~28 open, untriaged |

† 32 emitted, 2 self-retracted mid-response. Deposited to the fx32 maintainers for triage. What it shows: qwen3.7-max is a *real* reviewer (it found the genuine bug) **and** noisy (a couple of confident false positives) — which is exactly the job the chairman does.

## You need opencode first

This is a front-end. The reviewing happens through the opencode CLI on an opencode-go plan — a pile of cheap models for a flat monthly fee. No opencode, nothing runs, and the command will tell you as much.

- https://opencode.ai/go?ref=RWGQD6Q9RA — referral link. You get five dollars, I get five dollars. Use it if that sits fine with you.
- https://opencode.ai/go — the same thing without the referral, if it doesn't.

## Install — Claude Code

```
/plugin marketplace add photod/pi-reviewer
/plugin install pi@pi-reviewer
```

Restart the session so the command registers, then run `/pi-review med <target>`. It installs its own review engine the first time you use it.

## Install — Codex

```bash
codex plugin marketplace add photod/pi-reviewer
codex plugin add pi@pi-reviewer
```

Start a new Codex thread, invoke `$pi-setup install` once, approve installing the three bundled custom
agent profiles, then start one more new thread so Codex loads them. That second activation step is needed
because plugins can bundle skills but do not currently register custom-agent TOMLs themselves.

During local development from this checkout:

```bash
codex plugin marketplace add ~/gh/pi-reviewer
codex plugin add pi@pi-reviewer
```

The installer backs up conflicting profiles, updates atomically, and only removes bytes it owns.

PI's Codex skills use native subagents only. If the current surface cannot spawn them, PI stops and asks
you to use a fresh interactive Codex app/CLI/IDE thread; it never falls back to spawning `codex exec`.

## Running it — Claude Code

```
/pi-review                     review the current diff, default settings
/pi-review high src/engine     the whole council, on a path
/pi-review low diff opus       cheaper panel, Opus in the chair
```

The three tiers, spelled out:

- **low** — a quick pass with three reviewers; cheap and fast, the one for a routine diff. (MiniMax-M3, DeepSeek-V4-Pro, MiMo-V2.5-Pro.)
- **med** *(default)* — three reviewers with a better spread; the one you'll reach for most days. (GLM-5.2, Qwen3.7-Max, Kimi K2.7-Code.)
- **high** — all six reviewers plus a heavier reconciliation pass by the chairman, for a pre-merge audit or a change that scares you.

## Running it — Codex

The main entry point chooses review versus build from the task:

```text
$pi med review the current diff
$pi high audit src/engine
$pi low fix the parser regression; acceptance: ./run.sh test
```

Direct entry points are available when you want to be explicit:

```text
$pi-review med current diff
$pi-build low add the named regression test and fix src/parser.ts; run npm test
```

An operator can also say: “Use `$pi med` to review this branch. Spawn the PI leaves in parallel, wait
for all of them, then return only the external chairman verdict and coverage.” Usually the shorter form is
enough; the skill itself instructs the main thread to use native PI subagents and never self-author a
missing leaf.

Codex PI automatically routes review language (`review`, `audit`, `inspect`, `find bugs`) to the council,
and change language (`implement`, `fix`, `add`, `refactor`) to the scoped builder. It asks only when the
request genuinely does not say whether files should change.

One deliberate confirmation remains: PI sends the selected code to third-party OpenCode-Go/Kimi model
endpoints. Codex asks for explicit disclosure consent before the first leaf unless your current request
already says that you approve sending that named target to those providers. This is not an approval-mode
replacement; it is the data boundary PI actually crosses.

Why those six and not some other set? Nothing handed me the list — it's the combination I've landed on and trust. Each one is strong on its own, and, more to the point, they're different enough that they don't all trip on the same things. Six great models that think alike would be worth one. These six disagree, usefully. That's why they're the ones.

## Changing the defaults

Nothing to set up to get going. For different defaults for good, drop a `~/.claude/pi.json`:

```json
{ "tier": "med", "chairman": "glm-5.2", "kimiMode": "opencode" }
```

Codex reads the same keys from `~/.codex/pi.json` (plus `buildModel`); Claude reads `~/.claude/pi.json`.
The chairman defaults to GLM-5.2 — cheap to run, frontier-league in ability, and reconciling a stack of
reviews is well within it. Claude can also seat `opus` or `sonnet`; Codex deliberately keeps its chairman
external so the result stays PI rather than turning into a host-model review. Per-run arguments win.

Upgrading from 0.1.x: tier names changed by meaning-preserving position — old `med` is now `low`, old
`high` is now `med`, and old `ultra` is now `high`. Update a saved `"tier": "high"` to `"tier": "med"`
if you want the previous default three-model panel rather than the new full-panel `high`.

PI masks common secrets before whole-repo reviews — see [masking details](#privacy--masking) to preview or configure it.

## Where it doesn't help

It's a cost play, not sorcery. On the bugs any competent reviewer would catch it's a tie, and paying for six opinions to confirm what one already told you is silly. The value is entirely on messy, divergent, real code, and even there the raw output has junk in it — the chairman exists because a stack of cheap reviews needs someone to decide which ones are true. Point it at your working tree mid-project, when a second read still changes what you do next. It's a reviewer, not a rubber stamp for the night before release.

## Bonus: PI also builds (/pi-build)

There's a companion command, `/pi-build`, for when you'd rather have the council write the change than just read it. It delegates a scoped, test-driven change to GLM-5.2 over opencode-go, a different model augments the tests, and a cross-model pass reviews the resulting diff before it comes back. Same opencode-go plan, no extra cost. It's secondary to the review council — the reviewer is the headline — but handy when you already trust the panel and want a small, well-checked change out the door.

One honest limit: these cheap models are strong *reviewers* at any repo size, but as *builders* they're only reliable on tiny-to-small, well-scoped changes — which is exactly why `/pi-build` is scoped that way. Reach for it on a contained edit, not a sprawling feature; for the big stuff, use PI to review what your main model built.

## Why not OpenRouter or opencode-zen?

Neither is wired up today — and here's the honest reason. Both *could* be: they route through the same `opencode` binary (`-m openrouter/<provider/model>`), so adding one is a prefix-and-key change, not a rewrite. But both are **per-token**, and that breaks the one idea PI stands on. opencode-go is flat — you fan out the whole council in parallel and never watch a meter. Go per-token and a parallel council turns into a variable, uncapped bill.

Where they *would* earn a place is the **chairman**: OpenRouter and opencode-zen each put a pile of first-league reconcilers — Opus, GPT-5, Gemini — behind a single key (no Codex, though). Seating one of those in the chair for a review worth a few cents is the real use case. So treat it as **planned, not promised**: if you want either, [open a GitHub issue](../../issues) and say so — enough interest and it goes in, opt-in and gated behind a per-run budget so the flat-fee council stays the default.

## Built and reviewed by

Opus 4.8 did most of the building. GPT-5.6, GPT-5.5, and GLM-5.2 reviewed the code. And PI reviewed itself — a full high-tier pass of the council over its own source.

Not AI. PI.

## If it helped

If PI caught a bug that would've cost you an evening, a ⭐ on the repo helps the next person find it. That's the whole ask.

## Credits

The review lenses are a clean-room adaptation of the "Difference Layer" (§15) from the [Fable-5 methodology by UnpaidAttention](https://github.com/UnpaidAttention/fable5-methodology) — its ideas, re-expressed in our own words, not its code. Reviewing runs on [opencode](https://opencode.ai) and its opencode-go plan.

## Privacy & masking

Diff, feature, and `yolo` reviews send code as-is; whole-repo `list` / `curated` reviews send a best-effort masked copy instead.

- Preview a file or directory: `python3 <plugin>/scripts/pi-mask.py --preview path/to/file_or_dir`
- Toggle masked secret domains/countries in `pi-mask.config.json` (see `scripts/pi-mask.config.example.json`); defaults are deliberately lean, with broader and higher-noise checks off.
- Inspect the gitignored, owner-only `.pi-review/snap-<timestamp>/` copy to see what was sent; PI never masks source in place and auto-prunes snapshots by newest N and age in days, whichever removes more.

**Honest caveat on the masker:** its rules are validated only against **synthetic** test data — keys and IDs we generated with the correct prefixes, lengths, and checksums, never real leaked secrets (which we neither have nor want). So the patterns are correct *by construction*, and the test suite is fully shareable — but we have **no measured real-world catch rate**, and we can't promise it fires on a credential shaped differently than the public format. That's exactly why it's a seatbelt, not a vault, and why you can preview before trusting it.

## Disclaimers

- **One repo, one run.** The numbers here come from a single private codebase reviewed once — a real result, not a benchmark or a promise about your code.
- **Not affiliated.** PI is an independent tool, not affiliated with or endorsed by opencode/SST, Anthropic, OpenAI, Google, or any model vendor. Model and product names belong to their owners.
- **Only basic secret masking.** Whole-repo reviews (`list`/`curated` modes) stage a redacted copy first — a best-effort masker that catches common high-value keys (LLM/cloud/git/S3 tokens) by prefix and shape, and fails closed if it errors. It is **not a guarantee**, and diff, feature, and `yolo`-mode reviews send code **as-is**. Treat it as a seatbelt, not a vault: don't point PI at anything you truly can't share with a third-party model provider.
- **As-is, no warranty.** Use at your own discretion.

## License

MIT — see [LICENSE](LICENSE).
