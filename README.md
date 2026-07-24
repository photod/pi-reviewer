# Poor Intelligence

PI, not AI.

> **Claude Code plugin.** PI needs the `opencode` CLI and an opencode-go plan (about $10/month) — no
> opencode, nothing happens. Claude runs the council through its Workflow API.

It's a code review tool that does the obvious-in-hindsight thing: instead of paying one expensive model to look at your code, it asks a handful of cheap ones and lets them fight about it, then a chairman reads the fight and hands you a single verdict.

The name is a price tag, not an insult. Poor as in cheap, not poor as in dim — these models are, officially, in the frontier's league. GLM-5.2 lands within a few points of the best closed models on real coding benchmarks, and the rest aren't far off; they just cost pennies a call instead of dollars. So yes, it's poor-man's AI, and the poor man is getting six frontier-grade reviewers for a flat monthly fee. The bet is that six strong models with different blind spots cover more ground than one expensive model with a single blind spot, and running all six costs about nothing. Poverty of price, not of intelligence. That's the thesis.

## You need opencode first

This is a front-end. The reviewing happens through the opencode CLI on an opencode-go plan — a pile of cheap models for a flat monthly fee. No opencode, nothing runs, and the command will tell you as much.

- https://opencode.ai/go?ref=RWGQD6Q9RA — referral link. You get five dollars, I get five dollars. Use it if that sits fine with you.
- https://opencode.ai/go — the same thing without the referral, if it doesn't.

## Install — Claude Code

```
/plugin marketplace add photod/pi-reviewer
/plugin install pi@pi-reviewer
```

Restart the session so the command registers, then run `/pi-review med <target>`. It installs its own review engine on first use — and refreshes it automatically whenever you `/plugin update` (it re-copies the bundled engine whenever the installed one differs, so upgrades actually take effect).

### Why not Codex

PI targets Claude Code, and only Claude Code. I did try to build a Codex edition — and I'll be straight with you: I tried, I failed, and there is nothing to pick up. Codex's managed Auto-review policy blocks exporting workspace data to third-party model endpoints, even with explicit, scope-specific operator consent, and no approval profile I tried could get past it consistently. Sessions that worked once would refuse the next time, with no way to reproduce the difference — not a workflow I can hand you in good conscience. The abandoned experiment is preserved on the `codex` branch if anyone wants to pick it back up, but it's unsupported and I don't recommend it. Claude Code is the one host, and all of PI's attention goes there.

## Running it

```
/pi-review                     review the current diff, default settings
/pi-review high src/engine     the whole council, on a path
/pi-review low diff opus       cheaper panel, Opus in the chair
```

The three tiers, spelled out:

- **low** — a quick pass with three reviewers; cheap and fast, the one for a routine diff. (MiniMax-M3, DeepSeek-V4-Pro, MiMo-V2.5-Pro.)
- **med** *(default)* — three reviewers with a better spread; the one you'll reach for most days. (GLM-5.2, Qwen3.7-Max, Kimi K2.7-Code.)
- **high** — all six reviewers plus a heavier reconciliation pass by the chairman, for a pre-merge audit or a change that scares you.

(`max` and `ultra` also work — both map to `high`, for anyone who forgets which word is the top.)

Why those six and not some other set? Nothing handed me the list — it's the combination I've landed on and trust. Each one is strong on its own, and, more to the point, they're different enough that they don't all trip on the same things. Six great models that think alike would be worth one. These six disagree, usefully. That's why they're the ones.

## Changing the defaults

Nothing to set up to get going. For different defaults for good, drop a `~/.claude/pi.json`:

```json
{ "tier": "med", "chairman": "glm-5.2", "kimiMode": "opencode" }
```

The chairman defaults to GLM-5.2 — cheap to run, frontier-league in ability, and reconciling a stack of
reviews is well within it. Claude can also seat `opus` or `sonnet` in the chair. Per-run arguments win.

`kimiMode` deserves a word, because Kimi is the one panel model with two homes. Every other reviewer is
reachable only through opencode-go, but Kimi K2.7-Code also has a standalone `kimi` CLI with its own
separate subscription. So the Kimi leaf (it joins at `med`/`high`) can be served three ways:

