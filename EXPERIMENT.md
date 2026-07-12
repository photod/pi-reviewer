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
