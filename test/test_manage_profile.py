import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "plugins/pi/scripts/manage_profile.py"


def load_manager():
    spec = importlib.util.spec_from_file_location("manage_profile", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PROFILE = (
    'approval_policy = "on-request"\n'
    'approvals_reviewer = "user"\n'
    'sandbox_mode = "workspace-write"\n'
    '[sandbox_workspace_write]\n'
    'network_access = true\n'
)


class ManageProfileTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.manager = load_manager()
        self.manager.CODEX_HOME = root / "home"
        self.manager.TARGET = self.manager.CODEX_HOME / "pi.config.toml"
        self.manager.STATE_PATH = self.manager.CODEX_HOME / ".pi-reviewer-profile-state.json"
        self.manager.SOURCE = root / "source" / "pi.config.toml"
        self.manager.SOURCE.parent.mkdir()
        self.manager.SOURCE.write_text(PROFILE)

    def tearDown(self):
        self.temporary.cleanup()

    def test_created_profile_is_removed(self):
        self.manager.install()
        self.assertEqual(PROFILE, self.manager.TARGET.read_text())
        self.manager.uninstall()
        self.assertFalse(self.manager.TARGET.exists())

    def test_replaced_profile_is_restored(self):
        self.manager.CODEX_HOME.mkdir()
        original = 'model = "personal"\n'
        self.manager.TARGET.write_text(original)
        self.manager.install()
        self.manager.uninstall()
        self.assertEqual(original, self.manager.TARGET.read_text())

    def test_update_preserves_original_backup(self):
        self.manager.CODEX_HOME.mkdir()
        original = 'model = "personal"\n'
        self.manager.TARGET.write_text(original)
        self.manager.install()
        self.manager.SOURCE.write_text(PROFILE + '# version two\n')
        self.manager.install()
        self.manager.uninstall()
        self.assertEqual(original, self.manager.TARGET.read_text())

    def test_uninstall_preserves_modified_profile(self):
        self.manager.install()
        self.manager.TARGET.write_text(PROFILE + '# local edit\n')
        self.manager.uninstall()
        self.assertTrue(self.manager.TARGET.exists())

    def test_rejects_profile_that_uses_auto_review(self):
        self.manager.SOURCE.write_text(PROFILE.replace('"user"', '"auto_review"'))
        with self.assertRaisesRegex(SystemExit, "approvals_reviewer"):
            self.manager.install()

    def test_rejects_state_target_escape(self):
        outside = Path(self.temporary.name) / "outside.toml"
        outside.write_text("preserve\n")
        self.manager.CODEX_HOME.mkdir()
        self.manager.STATE_PATH.write_text(
            json.dumps(
                {
                    "target": str(outside),
                    "installed_hash": hashlib.sha256(outside.read_bytes()).hexdigest(),
                    "ownership": "created",
                    "backup": None,
                }
            )
        )
        with self.assertRaisesRegex(SystemExit, "target escapes"):
            self.manager.install()
        self.assertTrue(outside.exists())

    def test_rejects_state_backup_escape(self):
        self.manager.CODEX_HOME.mkdir()
        self.manager.TARGET.write_text(PROFILE)
        outside = Path(self.temporary.name) / "outside-backup.toml"
        outside.write_text("preserve\n")
        self.manager.STATE_PATH.write_text(
            json.dumps(
                {
                    "target": str(self.manager.TARGET),
                    "installed_hash": hashlib.sha256(self.manager.TARGET.read_bytes()).hexdigest(),
                    "ownership": "replaced",
                    "backup": str(outside),
                }
            )
        )
        with self.assertRaisesRegex(SystemExit, "backup escapes"):
            self.manager.install()
        self.assertTrue(outside.exists())


if __name__ == "__main__":
    unittest.main()
