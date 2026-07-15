# AGENTS.md — Codex working notes for this repo

Project instructions for OpenAI Codex. Human-facing usage lives in `README.md`.

## What this repo is

Poor Intelligence (PI) is a multi-model review council and a small-change builder. It is distributed
for both Claude Code (`plugin/`) and Codex (`plugins/pi/`). The external OpenCode-Go/Kimi models are
the product; Claude or Codex orchestrates them but must never replace a failed leaf with its own review.

## Boundaries

- Preserve Claude-specific mechanics under `plugin/`: Workflow API calls, `agentType`, Claude
  frontmatter, `${CLAUDE_PLUGIN_ROOT}`, and `< /dev/null` are intentional.
- Codex-native work lives under `plugins/pi/` and `.agents/plugins/marketplace.json`.
- Operator tiers are exactly `low|med|high` on both hosts. Provider `--variant` values remain
  `low|medium|high`; do not conflate the two vocabularies.
- Whole-repo `list` and `curated` reviews must use the fail-closed masking/staging scripts. Never
  weaken privacy behavior or silently fall back to raw source.
- Review leaves are relays. Backend unavailable means `status: UNAVAILABLE`, never a host-authored
  substitute wearing another model's label.
- Builder model calls are sequential because they share a working tree. Never fan out write legs.

## Validation

Run `./run.sh check`. It validates Claude frontmatter/manifests, Codex manifests/skills/agent TOMLs,
the activation manager, synchronized bundled scripts, and all test suites.

Use strict Bash (`set -euo pipefail`), quote variables, and keep committed shell scripts shellcheck-clean.
Every TOML must parse with Python 3.11+ `tomllib`.