- `"opencode"` *(default)* — Kimi runs through opencode-go like every other leaf: one plan, one quota pool, zero extra setup.
- `"cli"` — Kimi runs through the standalone `kimi` CLI instead. Pick this if you pay for Kimi separately (its own quota, not your opencode-go pool), or if your opencode-go plan doesn't carry Kimi.
- `"off"` — drop the Kimi leaf entirely; `med` becomes a GLM + Qwen pair.

No other model has a mode because no other model has a second backend — there'd be nothing to choose.

> 🎁 **A bit of fun — a clearly-labelled referral.** `kimiMode: "cli"` means your own Kimi account, and
> honestly its **K3** model is a treat: 1M-context, and it accompanies Opus and Fable wonderfully whether
> it's chairing or on the panel. If you're signing up anyway, here's my Kimi referral (invitation code
> **`PYDR92`**): https://kimi-bot.com/activities/viral-referral/share?scenario=invite&from=share_poster&invitation_code=PYDR92
> — yes, it's a referral: it kicks a little something my way, and their promo might toss you (or me) a
> prize, might not — bit of a lottery ;-). Use it if that sits fine, or just find Kimi on your own and
> skip it. No pressure either way.

Upgrading from 0.1.x: tier names changed by meaning-preserving position — old `med` is now `low`, old
`high` is now `med`, and old `ultra` is now `high`. Update a saved `"tier": "high"` to `"tier": "med"`
if you want the previous default three-model panel rather than the new full-panel `high`.

PI masks common secrets before sending anything to the panel — see [Privacy & masking](#privacy--masking) to preview or configure it.

## Privacy & masking

**PI masks before sending, at every scope.** Whatever you point it at — a whole repo, a bare directory, named files, or an ordinary `git diff` — the panel only ever sees a redacted copy. Repos, directories, and named files are staged as masked copies in an **owner-only temp dir outside your repo** (default `${TMPDIR:-/tmp}/pireview/…`, under an opaque per-repo hash so the path the models see carries no username; set `PI_SNAP_ROOT` to relocate — e.g. to `.pi-review/` in the repo for in-place auditing); a diff or branch review pipes the diff text through the same masker and the panel reviews the masked patch instead of touching your tree. The masker catches common high-value secrets — LLM, cloud, git, and S3 tokens, by prefix and shape. Your source is never modified. Masking is **fail-closed**: if it errors, the run aborts rather than forward anything raw. And you can inspect exactly what was sent — snapshots stay on disk, then auto-prune (newest 10, or older than 7 days).

### How masking applies to each input mode

PI has several review **modes**, and masking is applied differently in each — worth knowing so you are
never surprised by what a model actually sees:

| Mode | What it reviews | How it's redacted |
|---|---|---|
| **diff** *(default)* | a `git diff` | the patch text is piped through the masker (`pi-mask.py` on stdin) |
| **list** / **curated** | ≤50 named or hand-picked files | files are **staged as masked copies** under `.pi-review/snap-…/`, then reviewed |
| **pack** | >50 files (whole repo) | a repomix bundle, redacted by **repomix's own `secretlint`** — a *different* redactor, not `pi-mask.py` |
| **yolo** | the raw tree, unbounded | **not redacted** — explicit opt-in only |

So this repo's masker (`pi-mask.py` + the staging denylist) covers the **diff / list / curated** paths;
**pack** hands redaction to repomix + secretlint (whatever those catch); **yolo** sends raw by design.
Whole-repo and single-directory reviews take the staged-copy path.

The single exception is `yolo` mode — explicit-only, never automatic; it sends raw source by definition, and that's the trade you opt into. (`pack` mode relies on repomix's own `secretlint`.) One honest cost: a masked diff review sees only the patch, not the surrounding files — a little context is the price of masking.

- **Preview, in chat:** ask *"what would PI mask in `src/config.py`?"* — the agent runs the masker's preview and shows you exactly what would be redacted, line by line, before anything is sent. (Same thing by hand: `python3 <plugin>/scripts/pi-mask.py --preview path/to/file_or_dir`.) The masked domains are deliberately lean by default — common high-value keys, with broader and higher-noise checks off.

