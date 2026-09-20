"""Exercise release failure propagation without calling Codex or a marketplace.

All release/cache trees are temporary fixtures. Only the real preflight and
harmless hook processes run; marketplace helpers and Codex install are simulated.
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent / "pptx-agent"
spec = importlib.util.spec_from_file_location("update_plugin_under_test", HERE / "update-plugin.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class IsolatedCommands:
    TimeoutExpired = subprocess.TimeoutExpired

    def __init__(self, test):
        self.test = test
        self.calls = []

    def check_output(self, command, **kwargs):
        self.calls.append(command)
        if Path(command[1]).name == "read_marketplace_name.py":
            return "private-fixture-market\n"
        if command[:3] == ["codex", "plugin", "list"]:
            return json.dumps({"plugins": [{"name": "pptx-agent", "marketplaceName": "private-fixture-market",
                                          "source": {"source": "local", "path": str(self.test.target)}}]})
        raise AssertionError(f"Unexpected external command: {command}")

    def run(self, command, **kwargs):
        self.calls.append(command)
        name = Path(command[1]).name
        if name == "validate_plugin.py":
            return subprocess.CompletedProcess(command, 0)
        if name == "update_plugin_cachebuster.py":
            path = self.test.target / ".codex-plugin/plugin.json"
            manifest = json.loads(path.read_text())
            manifest["version"] = self.test.version
            path.write_text(json.dumps(manifest))
            return subprocess.CompletedProcess(command, 0)
        if command == ["codex", "plugin", "add", "pptx-agent@private-fixture-market"]:
            shutil.copytree(self.test.target, self.test.installed)
            if self.test.existing_environment_file:
                (self.test.installed / ".venv").write_bytes(b"retain installed environment file")
            # Simulate cache eviction inside this private fixture. The real
            # release code's finally block must restore its retained old cache.
            assert self.test.previous.is_relative_to(self.test.root)
            shutil.rmtree(self.test.previous)
            return subprocess.CompletedProcess(command, 0)
        if name == "configure-installed-hooks.py" or (Path(command[1]).parent.name == "hooks" and name in {"pre_tool.py", "post_tool.py", "stop.py"}):
            env = {key: value for key, value in os.environ.items()
                   if key in {"PATH", "LANG", "LC_ALL", "TMPDIR"}}
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            if self.test.bootstrap_path is not None:
                env["PATH"] = str(self.test.bootstrap_path)
            return subprocess.run(command, **kwargs, env=env)
        raise AssertionError(f"Refusing any unrecognized process in release test: {command}")


class UpdatePluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="test-plugin-release-gate-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source/pptx-agent"
        self.target = self.root / "marketplace/pptx-agent"
        self.fixture_codex = self.root / "codex-fixture"
        self.cache = self.fixture_codex / "plugins/cache/private-fixture-market/pptx-agent"
        self.backups = self.root / "backups"
        self.version = "0.1.0+codex.fixture-new"
        self.previous = self.cache / "0.1.0+codex.fixture-old"
        self.installed = self.cache / self.version
        self.source.mkdir(parents=True)
        (self.source / ".codex-plugin").mkdir()
        (self.source / ".codex-plugin/plugin.json").write_text(json.dumps({"name": "pptx-agent", "version": "0.1.0"}))
        shutil.copyfile(PLUGIN / "pyproject.toml", self.source / "pyproject.toml")
        shutil.copytree(PLUGIN / "hooks", self.source / "hooks", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(PLUGIN / "skills/pptx/scripts", self.source / "skills/pptx/scripts", ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("runtime/dist/preview.html", "runtime/dist/content.html", "runtime/manifests/manifest.addin.xml"):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("inert release fixture")
        shutil.copytree(self.source, self.target)
        (self.target / "runtime/dist/prior-chunk.js").write_text("retain previous build")
        shutil.copytree(self.target, self.previous)
        (self.previous / ".venv").symlink_to(Path(sys.prefix), target_is_directory=True)
        (self.previous / "old-cache-canary").write_bytes(b"preserve original cache")
        self.config = self.fixture_codex / "config.toml"
        self.config.write_text("# inert fixture: preserve disabled hooks\nhooks_enabled = false\n")
        self.original_config = self.config.read_bytes()
        self.bootstrap_path = None
        self.existing_environment_file = False
        self.commands = IsolatedCommands(self)
        self.assertNotEqual(sys.prefix, sys.base_prefix, "Use the project dependency venv for real preflight tests")

    def run_release(self):
        output = io.StringIO()
        self.output = output
        args = [str(HERE / "update-plugin.py"), "--source", str(self.source), "--python", sys.executable,
                "--backup-root", str(self.backups)]
        # Replace only this module's environment view; the process environment,
        # actual CODEX_HOME, user configuration and CLI are never changed/read.
        with patch.object(module, "os", SimpleNamespace(environ={"CODEX_HOME": str(self.fixture_codex)})), \
             patch.object(module, "subprocess", self.commands), patch.object(sys, "argv", args), \
             contextlib.redirect_stdout(output):
            module.main()
        return json.loads(output.getvalue())

    def receipt(self):
        backups = list(self.backups.glob("pptx-plugin-release-*"))
        self.assertEqual(len(backups), 1)
        return backups[0], json.loads((backups[0] / "installed-hook-preflight.json").read_text())

    def assert_preserved(self):
        self.assertEqual((self.previous / "old-cache-canary").read_bytes(), b"preserve original cache")
        self.assertTrue((self.previous / ".venv").is_symlink())
        self.assertEqual(self.config.read_bytes(), self.original_config)
        backup, _ = self.receipt()
        self.assertEqual((backup / "retained-runtime-dist/prior-chunk.js").read_text(), "retain previous build")
        self.assertEqual((backup / "marketplace-source-before/runtime/dist/prior-chunk.js").read_text(), "retain previous build")
        self.assertTrue(self.installed.is_dir())

    def test_success_requires_real_default_launcher_preflight_and_keeps_old_checks(self):
        result = self.run_release()
        self.assertEqual(result["installed_default_hook_checks"], "passed")
        self.assertEqual(result["hook_checks"], "passed")
        backup, receipt = self.receipt()
        self.assertEqual(result["hook_preflight"], str(backup / "installed-hook-preflight.json"))
        self.assertTrue(receipt["ok"])
        self.assertTrue(receipt["report"]["environmentAdded"])
        self.assertEqual(len(receipt["report"]["hooks"]), 3)
        self.assertTrue(all(item["ok"] for item in receipt["report"]["hooks"]))
        explicit_checks = [call for call in self.commands.calls if Path(call[1]).parent.name == "hooks"]
        self.assertEqual(len(explicit_checks), 6, "Prior explicit-Python checks must remain for old and new cache")
        self.assert_preserved()

    def test_default_python_failure_blocks_success_even_when_explicit_python_works(self):
        self.bootstrap_path = self.root / "bad-bootstrap"
        self.bootstrap_path.mkdir()
        bad = self.bootstrap_path / "python3"
        bad.write_text("#!/bin/sh\nprintf 'fixture default launcher failed\\n' >&2\nexit 43\n")
        bad.chmod(0o755)
        # This was the old false-pass condition: the same hook does start when
        # called with the provisioned interpreter explicitly.
        direct = subprocess.run([sys.executable, str(self.source / "hooks/pre_tool.py")],
                                input=json.dumps({"cwd": str(self.root), "tool_name": "Bash", "tool_input": {"command": "pwd"}}),
                                capture_output=True, text=True, timeout=10,
                                env={"PATH": str(self.bootstrap_path), "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(direct.returncode, 0, direct.stderr)
        with self.assertRaisesRegex(RuntimeError, "default-launcher hook preflight failed"):
            self.run_release()
        self.assertEqual(self.output.getvalue(), "", "No success JSON may be emitted on failure")
        _, receipt = self.receipt()
        self.assertFalse(receipt["ok"])
        self.assertEqual(receipt["returncode"], 1)
        self.assertEqual([hook["returncode"] for hook in receipt["report"]["hooks"]], [43, 43, 43])
        self.assertEqual(json.loads((self.source / ".codex-plugin/plugin.json").read_text())["version"], "0.1.0")
        self.assert_preserved()

    def test_existing_environment_conflict_propagates_without_replacement(self):
        self.existing_environment_file = True
        with self.assertRaisesRegex(RuntimeError, "left untouched"):
            self.run_release()
        self.assertEqual(self.output.getvalue(), "")
        self.assertEqual((self.installed / ".venv").read_bytes(), b"retain installed environment file")
        _, receipt = self.receipt()
        self.assertEqual(receipt["report"]["stage"], "environment")
        self.assert_preserved()

    def test_invalid_success_report_and_timeout_both_retain_diagnostics(self):
        for index, outcome in enumerate((subprocess.CompletedProcess([], 0, "not JSON", ""), subprocess.TimeoutExpired("preflight", 120))):
            with self.subTest(index=index):
                backup = self.root / f"transport-backup-{index}"
                backup.mkdir()
                fake = SimpleNamespace(TimeoutExpired=subprocess.TimeoutExpired)
                def run(*args, **kwargs):
                    if isinstance(outcome, Exception):
                        raise outcome
                    return outcome
                fake.run = run
                with patch.object(module, "subprocess", fake), self.assertRaisesRegex(RuntimeError, "diagnostics and backups"):
                    module.check_installed_hooks(Path(sys.executable), self.target, backup)
                report = json.loads((backup / "installed-hook-preflight.json").read_text())
                self.assertFalse(report["ok"])
                if index == 0:
                    self.assertEqual(report["stdout"], "not JSON")
                else:
                    self.assertIn("TimeoutExpired", report["error"])
                self.assertTrue(self.target.is_dir())

    def test_missing_required_helper_fails_before_any_release_operation(self):
        with patch.object(module, "HOOK_PREFLIGHT", self.root / "missing-helper.py"), \
             self.assertRaisesRegex(RuntimeError, "Missing required installed-hook preflight"):
            self.run_release()
        self.assertFalse(self.commands.calls)
        self.assertFalse(self.installed.exists())
        self.assertFalse(self.backups.exists())


if __name__ == "__main__":
    unittest.main()
