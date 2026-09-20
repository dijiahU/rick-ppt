"""Post-install preflight boundaries and real default-python hook startup."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import venv


HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "configure-installed-hooks.py"
PLUGIN = HERE.parent / "pptx-agent"
spec = importlib.util.spec_from_file_location("installed_hooks_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class InstalledHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="test-installed-hooks-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.plugin = self.root / "installed plugin with spaces"
        self.plugin.mkdir()
        shutil.copytree(PLUGIN / "hooks", self.plugin / "hooks", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(PLUGIN / "pyproject.toml", self.plugin / "pyproject.toml")
        (self.plugin / "skills").symlink_to(PLUGIN / "skills", target_is_directory=True)
        self.python = Path(sys.executable)
        self.prefix = Path(sys.prefix).resolve()
        self.assertNotEqual(sys.prefix, sys.base_prefix, "Run these tests using the provisioned plugin venv")

    def cli(self, *arguments, env=None):
        process = subprocess.run([sys.executable, "-B", str(SCRIPT), "--plugin", str(self.plugin),
                                  "--python", str(self.python), *arguments],
                                 text=True, capture_output=True, timeout=30,
                                 env=env, cwd=self.root)
        return process, json.loads(process.stdout)

    def own_files(self):
        return {str(path.relative_to(self.plugin)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [self.plugin / "pyproject.toml", *sorted((self.plugin / "hooks").glob("*"))] if path.is_file()}

    def test_missing_check_is_read_only_and_reports_all_import_checks(self):
        before = self.own_files()
        process, report = self.cli("--check")
        self.assertEqual(process.returncode, 1)
        self.assertEqual(report["environmentState"], "missing")
        self.assertEqual(report["stage"], "environment")
        self.assertEqual(len(report["runtime"]["checks"]), 6)
        self.assertTrue(all(item["ok"] for item in report["runtime"]["checks"]))
        self.assertFalse(os.path.lexists(self.plugin / ".venv"))
        self.assertEqual(before, self.own_files())
        self.assertFalse(list((self.plugin / "hooks").glob("__pycache__")))

    def test_configure_and_check_real_hooks_are_idempotent_and_ignore_overrides(self):
        before = self.own_files()
        # An inherited override must not accidentally make a broken cache pass.
        env = dict(os.environ, PPTX_AGENT_PYTHON="/does/not/exist/python",
                   PPTX_AGENT_WORKSPACE=str(self.root / "not-a-workspace"),
                   PPTX_AGENT_REEXEC_TARGET="stale", PYTHONPATH="/does/not/exist/modules",
                   PLUGIN_DATA=str(self.root / "must-not-be-created"))
        process, report = self.cli(env=env)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(report["environmentAdded"])
        self.assertEqual((self.plugin / ".venv").resolve(), self.prefix)
        self.assertEqual([item["kind"] for item in report["hooks"]], ["PreToolUse", "PostToolUse", "Stop"])
        self.assertTrue(all(item["ok"] for item in report["hooks"]))
        self.assertNotEqual(Path(report["bootstrapPython"]), self.plugin / ".venv/bin/python")
        inode = (self.plugin / ".venv").lstat().st_ino
        for arguments in (("--check",), ()):
            process, report = self.cli(*arguments, env=env)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertFalse(report["environmentAdded"])
            self.assertEqual(report["environmentState"], "existing-matching")
            self.assertEqual((self.plugin / ".venv").lstat().st_ino, inode)
        self.assertEqual(before, self.own_files())
        self.assertFalse((self.root / "must-not-be-created").exists())
        self.assertFalse((self.plugin / "hooks/__pycache__").exists())

    def test_existing_file_is_never_replaced(self):
        link = self.plugin / ".venv"
        link.write_bytes(b"keep this existing file")
        process, report = self.cli()
        self.assertEqual(process.returncode, 1)
        self.assertIn("left untouched", report["error"])
        self.assertEqual(link.read_bytes(), b"keep this existing file")

    def test_dangling_link_is_never_replaced(self):
        link = self.plugin / ".venv"
        target = self.root / "missing-original-venv"
        link.symlink_to(target)
        process, report = self.cli()
        self.assertEqual(process.returncode, 1)
        self.assertIn("left untouched", report["error"])
        self.assertEqual(os.readlink(link), str(target))

    def test_existing_different_environment_is_retained(self):
        link = self.plugin / ".venv"
        venv.EnvBuilder(with_pip=False, symlinks=True).create(link)
        self.assertTrue(os.path.samefile(link / "bin/python", sys.executable))
        (link / "canary").write_bytes(b"original environment")
        process, report = self.cli()
        self.assertEqual(process.returncode, 1)
        self.assertIn("does not match requested venv", report["error"])
        self.assertFalse(link.is_symlink())
        self.assertEqual((link / "canary").read_bytes(), b"original environment")

    def test_bare_venv_missing_dependencies_fails_before_mutation(self):
        bare = self.root / "bare"
        venv.EnvBuilder(with_pip=False).create(bare)
        self.python = bare / "bin/python"
        process, report = self.cli()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(report["stage"], "dependencies")
        failed = {item["name"] for item in report["runtime"]["checks"] if not item["ok"]}
        self.assertEqual(failed, preflight.DEPENDENCIES)
        self.assertIn("lxml", report["error"])
        self.assertFalse(os.path.lexists(self.plugin / ".venv"))

    def test_base_interpreter_is_not_accepted_as_a_venv(self):
        self.python = Path(sys._base_executable)
        process, report = self.cli()
        self.assertEqual(process.returncode, 1)
        self.assertIn("virtual environment", report["error"])
        self.assertFalse(os.path.lexists(self.plugin / ".venv"))

    def test_declared_version_bounds_are_checked_against_installed_packages(self):
        path = self.plugin / "pyproject.toml"
        path.write_text(path.read_text().replace('"lxml>=5"', '"lxml>=999"'))
        process, report = self.cli()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(report["stage"], "dependencies")
        self.assertIn("lxml>=999 required; found", report["error"])
        self.assertFalse(os.path.lexists(self.plugin / ".venv"))

    def test_python_version_boundary_and_xml_dylib_diagnostic(self):
        value = {"version": [3, 10, 14], "prefix": str(self.prefix), "basePrefix": "/base", "checks": []}
        with self.assertRaisesRegex(preflight.PreflightError, ">=3.11"):
            preflight._validate_runtime(value)
        value["version"] = [3, 11, 14]
        value["checks"] = [{"name": "stdlib XML / pyexpat", "ok": False,
                            "error": "ImportError: dlopen: incompatible libexpat dylib"}]
        with self.assertRaisesRegex(preflight.PreflightError, "pyexpat.*incompatible libexpat"):
            preflight._validate_runtime(value)

    def test_unrecognized_manifest_is_not_executed(self):
        path = self.plugin / "hooks/hooks.json"
        value = json.loads(path.read_text())
        value["hooks"]["PreToolUse"][0]["hooks"][0]["command"] += "; touch unwanted"
        path.write_text(json.dumps(value))
        process, report = self.cli()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(report["stage"], "manifest")
        self.assertIn("Unsupported PreToolUse", report["error"])
        self.assertFalse((self.root / "unwanted").exists())
        self.assertFalse(os.path.lexists(self.plugin / ".venv"))

    def test_new_unsupported_dependency_fails_explicitly(self):
        path = self.plugin / "pyproject.toml"
        path.write_text(path.read_text().replace('"lxml>=5"', '"lxml>=5", "new-package>=1"'))
        process, report = self.cli()
        self.assertEqual(process.returncode, 1)
        self.assertIn("new runtime dependency new-package", report["error"])
        self.assertFalse(os.path.lexists(self.plugin / ".venv"))

    def test_failure_runs_all_hook_entries_and_preserves_new_link_and_sources(self):
        entry = self.plugin / "hooks/pre_tool.py"
        entry.write_text("raise RuntimeError('deliberate startup regression')\n")
        before = self.own_files()
        process, report = self.cli()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(report["stage"], "hooks")
        self.assertTrue(report["environmentAdded"])
        self.assertTrue((self.plugin / ".venv").is_symlink())
        self.assertEqual(len(report["hooks"]), 3)
        self.assertFalse(report["hooks"][0]["ok"])
        self.assertIn("deliberate startup regression", report["hooks"][0]["stderr"])
        self.assertTrue(report["hooks"][1]["ok"])
        self.assertTrue(report["hooks"][2]["ok"])
        self.assertEqual(before, self.own_files())

    def test_workspace_discovery_guard_does_not_open_or_modify_workspace(self):
        home = self.root / ".pptx-agent/canary"
        home.mkdir(parents=True)
        state = home / "state.json"
        state.write_bytes(b"do not parse or change this")
        nested = self.root / "temporary-probe"
        nested.mkdir()
        with self.assertRaisesRegex(preflight.PreflightError, "ancestor contains a PPTX workspace"):
            preflight._empty_workspace(nested)
        self.assertEqual(state.read_bytes(), b"do not parse or change this")

    def test_launch_timeout_is_bounded(self):
        with patch.object(preflight, "TIMEOUT", 0.1):
            with self.assertRaisesRegex(preflight.PreflightError, "exceeded"):
                preflight._run([sys.executable, "-I", "-B", "-c", "import time; time.sleep(3)"],
                               cwd=self.root, env=preflight._environment(self.plugin))


if __name__ == "__main__":
    unittest.main()