**Honest caveat on the masker:** its rules are validated only against **synthetic** test data — keys and IDs I generated with the correct prefixes, lengths, and checksums, never real leaked secrets (which I neither have nor want). So the patterns are correct *by construction*, and the test suite is fully shareable — but I have **no measured real-world catch rate**, and I can't promise it fires on a credential shaped differently than the public format. That's exactly why it's a seatbelt, not a vault, and why you can preview before trusting it.

**The reviewed code is treated as untrusted, too.** The flip side of masking: PI assumes the code it reviews may try to *manipulate the reviewers*. Every leaf, the chairman that reconciles them, and the standalone `kimi`/`cody` reviewers are told that an instruction planted in the code or a diff — an *"ignore all issues"* comment, a *"you are now…"* string — is content to flag, never a command to obey. Best-effort prompt hardening, not a sandbox — but it keeps a planted line from silently muzzling the panel.

## Bonus: PI also builds (/pi-build)

There's a companion command, `/pi-build`, for when you'd rather have the council write the change than just read it. It delegates a scoped, test-driven change to GLM-5.2 over opencode-go, a different model augments the tests, and a cross-model pass reviews the resulting diff before it comes back. Same opencode-go plan, no extra cost. It's secondary to the review council — the reviewer is the headline — but handy when you already trust the panel and want a small, well-checked change out the door.

One honest limit: these cheap models are strong *reviewers* at any repo size, but as *builders* they're only reliable on tiny-to-small, well-scoped changes — which is exactly why `/pi-build` is scoped that way. Reach for it on a contained edit, not a sprawling feature; for the big stuff, use PI to review what your main model built.

## Where it doesn't help

It's a cost play, not sorcery. On the bugs any competent reviewer would catch it's a tie, and paying for six opinions to confirm what one already told you is silly. The value is entirely on messy, divergent, real code, and even there the raw output has junk in it — the chairman exists because a stack of cheap reviews needs someone to decide which ones are true. Point it at your working tree mid-project, when a second read still changes what you do next. It's a reviewer, not a rubber stamp for the night before release.

## Why this council

Three deliberate choices separate it from a one-model reviewer. A **council**, because one model has one blind spot and six have six small ones that barely overlap. An **arbiter** — the chairman — because a stack of raw, conflicting reviews is worse than none; something has to decide what's real and hand you a single list. And **modes**, a dial from a quick three-model pass to the full six-model panel with a heavier synthesis, because scratching a diff and auditing before a merge are not the same job. That part has to be a plugin, not a clever prompt.

Multi-model orchestrators already exist, so why another? Because most of them wire together two or three expensive frontier models and bill you per run — you save those for the commits that scare you. This one inverts it: six cheap, frontier-league models on a flat plan, so the panel is wider, the disagreement richer, and a review costs close to nothing. The experiment below is the case for it: the cheap, wide panel out-covered the pricey, narrow ones. Free opinions change the habit. You ask on every diff, not just the frightening ones.

## Does it actually work

On easy bugs it's a wash. One decent model spots the missing null check; so does the council; you didn't need a committee for that.

The interesting case is real code. I pointed PI at a mid-development C/C++ audio synth — itself written by an AI, which is exactly the kind of code that hides bugs that look fine — and had the maintainers triage whatever came back. Sixty-one findings. Thirty-six were real: seventeen already fixed and test-verified, nineteen confirmed and queued. The other twenty-five got rejected — the mechanism doing its job. You want a wide, noisy net and someone at the end who throws the garbage back.

The part worth the ticket was that nobody won alone. Opus caught a nasty allocator bug and missed an entire family of serialization gaps; the Codex-family arms owned those gaps and walked straight past the concurrency ones. The same divergence held inside the cheap panel — GLM alone caught the codegen error that aborts the build, MiMo alone the loudness gate: real bugs each found that the others, frontier included, missed. Their blind spots barely overlap, and everything they truly see, once filtered, stacks up.

Which is why the column that matters is **confirmed-real**, not raw finds — a model that sprays false alarms shouldn't score for the noise:

