#!/usr/bin/env python3
"""Install PI's dedicated Codex profile without clobbering operator edits."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import tomllib


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SOURCE = PLUGIN_ROOT / "profiles" / "pi.config.toml"
CODEX_HOME = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
TARGET = CODEX_HOME / "pi.config.toml"
STATE_PATH = CODEX_HOME / ".pi-reviewer-profile-state.json"
SHA256_LENGTH = 64


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_source() -> None:
    if SOURCE.is_symlink() or not SOURCE.is_file():
        raise SystemExit(f"error: invalid bundled PI profile: {SOURCE}")
    with SOURCE.open("rb") as stream:
        config = tomllib.load(stream)
    expected = {
        "approval_policy": "on-request",
        "approvals_reviewer": "user",
        "sandbox_mode": "workspace-write",
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise SystemExit(f"error: PI profile must set {key}={value!r}")
    sandbox = config.get("sandbox_workspace_write")
    if not isinstance(sandbox, dict) or sandbox.get("network_access") is not True:
        raise SystemExit("error: PI profile must enable sandbox_workspace_write.network_access")


def load_state() -> dict | None:
    if STATE_PATH.is_symlink():
        raise SystemExit(f"error: refusing symlinked installer state: {STATE_PATH}")
    try:
        state = json.loads(STATE_PATH.read_text())
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as error:
        raise SystemExit(f"error: invalid installer state {STATE_PATH}: {error}") from error
    if not isinstance(state, dict):
        raise SystemExit(f"error: invalid installer state shape: {STATE_PATH}")
    target = state.get("target")
    installed_hash = state.get("installed_hash")
    ownership = state.get("ownership")
    backup = state.get("backup")
    if not isinstance(target, str) or Path(target).resolve() != TARGET.resolve():
        raise SystemExit(f"error: installer state target escapes PI profile path: {target!r}")
    if (
        not isinstance(installed_hash, str)
        or len(installed_hash) != SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in installed_hash)
    ):
        raise SystemExit("error: invalid installer state hash")
    if ownership not in {"created", "replaced", "preexisting"}:
        raise SystemExit(f"error: invalid installer ownership: {ownership!r}")
    if backup is not None:
        if not isinstance(backup, str):
            raise SystemExit("error: invalid installer backup")
        resolved = Path(backup).resolve()
        if resolved.parent != CODEX_HOME.resolve() or not resolved.name.startswith(
            ".pi-reviewer-profile-backup-"
        ):
            raise SystemExit(f"error: installer backup escapes CODEX_HOME: {backup!r}")
    if ownership == "replaced" and backup is None:
        raise SystemExit("error: replaced profile lacks backup")
    return state


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def write_state(state: dict) -> None:
    if STATE_PATH.is_symlink():
        raise SystemExit(f"error: refusing symlinked installer state: {STATE_PATH}")
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=CODEX_HOME, prefix=f".{STATE_PATH.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
        json.dump(state, stream, indent=2)
        stream.write("\n")
    try:
        os.replace(temporary, STATE_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def backup_profile() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = CODEX_HOME / f".pi-reviewer-profile-backup-{stamp}.toml"
    counter = 1
    while candidate.exists():
        candidate = CODEX_HOME / f".pi-reviewer-profile-backup-{stamp}-{counter}.toml"
        counter += 1
    shutil.copy2(TARGET, candidate)
    print(f"backup: {TARGET} -> {candidate}")
    return candidate


def install() -> None:
    validate_source()
    state = load_state()
    if TARGET.is_symlink() or (TARGET.exists() and not TARGET.is_file()):
        raise SystemExit(f"error: refusing non-regular destination: {TARGET}")
    source_hash = digest(SOURCE)
    target_hash = digest(TARGET) if TARGET.exists() else None
    previous_hash = state.get("installed_hash") if state else None
    if target_hash == source_hash:
        ownership = state.get("ownership", "preexisting") if state else "preexisting"
        backup = state.get("backup") if state else None
        print(f"unchanged: {TARGET}")
    elif state and target_hash == previous_hash:
        ownership = state.get("ownership", "preexisting")
        backup = state.get("backup")
        if ownership == "preexisting":
            backup = str(backup_profile())
            ownership = "replaced"
        atomic_copy(SOURCE, TARGET)
        print(f"updated: {TARGET}")
    elif TARGET.exists():
        backup = str(backup_profile())
        ownership = "replaced"
        atomic_copy(SOURCE, TARGET)
        print(f"installed: {TARGET}")
    else:
        backup = None
        ownership = "created"
        atomic_copy(SOURCE, TARGET)
        print(f"installed: {TARGET}")
    write_state(
        {
            "target": str(TARGET),
            "installed_hash": source_hash,
            "ownership": ownership,
            "backup": backup,
        }
    )
    print("launch PI with: codex -p pi --sandbox workspace-write -C /path/to/repo")


def check() -> None:
    validate_source()
    if not TARGET.is_file() or digest(TARGET) != digest(SOURCE):
        print(f"inactive or different: {TARGET}")
        raise SystemExit(1)
    print(f"active: {TARGET}")


def uninstall() -> None:
    state = load_state()
    if state is None:
        print("no installer state; nothing removed")
        return
    if not TARGET.exists():
        print(f"already absent: {TARGET}")
    elif digest(TARGET) != state["installed_hash"]:
        print(f"preserved modified: {TARGET}")
        return
    elif state["ownership"] == "created":
        TARGET.unlink()
        print(f"removed: {TARGET}")
    elif state["ownership"] == "replaced" and state.get("backup"):
        backup = Path(state["backup"])
        if not backup.is_file():
            print(f"preserved because backup is missing: {TARGET}")
            return
        atomic_copy(backup, TARGET)
        print(f"restored: {TARGET}")
    else:
        print(f"preserved pre-existing: {TARGET}")
    STATE_PATH.unlink(missing_ok=True)


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    actions = {"install": install, "check": check, "uninstall": uninstall}
    if command not in actions:
        raise SystemExit(f"usage: {sys.argv[0]} {{install|check|uninstall}}")
    actions[command]()


if __name__ == "__main__":
    main()
