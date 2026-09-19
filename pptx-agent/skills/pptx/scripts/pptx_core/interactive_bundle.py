"""Assemble a self-contained, non-overwriting distribution after native export."""
from __future__ import annotations
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from .common import PptxError,atomic_json,sha256
from .manifest import manifest,changed_paths
from .package import export
from .interactive_validate import PLUGIN_ROOT,validate_interactive,validate_bundle_manifest,read_json


def assemble_bundle(ws,destination,zip_output=False):
    report=validate_interactive(ws.root,require_runtime=True)
    if not report['ok']:raise PptxError('; '.join(report['errors']))
    if not report['instances']:raise PptxError('No interactive instances to bundle')
    destination=Path(destination).absolute()
    if destination.exists() or destination.is_symlink():raise PptxError('Bundle destination already exists; choose a new directory')
    sidecar=ws.home/'interactive/deck';before=manifest(sidecar)
    runtime=PLUGIN_ROOT/'runtime/dist';manifest(runtime)
    if not (runtime/'preview.html').is_file():raise PptxError('Build runtime before bundling')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.interactive-bundle-',dir=destination.parent) as tmp:
        stage=Path(tmp)/'bundle';stage.mkdir()
        output=export(ws,stage/'presentation.pptx')
        shutil.copytree(sidecar,stage/'deck');shutil.copytree(runtime,stage/'runtime/dist');shutil.copytree(PLUGIN_ROOT/'runtime/manifests',stage/'manifests')
        # Small serving package travels with the bundle; it does not require the repo checkout.
        scripts=stage/'scripts';scripts.mkdir();server=scripts/'pptx_core';server.mkdir()
        for filename in ('__init__.py','common.py','interactive_server.py','interactive_validate.py'):
            shutil.copyfile(Path(__file__).parent/filename,server/filename)
        # Bundled server has local configuration and no mutation APIs.
        (server/'interactive_validate.py').write_text((server/'interactive_validate.py').read_text().replace("PLUGIN_ROOT = Path(__file__).resolve().parents[4]","PLUGIN_ROOT = Path(__file__).resolve().parents[2]"))
        shutil.copyfile(PLUGIN_ROOT/'runtime/config.json',stage/'runtime/config.json')
        shutil.copytree(PLUGIN_ROOT/'skills/pptx/schemas',stage/'skills/pptx/schemas')
        bundle=read_json(stage/'deck/bundle.json');bundle['pptxHash']=sha256(output);atomic_json(stage/'deck/bundle.json',bundle);validate_bundle_manifest(bundle,stage/'deck')
        (scripts/'requirements.txt').write_text('aiohttp>=3.11,<4\njsonschema>=4.23,<5\nlxml>=5\n')
        (scripts/'start.command').write_text('#!/bin/sh\nset -eu\ncd "$(dirname "$0")/.."\nexec python3 scripts/serve.py\n')
        (scripts/'start.ps1').write_text('Set-Location (Join-Path $PSScriptRoot "..")\npython scripts/serve.py\n')
        (scripts/'serve.py').write_text('from pathlib import Path\nfrom pptx_core.interactive_server import main\nroot=Path(__file__).resolve().parents[1]\nmain(["--root",str(root),"--runtime",str(root/"runtime/dist")])\n')
        (scripts/'stop.command').write_text('#!/bin/sh\nprintf "Stop the foreground runtime using Ctrl+C in its terminal. No other processes are stopped.\\n"\n')
        (scripts/'stop.ps1').write_text('Write-Output "Stop the foreground runtime using Ctrl+C in its terminal. No other processes are stopped."\n')
        for path in scripts.glob('*.command'):path.chmod(0o755)
        (stage/'README.txt').write_text('Interactive presentation bundle\n\n1. Install Python 3.11+ and run python3 -m pip install -r scripts/requirements.txt\n2. Install a trusted localhost certificate with office-addin-dev-certs on this computer.\n3. Sideload manifests/manifest.addin.xml in PowerPoint (or unified manifest on supported hosts).\n4. Run scripts/start.command (macOS/Linux) or scripts/start.ps1 (Windows).\n5. Open presentation.pptx. Keep the runtime terminal open while presenting.\n\nStandalone preview: https://localhost:41973/preview.html?deck='+bundle['deckId']+'&scene='+next(iter(bundle['scenes']))+'\nOffice.js is loaded from Microsoft; all deck assets and feature packs are local.\nBrowser tests do not certify PowerPoint playback. See verification.json.\n')
        atomic_json(stage/'verification.json',report)
        # Inventory the whole distribution, including optional WASM/model chunks.
        atomic_json(stage/'checksums.json',{k:v['hash'] for k,v in manifest(stage).items()})
        if changed_paths(before,manifest(sidecar)):raise PptxError('Sidecar changed during bundle assembly')
        destination.mkdir()  # No replacement of existing files.
        for child in stage.iterdir():shutil.move(str(child),destination/child.name)
    zipped=None
    if zip_output:
        zipped=destination.with_suffix('.zip')
        with zipfile.ZipFile(zipped,'x',zipfile.ZIP_DEFLATED) as archive:
            for name in manifest(destination):archive.write(destination/name,destination.name+'/'+name)
    ws.state.update(latest_bundle=str(destination),interactive_dirty=False,interactive_baseline=manifest(sidecar));ws.save()
    return {'bundle':str(destination),'zip':str(zipped) if zipped else None,'pptx':str(destination/'presentation.pptx'),'runtime_verified':report['runtime_verified'],'powerpoint_playback_verified':False}
