"""Read-only capability check; never installs or contacts an API."""
import importlib
import json
from pathlib import Path
import shutil
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    checks = {'python_3_11': sys.version_info >= (3, 11), 'posix_host': sys.platform != 'win32'}
    details = {'python': sys.version.split()[0], 'platform': sys.platform}
    for module in ('lxml.etree', 'PIL.Image', 'jsonschema'):
        try:
            importlib.import_module(module)
            checks[module] = True
        except ImportError:
            checks[module] = False
    for name in ('assets/blank.pptx', 'assets/workflow-choices.json', 'references/workflow-branches.md'):
        checks[name] = (root / name).is_file()
    try:
        from pptx_core.renderer import executables
        office, poppler = executables()
        checks['renderer'] = Path(office).is_file() and bool(shutil.which(poppler))
        details['renderer'] = {'soffice': office, 'pdftoppm': poppler}
    except Exception as exc:
        checks['renderer'] = False
        details['renderer'] = str(exc)
    ok = all(checks.values())
    print(json.dumps({'ok': ok, 'checks': checks, 'details': details}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
