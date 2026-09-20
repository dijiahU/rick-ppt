#!/usr/bin/env python3
"""Check/install the dependency environment used by a cached plugin's hooks.

This is an explicit local post-install step, not an installer or dependency
downloader. The only persistent mutation is a new, previously absent .venv link.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib


TIMEOUT = 20
MAX_OUTPUT = 65536
HOOKS = {"PreToolUse": "pre_tool.py", "PostToolUse": "post_tool.py", "Stop": "stop.py"}
DEPENDENCIES = {"lxml", "pillow", "jsonschema", "aiohttp", "playwright"}

# -I excludes caller PYTHONPATH/user site packages. Importing pyexpat explicitly
# catches broken base-Python dylibs that an executable/version check misses.
PROBE = r'''
import importlib.metadata, io, json, pathlib, re, sys
result = {"version": list(sys.version_info[:3]), "executable": sys.executable,
          "prefix": str(pathlib.Path(sys.prefix).resolve()),
          "basePrefix": str(pathlib.Path(sys.base_prefix).resolve()), "checks": []}
def check(name, operation):
    try:
        operation()
        result["checks"].append({"name": name, "ok": True})
    except Exception as exc:
        result["checks"].append({"name": name, "ok": False,
                                 "error": (type(exc).__name__ + ": " + str(exc))[:2000]})
def xml():
    import pyexpat
    from xml.sax.saxutils import escape
    pyexpat.ParserCreate().Parse('<probe/>', True)
    assert escape('<') == '&lt;'
def lxml():
    from lxml import etree
    assert etree.fromstring(b'<probe/>').tag == 'probe'
def pillow():
    from PIL import Image
    data = io.BytesIO()
    Image.new('RGB', (2, 2), 'white').save(data, 'PNG')
    data.seek(0)
    with Image.open(data) as picture:
        picture.load()
        assert picture.size == (2, 2)
def jsonschema():
    from jsonschema import Draft202012Validator
    Draft202012Validator({'type': 'integer'}).validate(1)
def aiohttp():
    from aiohttp import web
    assert web.Response(text='probe').status == 200
def playwright():
    from playwright.sync_api import sync_playwright
    assert callable(sync_playwright)
def release(value):
    if not re.fullmatch(r'\d+(?:\.\d+)*', value):
        raise ValueError('Cannot verify non-release version: ' + value)
    parts = tuple(map(int, value.split('.')))
    return parts + (0,) * max(0, 4-len(parts))
def dependency(item):
    version = importlib.metadata.version(item['name'])
    actual = release(version)
    for op, bound in item['bounds']:
        wanted = release(bound)
        if not {'>=': actual >= wanted, '<': actual < wanted,
                '>': actual > wanted, '<=': actual <= wanted, '==': actual == wanted}[op]:
            raise ValueError(item['requirement'] + ' required; found ' + version)
    globals()[item['name']]()
    result.setdefault('distributions', {})[item['name']] = version
check('stdlib XML / pyexpat', xml)
for item in json.loads(sys.argv[1]):
    check(item['name'], lambda item=item: dependency(item))
print(json.dumps(result))
'''


class PreflightError(Exception):
    pass


def _absolute(value: str) -> Path:
    # Do not resolve the final Python symlink: that discards venv identity.
    return Path(os.path.abspath(os.path.expanduser(value)))


def _environment(plugin: Path) -> dict[str, str]:
    allowed = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "SYSTEMROOT")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.setdefault("PATH", os.defpath)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PLUGIN_ROOT=str(plugin))
    return env


def _run(argv: list[str], *, cwd: Path, env: dict[str, str], payload: str | None = None) -> dict:
    try:
        proc = subprocess.run(argv, input=payload, text=True, capture_output=True,
                              cwd=cwd, env=env, timeout=TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise PreflightError(f"Startup exceeded {TIMEOUT} seconds: {Path(argv[-1]).name}") from exc
    except OSError as exc:
        raise PreflightError(f"Cannot launch {argv[0]}: {exc}") from exc
    if len(proc.stdout) > MAX_OUTPUT or len(proc.stderr) > MAX_OUTPUT:
        raise PreflightError("Startup output exceeded the 64 KiB diagnostic limit")
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def _requirements(plugin: Path) -> list[dict]:
    project = tomllib.loads((plugin / "pyproject.toml").read_text())["project"]
    declared = project["dependencies"] + project.get("optional-dependencies", {}).get("interactive", [])
    result = []
    for requirement in declared:
        match = re.fullmatch(r"([A-Za-z0-9_-]+)((?:(?:>=|<=|==|>|<)\d+(?:\.\d+)*(?:,|$))+)", requirement)
        if not match:
            raise PreflightError(f"Unsupported dependency declaration; update this preflight: {requirement!r}")
        name = match[1].lower().replace("_", "-")
        if name not in DEPENDENCIES:
            raise PreflightError(f"No import smoke for new runtime dependency {name}; update this preflight")
        bounds = re.findall(r"(>=|<=|==|>|<)(\d+(?:\.\d+)*)", match[2])
        result.append({"name": name, "requirement": requirement, "bounds": bounds})
    if {item["name"] for item in result} != DEPENDENCIES:
        raise PreflightError("Plugin must declare its four core dependencies and interactive Playwright extra")
    return result


def _commands(plugin: Path) -> list[dict]:
    manifest = json.loads((plugin / "hooks/hooks.json").read_text())
    result = []
    for kind, filename in HOOKS.items():
        groups = manifest["hooks"][kind]
        entries = [hook for group in groups for hook in group["hooks"]]
        expected = ["python3", f"$PLUGIN_ROOT/hooks/{filename}"]
        if len(entries) != 1 or entries[0].get("type") != "command" or shlex.split(entries[0]["command"]) != expected:
            raise PreflightError(f"Unsupported {kind} command; inspect its manifest before running preflight")
        path = plugin / "hooks" / filename
        if not path.is_file() or path.is_symlink():
            raise PreflightError(f"Missing or symlinked hook entry: {path}")
        result.append({"kind": kind, "entry": filename, "path": str(path)})
    return result


def _runtime(python: Path, requirements: list[dict], scratch: Path, env: dict[str, str]) -> dict:
    run = _run([str(python), "-I", "-B", "-c", PROBE, json.dumps(requirements)], cwd=scratch, env=env)
    if run["returncode"]:
        raise PreflightError(f"Python dependency probe failed ({run['returncode']}): {run['stderr'][-4000:]}")
    try:
        value = json.loads(run["stdout"])
    except (ValueError, TypeError) as exc:
        raise PreflightError("Python dependency probe did not return a JSON report") from exc
    return value


def _validate_runtime(value: dict) -> None:
    if tuple(value["version"]) < (3, 11):
        raise PreflightError("Python >=3.11 is required")
    prefix = Path(value["prefix"])
    if value["prefix"] == value["basePrefix"] or not (prefix / "pyvenv.cfg").is_file():
        raise PreflightError("--python must select a virtual environment, not a base interpreter")
    failed = [item for item in value["checks"] if not item["ok"]]
    if failed:
        raise PreflightError("Dependency checks failed: " + "; ".join(item["name"] + ": " + item["error"] for item in failed))


def _empty_workspace(cwd: Path) -> None:
    # Hook discovery walks ancestors. Never let a no-op test discover a real deck.
    for parent in [cwd, *cwd.parents]:
        if ((parent / "state.json").is_file() and (parent / "workspace").is_dir()) or any((parent / ".pptx-agent").glob("*/state.json")):
            raise PreflightError(f"Cannot safely probe hooks: temporary-directory ancestor contains a PPTX workspace: {parent}")


def _fingerprints(plugin: Path) -> dict[str, str]:
    names = ["pyproject.toml", "hooks/hooks.json", "hooks/runner.py", *["hooks/" + name for name in HOOKS.values()]]
    return {name: hashlib.sha256((plugin / name).read_bytes()).hexdigest() for name in names}


def configure(plugin_arg: str, python_arg: str, *, check: bool = False) -> dict:
    report = {"ok": False, "mode": "check" if check else "configure", "environmentAdded": False,
              "stage": "arguments", "hooks": [], "persistentMutation": "none"}
    try:
        plugin = _absolute(plugin_arg).resolve(strict=True)
        python = _absolute(python_arg)
        report.update(plugin=str(plugin), requestedPython=str(python))
        if not plugin.is_dir() or not python.is_file() or not os.access(python, os.X_OK):
            raise PreflightError("--plugin must be an installed directory and --python an executable file")
        report["stage"] = "manifest"
        requirements, commands = _requirements(plugin), _commands(plugin)
        fingerprints = _fingerprints(plugin)
        env = _environment(plugin)
        launcher = shutil.which("python3", path=env["PATH"])
        if not launcher:
            raise PreflightError("The hook manifest requires python3 on PATH; no launcher was found")
        report["bootstrapPython"] = launcher
        with tempfile.TemporaryDirectory(prefix="pptx-hook-preflight-") as temporary:
            scratch = Path(temporary).resolve()
            _empty_workspace(scratch)
            report["stage"] = "dependencies"
            runtime = _runtime(python, requirements, scratch, env)
            report["runtime"] = runtime
            _validate_runtime(runtime)
            target, link = Path(runtime["prefix"]), plugin / ".venv"
            report["environmentTarget"] = str(target)
            report["stage"] = "environment"
            if os.path.lexists(link):
                if not link.is_dir() or link.resolve() != target:
                    raise PreflightError(f"Existing {link} does not match requested venv {target}; left untouched")
                report["environmentState"] = "existing-matching"
            elif check:
                report["environmentState"] = "missing"
                raise PreflightError(f"Missing {link}; rerun without --check to add the verified environment link")
            else:
                try:
                    link.symlink_to(target, target_is_directory=True)
                except FileExistsError as exc:
                    raise PreflightError(".venv appeared during preflight; it was not replaced") from exc
                report.update(environmentAdded=True, environmentState="created", persistentMutation="added .venv symlink only")
            installed = _runtime(link / "bin/python", requirements, scratch, env)
            report["installedRuntime"] = installed
            _validate_runtime(installed)
            if installed["prefix"] != runtime["prefix"]:
                raise PreflightError("Installed .venv/bin/python selects a different runtime; left untouched")
            report["stage"] = "hooks"
            payload = json.dumps({"cwd": str(scratch), "tool_name": "Bash", "tool_input": {"command": "pwd"},
                                  "session_id": "installed-hook-preflight", "tool_use_id": "no-workspace", "stop_hook_active": False})
            for command in commands:
                try:
                    result = _run([launcher, command["path"]], cwd=scratch, env=env, payload=payload)
                    result["ok"] = result["returncode"] == 0 and not result["stdout"].strip()
                except PreflightError as exc:
                    result = {"ok": False, "error": str(exc)}
                report["hooks"].append({"kind": command["kind"], "entry": command["entry"], **result})
            if _fingerprints(plugin) != fingerprints:
                raise PreflightError("Hook sources changed during preflight; inspect them before using this installation")
            report["sourceSha256"] = fingerprints
            failed = [item["entry"] for item in report["hooks"] if not item["ok"]]
            if failed:
                raise PreflightError("Actual default-launcher hook startup failed: " + ", ".join(failed))
        report.update(ok=True, stage="complete")
    except (PreflightError, OSError, ValueError, KeyError, TypeError) as exc:
        report["error"] = str(exc)
        report["replacedOrDeletedExistingPaths"] = False
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", required=True, help="Exact installed plugin directory")
    parser.add_argument("--python", required=True, help="Already provisioned venv interpreter (Python >=3.11)")
    parser.add_argument("--check", action="store_true", help="Read-only installation check; never add or replace .venv")
    args = parser.parse_args()
    report = configure(args.plugin, args.python, check=args.check)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        print(f"PPTX hook preflight failed at {report['stage']}: {report['error']}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
