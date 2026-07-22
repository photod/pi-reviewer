# AGENTS.md — working notes for this repo

Project instructions for coding agents working in this repo. Human-facing usage lives in `README.md`.

## What this repo is

Poor Intelligence (PI) is a multi-model review council and a small-change builder, targeted at Claude
Code (`plugin/`). The external OpenCode-Go/Kimi models are the product; Claude orchestrates them but
must never replace a failed leaf with its own review.

A Codex edition (`plugins/pi/`) was built and shipped experimentally but never became reliable — Codex's
managed Auto-review policy blocks exporting workspace data to third-party model endpoints even with
explicit consent, and there was no consistent way around it. It is no longer presented as an installable
plugin (no `.codex-plugin` manifest, no marketplace entry); its scripts/skills/tests remain in the tree
only because removing them isn't free and they're harmless. The full working state before it was dropped
is preserved on the `codex` branch. Do not build new Codex-facing features on `plugins/pi/`.

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

Run `./run.sh check`. It validates Claude frontmatter/manifests, the dormant Codex skills/agent TOMLs
and their activation-manager scripts, synchronized bundled scripts, and all test suites.

Scripts are mirrored three ways and must stay identical (the check fails on drift): `scripts/` is the
source of truth, `plugin/scripts/` is the Claude plugin bundle (commands/agents reference it as
`${CLAUDE_PLUGIN_ROOT}/scripts/...`), and `plugins/pi/scripts/` is the dormant Codex bundle. Likewise
`plugin/agents/*.md` and `plugin/workflows/pi-council.js` are mirrored into `plugins/pi/references/`.

Use strict Bash (`set -euo pipefail`), quote variables, and keep committed shell scripts shellcheck-clean.
Every TOML must parse with Python 3.11+ `tomllib`.
