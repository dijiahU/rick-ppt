"""Install a validated local marketplace release, retaining every previous cache.

Run only after the source/build gates pass. No marketplace/config file is edited.
The next Codex thread picks up the installed version; existing threads retain theirs.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[1]/'pptx-agent')
    parser.add_argument('--python',type=Path)
    parser.add_argument('--backup-root',type=Path)
    args=parser.parse_args()
    source=args.source.resolve(strict=True);python=(args.python or source/'.venv/bin/python').absolute()
    codex_root=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex'))).expanduser()
    helpers=codex_root/'skills/.system/plugin-creator/scripts'
    market=subprocess.check_output([str(python),str(helpers/'read_marketplace_name.py')],text=True).strip()
    name=json.loads((source/'.codex-plugin/plugin.json').read_text())['name']
    listing=json.loads(subprocess.check_output(['codex','plugin','list','--marketplace',market,'--json'],text=True))
    entries=[item for items in listing.values() if isinstance(items,list) for item in items if isinstance(item,dict)]
    matches=[entry for entry in entries if entry.get('name')==name and entry.get('marketplaceName')==market and entry.get('source',{}).get('source')=='local']
    paths={entry['source']['path'] for entry in matches}
    if len(paths)!=1:raise RuntimeError('Expected one configured local marketplace source')
    target=Path(paths.pop()).resolve(strict=True)
    if target==source or source.is_relative_to(target) or target.is_relative_to(source):raise ValueError('Use an isolated development checkout distinct from the marketplace source')
    if json.loads((target/'.codex-plugin/plugin.json').read_text())['name']!=name:raise ValueError('Marketplace source identity mismatch')
    for file in ('runtime/dist/preview.html','runtime/dist/content.html','runtime/manifests/manifest.addin.xml'):
        if not (source/file).is_file():raise ValueError('Build the runtime before installing: '+file)
    subprocess.run([str(python),str(helpers/'validate_plugin.py'),str(source)],check=True)
    cache=codex_root/'plugins/cache'/market/name
    backup_parent=args.backup_root.resolve() if args.backup_root else None
    if backup_parent:backup_parent.mkdir(parents=True,exist_ok=True)
    backup=Path(tempfile.mkdtemp(prefix='pptx-plugin-release-',dir=backup_parent))
    shutil.copytree(target,backup/'marketplace-source-before',symlinks=True)
    previous=[p for p in cache.iterdir() if p.is_dir()] if cache.is_dir() else []
    for old in previous:shutil.copytree(old,backup/'caches-before'/old.name,symlinks=True)
    # Hashed build chunks must match the tested distribution exactly. Retain an
    # older build under the release backup instead of mixing its stale chunks
    # into the new runtime or deleting them.
    old_distribution=target/'runtime/dist'
    if old_distribution.parent.is_symlink() or old_distribution.is_symlink():raise ValueError('Unexpected marketplace distribution symlink')
    if old_distribution.exists():old_distribution.rename(backup/'retained-runtime-dist')
    ignore={'.venv','node_modules','__pycache__','.pytest_cache','test-results','playwright-report','.git','.DS_Store','coverage'}
    def copy_tree(src,dst):
        if dst.is_symlink():raise ValueError('Refusing to write through marketplace symlink')
        dst.mkdir(parents=True,exist_ok=True)
        for item in src.iterdir():
            if item.name in ignore:continue
            out=dst/item.name
            if item.is_symlink():raise ValueError('Release source contains an unexpected symlink: '+str(item))
            if out.is_symlink():raise ValueError('Refusing to replace marketplace symlink: '+str(out))
            if item.is_dir():copy_tree(item,out)
            elif item.is_file():shutil.copy2(item,out)
    copy_tree(source,target)
    subprocess.run([str(python),str(helpers/'update_plugin_cachebuster.py'),str(target)],check=True)
    subprocess.run([str(python),str(helpers/'validate_plugin.py'),str(target)],check=True)
    version=json.loads((target/'.codex-plugin/plugin.json').read_text())['version']
    try:
        subprocess.run(['codex','plugin','add',name+'@'+market],check=True,timeout=120)
    finally:
        for old in previous:
            if not old.exists():shutil.copytree(backup/'caches-before'/old.name,old,symlinks=True)
    installed=cache/version
    if not installed.is_dir():raise RuntimeError('Installed release cache was not created')
    environment=installed/'.venv'
    if not environment.exists() and not environment.is_symlink():environment.symlink_to(python.parent.parent,target_is_directory=True)
    # The installed release has its own version; mirror that exact manifest into Git.
    shutil.copy2(target/'.codex-plugin/plugin.json',source/'.codex-plugin/plugin.json')
    for top in ('skills','hooks','.codex-plugin','runtime/dist','runtime/manifests'):
        for item in (source/top).rglob('*'):
            if item.is_file() and not any(part in ignore for part in item.parts):
                if (installed/item.relative_to(source)).read_bytes()!=item.read_bytes():raise RuntimeError('Installed file differs: '+str(item.relative_to(source)))
    with tempfile.TemporaryDirectory(prefix='pptx-hook-check-') as task:
        for release in [*previous,installed]:
            for name in ('pre_tool.py','post_tool.py','stop.py'):
                hook=release/'hooks'/name
                if not hook.is_file():continue
                result=subprocess.run([str(python),str(hook)],input=json.dumps({'cwd':task,'tool_name':'Bash','tool_input':{'command':'pwd'}}),capture_output=True,text=True,timeout=10)
                if result.returncode or result.stdout.strip():raise RuntimeError('Release hook smoke failed: '+str(hook))
    print(json.dumps({'version':version,'installed':str(installed),'backup':str(backup),'preserved_caches':len(previous),'hook_checks':'passed'}))


if __name__=='__main__':main()
