# The experiment — what PI was actually tested on

_2026-07. The honest provenance behind PI's results._

## What was under review

A music synthesizer in C/C++ — a private, deterministic fixed-point audio engine: voice allocator, ADSR envelopes, wavetable and FM, LUTs, a declarative preset wire-format, and a Python codegen that emits the C loader/saver and a JSON validator. Real code with real edges, not a benchmark or a toy.

## How the code was written

This matters for reading the results: the synth was itself AI-built. Fable 5 drew the plan, Sonnet 5 implemented it, Opus 4.8 rode along as the advisor — design review and course-correction. So every bug PI surfaced is an AI-introduced bug in AI-written code, which is exactly the population a review council exists to catch.

## When PI was run

Mid development cycle. PI was pointed at the working tree partway through, the way you actually reach for a reviewer: I've built a chunk, tell me what's wrong before I keep going.

## What PI was

The cheap council: six opencode-go models — glm-5.2, qwen, minimax, deepseek, mimo, kimi — as single-model leaves, a glm-5.2 chairman reconciling them, each leaf coached with the embedded lenses and reviewer scaffold. Cheap the whole way down.

## The results — triaged by the maintainers, not by PI

Deposited with the project's maintainers and fully triaged: all 61 distinct findings reviewed against current code, in two rounds (`cody-reviewer`, then `kimi-reviewer` for the tail).

- **17 fixed** — with commit hashes, verified against a full suite: 68 C++ suites / 3.5M assertions, 170 Python tests, lint clean.
- **19 confirmed real** — genuine gaps with a noted fix direction, not yet actioned.
- **25 disputed** — reviewer misread, not-a-correctness-bug, ratified design, or safe-for-now.
- **0 untriaged.**

So 36 of 61 findings, 59%, were real: 17 fixed, 19 confirmed. Twenty-five got rejected.

## Reference arms — how frontier and Codex compared

Same prompt, same mid-cycle tree. Raw findings, before triage:

| Reviewer | Raw finds | Notable / owned |
|---|:--:|---|
| **Opus 4.8** | ~7 | the big allocator stuck-note, retrigger-ADSR, the perf loop, report.json bloat — missed the entire codegen serialization-validation cluster |
| **Sonnet 5** | ~6 | retrigger-ADSR (with Opus), the PITCH rate-class bug, path-id off-by-one — missed the stuck-note |
| **Codex gpt-5.6-sol** (high) | 11 | broadest single arm: the save/encode-validation cluster, true-peak Nyquist, stuck-note; uniquely the `Schema.topo` cycle guard |
| **Codex gpt-5.6-terra** (med) | 7 | ties `sol` at half the reasoning effort; uniquely the `sus_level` overflow |
| **Codex gpt-5.5** (high) | 7 | save/load validation + stuck-note; missed true-peak |
| **Cheap council** (6 opencode-go) | most of the 61-bug union | Qwen alone owns an 8-bug allocator-concurrency family no other arm touched; GLM found the codegen `NameError` that aborts codegen outright; MiMo the BS.1770 gate |

The punchline: no single arm — frontier, Codex, or cheap — found more than a fraction of the union, and 36 of 61 bugs were lone-wolf, caught by one reviewer. Divergence lives *between* model families, and the cheap council's edge is breadth: a cheap model was as likely to catch a divergent bug as a frontier one. That's the honest case for PI — a broad, cheap net that needs the chairman to filter, run mid-cycle where a reviewer actually helps.

## The full matrix — review system × issues found

_fx32-libretto, one private C/C++ audio synth, single-repo experiment — see the caveat above. Every
number below is a column-count off the 61-bug, 11-reviewer union matrix maintained with the project
(`docs/pi-review/MATRIX.md` in the fx32-libretto tree), cross-checked against each arm's own raw
finding count and against the cheap-panel's per-model breakdown — they all agree exactly._

| System | Family | Found | Confirmed-real | Lone-wolf |
|---|---|--:|--:|--:|
| Opus 4.8 (solo) | strong single model | 7 | 6 | 1 |
| Sonnet 5 (solo) | strong single model | 6 | 5 | 1 |
| Codex gpt-5.6-sol, high (solo) | Codex family | 11 | 11 | 1 |
| Codex gpt-5.5, high (solo) | Codex family | 8 † | 8 | 0 |
| Codex gpt-5.6-terra, medium (solo) | Codex family | 7 | 6 | 0 |
| Kimi | cheap panel | 17 | 15 | 6 |
| GLM-5.2 | cheap panel | 15 | 9 | 7 |
| MiMo-V2.5-Pro | cheap panel | 13 | 6 | 7 |
| **Qwen3.7-Plus** | cheap panel | 10 | 1 | **8** |
| DeepSeek-V4-Pro | cheap panel | 6 | 3 | 4 |
| MiniMax-M3 | cheap panel | 2 | 1 | 1 |
| GLM-5.2, as chairman (reconciled rerun) | chairman | 39 | — ‡ | — ‡ |
| Opus, as chairman | chairman | — § | — § | — § |

**Found** = that system's total distinct bugs in the union matrix. **Confirmed-real** = of those, how
many the maintainers' two-round triage marked FIXED or CONFIRMED (not DISPUTED). **Lone-wolf** = of
those, how many no other reviewer (of the 11) also caught.

> ⚠️ **The Qwen3.7-Plus row is our error, kept in the record on purpose.** We ran the wrong Qwen —
> `qwen3.7-plus`, which scored 1 real of 10 (mostly disputed). Its "8-bug allocator family" was almost
> all ruled intentional; it is NOT a win. Production uses **`qwen3.7-max`**, a materially stronger model
> whose real numbers we'll only have after a second run. **Do not use `qwen3.7-plus` for review.** The
> row stays here so the mistake — and the reminder — is visible.

† Codex gpt-5.5's own arm file reports 7 findings; the union matrix credits it 8 because one of those
findings names two distinct technical claims in a single sentence and is counted for both — documented
inline as footnote †4 in `MATRIX.md`. Not a discrepancy, a stated credit-splitting rule.

‡ The chairman pass reconciles the panel's raw output into one list — it isn't itself one of the 11
reviewers scored in the union matrix, so "confirmed-real"/"lone-wolf" against that matrix don't apply.
39 is the count of items in its reconciled verdict (`raw-reviews/rerun-glm-chairman/_CHAIRMAN-glm.md`).

§ An Opus-chairman reconciliation is referenced in the fx32-libretto docs' `INDEX.md`
(`arm-B-panel/_CHAIRMAN-opus.md`), but that file does not exist in the delivered `raw-reviews/` tree —
not recoverable, not guessed.

Read the table by row, not just by total. **Kimi and GLM aren't just prolific, they're wide** — 6 and 7
of their finds respectively, nobody else touched. **Codex's family is narrow and tight** — sol, terra,
and g55 barely diverge from each other and own almost no lone-wolf finds; their value is depth on the
signature bugs, not breadth. The case for cheap models is elsewhere: **GLM and MiMo each landed real,
confirmed bugs nobody else caught** (the codegen error that aborts the build; the loudness gate), and
DeepSeek added several more — divergent *real* finds at a fraction of a cent. A council that's wide
enough to reach code paths a single model skips is also wide enough to be right in places nothing else
looks. That is the coverage argument — made by confirmed finds, not raw noise. (The `qwen3.7-plus` row
is the counter-example, not the poster child: 8 lone finds, 1 real — coverage that was almost all wrong,
which is exactly what the chairman is there to throw out. It's also the wrong model; see the warning
above. Production runs `qwen3.7-max`.)
