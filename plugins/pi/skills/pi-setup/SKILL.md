---
name: pi-setup
description: Install, check, update, or safely uninstall PI's native agents and dedicated user-reviewed network profile. Use for first activation, missing roles, or Auto-review tenant-policy blocks.
---

# PI Setup

Codex plugins do not currently register custom-agent TOMLs or named CLI profiles directly. PI needs:

- the bundled agent TOMLs under `${CODEX_HOME:-$HOME/.codex}/agents`;
- `${CODEX_HOME:-$HOME/.codex}/pi.config.toml`, a dedicated profile that changes approvals from
  Auto-review to the human operator and enables network inside `workspace-write`.

- Default, `install`, or `update`: ask approval, then run both
  `python3 ../../scripts/manage_agents.py install` and
  `python3 ../../scripts/manage_profile.py install` from this skill directory.
- `check`: run both managers with `check`.
- `uninstall`: only after the operator explicitly requests removal, run
  both managers with `uninstall`.

Both managers validate exact inputs, write atomically, back up conflicts, record ownership, restore
replaced files, remove only unchanged managed bytes, and preserve local edits.

Explain that the dedicated profile selects local user-reviewed, network-enabled workspace behavior; it
does not override Auto-review or any managed tenant rule. PI cannot change a private-workspace-export
denial from inside a running task. Where the host policy permits this workflow, the operator starts a
PI-capable CLI session explicitly:

`codex -p pi --sandbox workspace-write -C /absolute/path/to/repo`

This is narrower than `--yolo`: filesystem writes remain workspace-scoped, while external commands get
network and any remaining escalation goes to the human. If the profile session still returns a tenant-policy
denial, report `POLICY_BLOCKED`: only the organization can authorize that egress, and PI must not retry,
route around it, or recommend danger-full-access. Do not edit global `approvals_reviewer` or weaken
the Auto-review policy.

After install/update, tell the operator to start a new Codex thread with the command above. Never claim
newly installed agents/profile are active in the thread that performed installation.