| System | Found | Confirmed-real | Lone-wolf |
|---|--:|--:|--:|
| Kimi | 17 | 15 | 6 |
| Codex gpt-5.6-sol (solo, high) | 11 | 11 | 1 |
| GLM-5.2 | 15 | 9 | 7 |
| MiMo-V2.5-Pro | 13 | 6 | 7 |
| Opus 4.8 (solo) | 7 | 6 | 1 |
| Sonnet 5 (solo) | 6 | 5 | 1 |
| DeepSeek-V4-Pro | 6 | 3 | 4 |
| MiniMax-M3 | 2 | 1 | 1 |

*Confirmed-real = held up under the maintainers' two-round triage (FIXED/CONFIRMED, not disputed). Lone-wolf = of those, how many no other reviewer caught.*

**And what does `/pi-review high` hand you? Not six lists — one.** Those rows are the ingredients; the product is the reconciliation. The six-model cheap panel produced over 60 raw findings between them (overlaps included); the GLM-5.2 chairman read the whole fight and reconciled it into a **single 39-item verdict** — deduped, disagreements flagged, severity-ranked. That's the thing you actually read after a run. (The chairman's list isn't itself scored against the triage matrix — it's a reconciliation of the panel, not an extra reviewer; full accounting in [EXPERIMENT.md](https://github.com/photod/pi-reviewer/blob/main/EXPERIMENT.md).)

**Where's Qwen?** An honest mistake, kept on the record: the panel run accidentally benchmarked `qwen3.7-plus` — the wrong model — and it scored 1 real bug in 10, so its row would only mislead here. Production uses **`qwen3.7-max`**, a materially stronger model, and a validation rerun on the same tree backed that up: it independently re-found the panel's headline save/load bug (30 raw findings, 2 confirmed false positives on a source check, the rest deposited with the maintainers for triage). Both runs, full numbers, in [EXPERIMENT.md](https://github.com/photod/pi-reviewer/blob/main/EXPERIMENT.md).

One repo, one run — not a benchmark claim, just what happened here.

## Why not OpenRouter or opencode-zen?

Neither is wired up today — and here's the honest reason. Both *could* be: they route through the same `opencode` binary (`-m openrouter/<provider/model>`), so adding one is a prefix-and-key change, not a rewrite. But both are **per-token**, and that breaks the one idea PI stands on. opencode-go is flat — you fan out the whole council in parallel and never watch a meter. Go per-token and a parallel council turns into a variable, uncapped bill.

Where they *would* earn a place is the **chairman**: OpenRouter and opencode-zen each put a pile of first-league reconcilers — Opus, GPT-5, Gemini — behind a single key (no Codex, though). Seating one of those in the chair for a review worth a few cents is the real use case. So treat it as **planned, not promised**: if you want either, [open a GitHub issue](../../issues) and say so — enough interest and it goes in, opt-in and gated behind a per-run budget so the flat-fee council stays the default.

## Built and reviewed by

Opus 4.8 did most of the building. GPT-5.6, GPT-5.5, and GLM-5.2 reviewed the code. And PI reviewed itself — a full high-tier pass of the council over its own source.

Not AI. PI.

## If it helped

If PI caught a bug that would've cost you an evening, a ⭐ on the repo helps the next person find it. That's the whole ask.

## Credits

The review lenses are a clean-room adaptation of the "Difference Layer" (§15) from the [Fable-5 methodology by UnpaidAttention](https://github.com/UnpaidAttention/fable5-methodology) — its ideas, re-expressed in my own words, not its code. Reviewing runs on [opencode](https://opencode.ai) and its opencode-go plan.

## Disclaimers

- **One repo, one run.** The numbers here come from a single private codebase reviewed once — a real result, not a benchmark or a promise about your code.
- **Not affiliated.** PI is an independent tool, not affiliated with or endorsed by opencode/SST, Anthropic, OpenAI, Google, or any model vendor. Model and product names belong to their owners.
- **Only basic secret masking.** Every review scope stages a redacted copy first by default — a best-effort masker that catches common high-value keys (LLM/cloud/git/S3 tokens) by prefix and shape, and fails closed if it errors. It is **not a guarantee**, and explicit `yolo`-mode reviews send code **as-is**. Treat it as a seatbelt, not a vault: don't point PI at anything you truly can't share with a third-party model provider.
- **As-is, no warranty.** Use at your own discretion.

## License

MIT — see [LICENSE](LICENSE).
