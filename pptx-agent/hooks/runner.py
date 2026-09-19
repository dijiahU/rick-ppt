"""Re-exec in the plugin venv when launched by Codex's default Python."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = Path(os.environ.get("PPTX_AGENT_PYTHON", str(ROOT / ".venv" / "bin" / "python")))
REEXEC_GUARD = "PPTX_AGENT_REEXEC_TARGET"


def same_runtime(target):
    """Compare runtime identity, not the spelling of a symlinked path.

    Venv executables can resolve to the same base binary while loading different
    site-packages, so comparing the executable alone is insufficient.
    """
    try:
        if not os.path.samefile(sys.executable, target):
            return False
        environment = target.parent.parent.resolve()
        if (environment / "pyvenv.cfg").is_file():
            return Path(sys.prefix).resolve() == environment
        return True
    except OSError:
        return False


def ensure_runtime(target):
    if not target.exists() or same_runtime(target):
        return
    identity = str(target.parent.resolve() / target.name)
    if os.environ.get(REEXEC_GUARD) == identity:
        raise SystemExit("PPTX Agent: Python runtime did not match after re-exec; "
                         "check PPTX_AGENT_PYTHON and the plugin .venv.")
    os.environ[REEXEC_GUARD] = identity
    os.execv(str(target), [str(target), *sys.argv])


ensure_runtime(VENV)
sys.path.insert(0, str(ROOT / "skills" / "pptx" / "scripts"))


def main(kind):
    from pptx_core.hooks import handle
    result = handle(kind, json.load(sys.stdin))
    if result:
        print(json.dumps(result, ensure_ascii=False))
