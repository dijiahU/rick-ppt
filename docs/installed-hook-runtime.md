# Installed hook Python preflight

Run this after **every plugin install/cachebuster** and before accepting the new
version for desktop hooks or worker use. A successful worker invocation with an
explicit Python path does not prove that cached hooks work: `hooks.json` starts
`python3`, then the hook launcher selects `<installed-plugin>/.venv/bin/python`.
A cache installation can omit that environment. On this Mac, the default Python
also exposed an incompatible `pyexpat` dylib; checking only `python --version`
would miss it.

Use an already provisioned, retained Python 3.11+ venv with the plugin's core and
`interactive` dependencies. From the repository root:

```sh
python3 runner/configure-installed-hooks.py \
  --plugin /absolute/path/to/the/exact/installed/plugin-version \
  --python /absolute/path/to/verified/venv/bin/python

python3 runner/configure-installed-hooks.py \
  --plugin /absolute/path/to/the/exact/installed/plugin-version \
  --python /absolute/path/to/verified/venv/bin/python \
  --check
```

The normal `runner/update-plugin.py` release entry also runs this gate after
installation, before reporting success. Its report is retained as
`installed-hook-preflight.json` in the new release backup. A default-launcher
failure blocks release success even when an explicit venv invocation works;
the installed cache and all previous backups remain available for diagnosis.

The tool uses only the standard library; its own interpreter must be Python
3.11+. It does not install packages, reinstall a plugin, read runner settings,
start a worker/browser/renderer, or modify a deck. JSON is printed to stdout;
exit status `0` means all checks passed and `1` means preflight failed. Retain the
JSON with the private release evidence. Do not activate a version whose preflight
fails.

The checks cover:

- Python version and **venv prefix identity**, preserving Python executable
  symlinks. Two venvs that share a base binary are different environments.
- Real XML/`pyexpat`, lxml, Pillow PNG, JSON Schema and aiohttp operations, plus
  Playwright API import; installed versions must satisfy the plugin's declared
  core and interactive dependency bounds. New unrecognized dependencies or hook
  commands fail explicitly so the preflight cannot silently omit them.
- All three actual installed hook entries, launched through the manifest's
  default `python3` with no inherited `PPTX_AGENT_PYTHON`, Python path, workspace
  or plugin-data override. Each gets a harmless event in a new temporary directory
  whose ancestors contain no discoverable PPTX workspace. Startup is bounded to
  20 seconds per process. Sources are hashed before and after, and bytecode writes
  are disabled.

Configuration adds only a **missing** `.venv` symlink to the verified venv prefix.
An existing matching environment is retained. Existing files, other environments
and broken links produce a clear error and are never overwritten or removed.
`--check` never creates the link or writes into the installation; its temporary
probe directory is separate. If a hook still fails after a new link was created,
the link and all existing files remain for diagnosis. Keep the linked environment
available for as long as that installed plugin version may run.

This is an environment/startup gate. It does not establish actual PowerPoint
playback, Chromium installation, rendering correctness or hook behavior on a real
edited deck; those remain separate release smoke checks. It checks the invoking
process's `PATH`, so run it from the same launch environment used for the plugin.

Regression checks use isolated temporary plugin copies and require the provisioned
project venv:

```sh
pptx-agent/.venv/bin/python -B runner/test-installed-hooks.py
pptx-agent/.venv/bin/python -B runner/test-update-plugin.py
```

## Local incident verification, 2026-09-20

Cached releases `0.1.0+codex.20260919230549` and
`0.1.0+codex.20260919234350` lacked `.venv`. The real manifest launcher failed
with `ModuleNotFoundError: No module named 'lxml'`. Adding only the missing links
to the retained Python 3.11 dependency environment made all six pre/post/Stop
startup checks pass. The earlier `20260919170350` release also passed its three
startup checks, and all 20 retained cache versions passed default-launcher
PreToolUse checks in empty workspaces.

Verification includes 31 existing hook/runtime and CLI regressions, 14 new
environment-preflight tests, and five release-gate tests. A separate isolated
probe of cc-notify's ordinary Bash cleanup path passed 20 runs, with a maximum
duration of 53 ms against its 3-second timeout. No external notification was sent.

The existing hook enablement settings were left unchanged; at the subsequent
configuration inspection, all eight entries were disabled. These local checks
prove the repaired startup path and release gate. They do not establish that
previous UI failure messages disappeared or identify an additional live failure.
No presentation runtime, release version, or task artifact was changed by this
environment repair.
