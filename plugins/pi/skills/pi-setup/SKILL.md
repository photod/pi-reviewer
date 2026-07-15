---
name: pi-setup
description: Install, check, update, or safely uninstall PI's native Codex custom-agent profiles. Use for first activation or missing PI agents.
---

# PI Setup

Codex plugins do not currently register custom-agent TOMLs directly. The bundled profiles must be
copied to `${CODEX_HOME:-$HOME/.codex}/agents`.

- Default, `install`, or `update`: ask approval, then run
  `python3 ../../scripts/manage_agents.py install` from this skill directory.
- `check`: run `python3 ../../scripts/manage_agents.py check`.
- `uninstall`: only after the operator explicitly requests removal, run
  `python3 ../../scripts/manage_agents.py uninstall`.

The manager validates the exact roster, writes atomically, backs up conflicts, records ownership,
restores replaced files, removes only unchanged managed bytes, and preserves local edits.

After install/update, tell the operator to start a new Codex thread. Never claim newly installed agent
profiles are available to the thread that performed installation.
