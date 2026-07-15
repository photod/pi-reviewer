#!/usr/bin/env python3
"""Install and remove PI's native Codex agents without clobbering edits."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
import tomllib


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = PLUGIN_ROOT / "agents"
CODEX_HOME = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
DEST_DIR = CODEX_HOME / "agents"
STATE_PATH = CODEX_HOME / ".pi-reviewer-agents-state.json"
AGENT_NAME = re.compile(r"[a-z0-9_]+")
STATE_NAME = re.compile(r"[a-z0-9_-]+\.toml")
SHA256 = re.compile(r"[0-9a-f]{64}")
MODELS = {"gpt-5.6-luna"}
EFFORTS = {"low", "medium", "high", "xhigh"}
SANDBOXES = {"read-only", "workspace-write", "danger-full-access"}
EXPECTED_AGENTS = {
    "pi_oppy_reviewer": ("gpt-5.6-luna", "medium", "read-only"),
    "pi_kimi_reviewer": ("gpt-5.6-luna", "medium", "read-only"),
    "pi_glm_worker": ("gpt-5.6-luna", "high", "workspace-write"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources() -> list[Path]:
    files = sorted(SOURCE_DIR.glob("*.toml"))
    if not files:
        raise SystemExit(f"error: no bundled agents under {SOURCE_DIR}")
    names = set()
    actual = {}
    for path in files:
        with path.open("rb") as stream:
            config = tomllib.load(stream)
        name = config.get("name")
        if not isinstance(name, str) or not AGENT_NAME.fullmatch(name):
            raise SystemExit(f"error: invalid native agent name in {path}: {name!r}")
        if path.stem != name:
            raise SystemExit(f"error: agent filename/name mismatch: {path.stem!r} != {name!r}")
        if name in names:
            raise SystemExit(f"error: duplicate native agent name: {name}")
        required = {
            "description": str,
            "developer_instructions": str,
            "model": str,
            "model_reasoning_effort": str,
            "sandbox_mode": str,
        }
        for key, expected in required.items():
            value = config.get(key)
            if not isinstance(value, expected) or not value.strip():
                raise SystemExit(f"error: invalid or missing {key!r} in {path}")
        if config["model"] not in MODELS:
            raise SystemExit(f"error: unsupported model in {path}: {config['model']!r}")
        if config["model_reasoning_effort"] not in EFFORTS:
            raise SystemExit(
                f"error: unsupported reasoning effort in {path}: "
                f"{config['model_reasoning_effort']!r}"
            )
        if config["sandbox_mode"] not in SANDBOXES:
            raise SystemExit(f"error: unsupported sandbox mode in {path}: {config['sandbox_mode']!r}")
        names.add(name)
        actual[name] = (
            config["model"],
            config["model_reasoning_effort"],
            config["sandbox_mode"],
        )
    if actual != EXPECTED_AGENTS:
        missing = sorted(EXPECTED_AGENTS.keys() - actual.keys())
        extra = sorted(actual.keys() - EXPECTED_AGENTS.keys())
        wrong = sorted(
            name for name in actual.keys() & EXPECTED_AGENTS.keys() if actual[name] != EXPECTED_AGENTS[name]
        )
        raise SystemExit(
            f"error: bundled agent roster mismatch; missing={missing}, extra={extra}, wrong={wrong}"
        )
    return files


def load_state() -> dict:
    if STATE_PATH.is_symlink():
        raise SystemExit(f"error: refusing symlinked installer state: {STATE_PATH}")
    try:
        value = json.loads(STATE_PATH.read_text())
    except FileNotFoundError:
        return {"files": {}}
    except json.JSONDecodeError as error:
        raise SystemExit(f"error: invalid installer state {STATE_PATH}: {error}") from error
    files = value.get("files") if isinstance(value, dict) else None
    if not isinstance(files, dict):
        raise SystemExit(f"error: invalid installer state shape: {STATE_PATH}")
    destination = DEST_DIR.resolve()
    for name, item in files.items():
        if not isinstance(name, str) or not STATE_NAME.fullmatch(name) or not isinstance(item, dict):
            raise SystemExit(f"error: invalid installer state entry: {name!r}")
        target = item.get("target")
        installed_hash = item.get("installed_hash")
        ownership = item.get("ownership")
        backup_path = item.get("backup")
        expected_target = (DEST_DIR / name).resolve()
        if not isinstance(target, str) or Path(target).resolve() != expected_target:
            raise SystemExit(f"error: installer state target escapes agent directory: {target!r}")
        if expected_target.parent != destination:
            raise SystemExit(f"error: invalid installer state target: {target!r}")
        if not isinstance(installed_hash, str) or not SHA256.fullmatch(installed_hash):
            raise SystemExit(f"error: invalid installer state hash for {name}")
        if ownership not in {"created", "replaced", "preexisting"}:
            raise SystemExit(f"error: invalid installer ownership for {name}: {ownership!r}")
        if backup_path is not None:
            if not isinstance(backup_path, str):
                raise SystemExit(f"error: invalid installer backup for {name}")
            resolved_backup = Path(backup_path).resolve()
            if (
                resolved_backup.parent.parent != destination
                or not resolved_backup.parent.name.startswith(".pi-reviewer-backup-")
            ):
                raise SystemExit(f"error: installer state backup escapes agent directory: {backup_path!r}")
        if ownership == "replaced" and backup_path is None:
            raise SystemExit(f"error: replaced installer entry lacks backup: {name}")
    return value


def backup(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S-")
    root = Path(tempfile.mkdtemp(dir=DEST_DIR, prefix=f".pi-reviewer-backup-{stamp}"))
    target = root / path.name
    counter = 1
    while target.exists():
        target = root / f"{path.stem}-{counter}{path.suffix}"
        counter += 1
    shutil.copy2(path, target)
    print(f"backup: {path} -> {target}")
    return target


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def write_state(files: dict[str, dict]) -> None:
    if STATE_PATH.is_symlink():
        raise SystemExit(f"error: refusing symlinked installer state: {STATE_PATH}")
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    data = json.dumps({"files": files}, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=CODEX_HOME, prefix=f".{STATE_PATH.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, STATE_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def remove_owned(item: dict, *, stale: bool = False) -> bool:
    target = Path(item["target"])
    if not target.exists():
        print(f"already absent: {target}")
        return True
    if digest(target) != item["installed_hash"]:
        print(f"preserved modified: {target}")
        return False
    ownership = item.get("ownership")
    if ownership == "created":
        target.unlink()
        print(f"removed{' stale' if stale else ''}: {target}")
        return True
    elif ownership == "replaced" and item.get("backup"):
        backup_path = Path(item["backup"])
        if backup_path.is_file():
            atomic_copy(backup_path, target)
            print(f"restored{' stale' if stale else ''}: {target}")
            return True
        print(f"preserved because backup is missing: {target}")
        return False
    else:
        print(f"preserved pre-existing: {target}")
        return True


def install() -> None:
    files = sources()
    old = load_state().get("files", {})
    current: dict[str, dict] = {}
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    for source in files:
        target = DEST_DIR / source.name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise SystemExit(f"error: refusing non-regular destination {target}")
        source_hash = digest(source)
        previous = old.get(source.name)
        target_hash = digest(target) if target.exists() else None
        previous_hash = previous.get("installed_hash") if previous else None
        if target_hash == source_hash:
            ownership = previous.get("ownership", "preexisting") if previous else "preexisting"
            backup_path = previous.get("backup") if previous else None
            print(f"unchanged: {target}")
        elif previous and target_hash == previous_hash:
            ownership = previous.get("ownership", "preexisting")
            backup_path = previous.get("backup")
            if ownership == "preexisting":
                backup_path = str(backup(target))
                ownership = "replaced"
            atomic_copy(source, target)
            print(f"updated: {target}")
        elif target.exists():
            backup_path = str(backup(target))
            ownership = "replaced"
            atomic_copy(source, target)
            print(f"installed: {target}")
        else:
            backup_path = None
            ownership = "created"
            atomic_copy(source, target)
            print(f"installed: {target}")
        current[source.name] = {
            "target": str(target),
            "installed_hash": source_hash,
            "ownership": ownership,
            "backup": backup_path,
        }
    for name, item in old.items():
        if name not in current:
            if not remove_owned(item, stale=True):
                current[name] = item
    write_state(current)
    print("start a new Codex thread to load the custom agents")


def check() -> None:
    ok = True
    for source in sources():
        target = DEST_DIR / source.name
        if not target.is_file() or digest(target) != digest(source):
            print(f"inactive or different: {target}")
            ok = False
        else:
            print(f"active: {target}")
    if not ok:
        raise SystemExit(1)


def uninstall() -> None:
    state = load_state()
    if not state.get("files"):
        print("no installer state; nothing removed")
        return
    for item in state["files"].values():
        remove_owned(item)
    STATE_PATH.unlink(missing_ok=True)


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    actions = {"install": install, "check": check, "uninstall": uninstall}
    if command not in actions:
        raise SystemExit(f"usage: {sys.argv[0]} {{install|check|uninstall}}")
    actions[command]()


if __name__ == "__main__":
    main()
