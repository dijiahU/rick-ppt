"""Read-only capability check; never installs or contacts an API."""
import importlib
import importlib.metadata
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import subprocess


def package_integrity(root):
    """Verify the published payload, including the entrypoint and engine.

    Additional user configuration/venvs are not package members. Old releases
    without payload hashes are unknown, not retroactively declared verified.
    """
    try:
        manifest=json.loads((root/'assets/package-manifest.json').read_text())
        files=manifest.get('files')
        if not isinstance(files,dict) or not files:
            return {'verified':False,'reason':'This release has no payload hashes; use the current full package.'}
        digest=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        mismatches=[]
        for relative,expected in files.items():
            path=root/relative
            if Path(relative).is_absolute() or '..' in Path(relative).parts or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                mismatches.append(relative);continue
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                mismatches.append(relative)
        return {'verified':not mismatches and digest==manifest.get('package_id'),
                'package_id':manifest.get('package_id'),'checked_files':len(files),
                'mismatches':mismatches,'manifest_digest_matches':digest==manifest.get('package_id')}
    except (OSError,ValueError,TypeError) as error:
        return {'verified':False,'reason':type(error).__name__}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--full',action='store_true')
    args=parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    checks = {'python_3_11': sys.version_info >= (3, 11), 'posix_host': sys.platform != 'win32'}
    details = {'python': sys.version.split()[0], 'platform': sys.platform}
    for module in ('lxml.etree', 'PIL.Image', 'jsonschema', 'fontTools.ttLib'):
        try:
            importlib.import_module(module)
            checks[module] = True
        except ImportError:
            checks[module] = False
    for name in ('assets/blank.pptx', 'assets/workflow-choices.json', 'assets/workflow-choices-v3.json', 'references/workflow-branches.md'):
        checks[name] = (root / name).is_file()
    try:
        from pptx_core.renderer import executables
        office, poppler = executables()
        checks['renderer'] = Path(office).is_file() and bool(shutil.which(poppler))
        details['renderer'] = {'soffice': office, 'pdftoppm': poppler}
    except Exception as exc:
        checks['renderer'] = False
        details['renderer'] = str(exc)
    if args.full:
        details['package_integrity']=package_integrity(root)
        checks['package_integrity']=details['package_integrity']['verified']
        for name in ('native_batch.py','native_pages.py','planning_commit.py','tool_prepare.py','portable_workflow.py','dsh_adapter.py'):
            checks['full_tool:'+name]=(root/'scripts'/name).is_file()
        checks['production_engine']=(root/'engine/runner/workflow.py').is_file() and (root/'engine/workflow/journal.py').is_file()
        try:
            details['dsh_sdk_version']=importlib.metadata.version('deepseek-harness-sdk')
            checks['dsh_sdk']=details['dsh_sdk_version']=='0.2.1rc2'
        except importlib.metadata.PackageNotFoundError:checks['dsh_sdk']=False
        docker=shutil.which('docker')
        checks['full_renderer']=False
        if docker:
            try:
                result=subprocess.run([docker,'image','inspect','pptx-lab-renderer:1','--format','{{.Id}}'],capture_output=True,text=True,timeout=6)
                checks['full_renderer']=result.returncode==0 and result.stdout.strip().startswith('sha256:')
            except (OSError,subprocess.TimeoutExpired):pass
        details['full_runtime']='DSH owns model/tool execution; model access, vision, search/generation and approvals depend on the explicitly selected profile. No inference sent by this check.'
    ok = all(checks.values())
    print(json.dumps({'ok': ok, 'checks': checks, 'details': details}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
