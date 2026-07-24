# AGENTS.md — working notes for this repo

Project instructions for coding agents working in this repo. Human-facing usage lives in `README.md`.

## What this repo is

Poor Intelligence (PI) is a multi-model review council and a small-change builder, targeted at Claude
Code (`plugin/`). The external OpenCode-Go/Kimi models are the product; Claude orchestrates them but
must never replace a failed leaf with its own review.

A Codex **edition** (Codex-as-host: running the whole council *inside* `codex exec`) was built and shipped
experimentally but never became reliable — Codex's managed Auto-review policy blocks exporting workspace
data to third-party endpoints even with explicit consent, with no consistent way around it. That edition
was removed from `main` entirely; the abandoned experiment (the old `plugins/pi/` tree) is preserved on the
`codex` branch — do **not** resurrect Codex-as-host here. Distinct from that: the small opt-in `cody/`
plugin uses the Codex **CLI** as an *optional* non-Claude review/worker arm (`cody-reviewer` /
`cody-worker`) — that is intentional and fine; it's a bonus arm, not the host.

## Boundaries

- Preserve Claude-specific mechanics under `plugin/`: Workflow API calls, `agentType`, Claude
  frontmatter, `${CLAUDE_PLUGIN_ROOT}`, and `< /dev/null` are intentional.
- Operator tiers are exactly `low|med|high` (`max`/`ultra` are accepted as input aliases for `high`,
  resolved at parsing only). Provider `--variant` values remain `low|medium|high`;
  do not conflate the two vocabularies.
- Masking is the default at every review scope: whole-repo and named-file reviews use the fail-closed
  staging scripts, diff/branch reviews pipe the diff text through the masker's stdin mode. Only an
  explicit `yolo` sends raw source. Never weaken privacy behavior or silently fall back to raw source.
- Review leaves are relays. Backend unavailable means `status: UNAVAILABLE`, never a host-authored
  substitute wearing another model's label.
- Builder model calls are sequential because they share a working tree. Never fan out write legs.

## Validation

Run `./run.sh check`. It validates Claude frontmatter/manifests, synchronized bundled scripts, and all
test suites.

Scripts are mirrored two ways and must stay identical (the check fails on drift): `scripts/` is the
source of truth and `plugin/scripts/` is the Claude plugin bundle (commands/agents reference it as
`${CLAUDE_PLUGIN_ROOT}/scripts/...`).

Use strict Bash (`set -euo pipefail`), quote variables, and keep committed shell scripts shellcheck-clean.
