import importlib.util
from pathlib import Path
import hashlib
import json
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "plugins/pi/scripts/manage_agents.py"


def load_manager():
    spec = importlib.util.spec_from_file_location("manage_agents", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ManageAgentsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.source = root / "source"
        self.home = root / "home"
        self.source.mkdir()
        self.manager = load_manager()
        self.manager.SOURCE_DIR = self.source
        self.manager.CODEX_HOME = self.home
        self.manager.DEST_DIR = self.home / "agents"
        self.manager.STATE_PATH = self.home / ".pi-reviewer-agents-state.json"
        self.manager.EXPECTED_AGENTS = {
            "worker": ("gpt-5.6-luna", "medium", "workspace-write")
        }

    def tearDown(self):
        self.temporary.cleanup()

    def write_agent(self, description):
        path = self.source / "worker.toml"
        path.write_text(
            'name = "worker"\n'
            f'description = "{description}"\n'
            'model = "gpt-5.6-luna"\n'
            'model_reasoning_effort = "medium"\n'
            'sandbox_mode = "workspace-write"\n'
            'developer_instructions = "work"\n'
        )
        return path

    def test_created_agent_is_removed_after_managed_update(self):
        self.write_agent("version one")
        self.manager.install()
        target = self.manager.DEST_DIR / "worker.toml"

        self.write_agent("version two")
        self.manager.install()
        self.assertIn("version two", target.read_text())

        self.manager.uninstall()
        self.assertFalse(target.exists())

    def test_replaced_agent_restores_original_after_managed_update(self):
        self.manager.DEST_DIR.mkdir(parents=True)
        target = self.manager.DEST_DIR / "worker.toml"
        original = 'name = "personal-worker"\n'
        target.write_text(original)

        self.write_agent("version one")
        self.manager.install()
        self.write_agent("version two")
        self.manager.install()
        self.manager.uninstall()

        self.assertEqual(original, target.read_text())

    def test_uninstall_preserves_locally_modified_agent(self):
        self.write_agent("managed")
        self.manager.install()
        target = self.manager.DEST_DIR / "worker.toml"
        target.write_text(target.read_text() + "# local edit\n")

        self.manager.uninstall()

        self.assertTrue(target.exists())
        self.assertIn("local edit", target.read_text())

    def test_identical_preexisting_agent_is_restored_after_upgrade(self):
        source = self.write_agent("version one")
        self.manager.DEST_DIR.mkdir(parents=True)
        target = self.manager.DEST_DIR / "worker.toml"
        target.write_bytes(source.read_bytes())
        original = target.read_text()

        self.manager.install()
        self.write_agent("version two")
        self.manager.install()
        self.manager.uninstall()

        self.assertEqual(original, target.read_text())

    def test_rejects_agent_name_that_native_spawn_cannot_address(self):
        path = self.source / "bad-agent.toml"
        path.write_text(
            'name = "bad-agent"\n'
            'description = "invalid native identifier"\n'
            'model = "gpt-5.6-luna"\n'
            'model_reasoning_effort = "medium"\n'
            'sandbox_mode = "workspace-write"\n'
            'developer_instructions = "work"\n'
        )

        with self.assertRaisesRegex(SystemExit, "invalid native agent name"):
            self.manager.install()

    def test_rejects_incomplete_agent_configuration(self):
        path = self.source / "worker.toml"
        path.write_text(
            'name = "worker"\n'
            'description = "missing pinned execution settings"\n'
            'developer_instructions = "work"\n'
        )

        with self.assertRaisesRegex(SystemExit, "model"):
            self.manager.install()

    def test_rejects_wrong_pinned_route(self):
        path = self.write_agent("wrong model")
        path.write_text(path.read_text().replace("gpt-5.6-luna", "gpt-5.6-terra"))

        with self.assertRaisesRegex(SystemExit, "unsupported model"):
            self.manager.install()

    def test_rejects_state_target_outside_agent_directory(self):
        self.write_agent("managed")
        outside = Path(self.temporary.name) / "outside.toml"
        outside.write_text("do not remove\n")
        self.home.mkdir(parents=True)
        self.manager.STATE_PATH.write_text(
            json.dumps(
                {
                    "files": {
                        "worker.toml": {
                            "target": str(outside),
                            "installed_hash": hashlib.sha256(outside.read_bytes()).hexdigest(),
                            "ownership": "created",
                            "backup": None,
                        }
                    }
                }
            )
        )

        with self.assertRaisesRegex(SystemExit, "target escapes"):
            self.manager.install()
        self.assertTrue(outside.exists())

    def test_rejects_state_backup_outside_agent_directory(self):
        self.write_agent("managed")
        self.manager.DEST_DIR.mkdir(parents=True)
        target = self.manager.DEST_DIR / "worker.toml"
        target.write_text("installed bytes\n")
        target_before = target.read_bytes()
        outside_backup = Path(self.temporary.name) / "outside-backup.toml"
        outside_backup.write_text("personal bytes\n")
        backup_before = outside_backup.read_bytes()
        self.home.mkdir(parents=True, exist_ok=True)
        self.manager.STATE_PATH.write_text(
            json.dumps(
                {
                    "files": {
                        "worker.toml": {
                            "target": str(target),
                            "installed_hash": hashlib.sha256(target_before).hexdigest(),
                            "ownership": "replaced",
                            "backup": str(outside_backup),
                        }
                    }
                }
            )
        )

        with self.assertRaisesRegex(SystemExit, "backup escapes"):
            self.manager.install()
        self.assertEqual(target_before, target.read_bytes())
        self.assertEqual(backup_before, outside_backup.read_bytes())


if __name__ == "__main__":
    unittest.main()
