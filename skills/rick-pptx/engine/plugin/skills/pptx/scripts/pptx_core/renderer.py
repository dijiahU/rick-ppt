from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
import tempfile
import re
import time
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

from .common import PptxError, now, sha256


def executables():
    soffice = os.environ.get("PPTX_SOFFICE") or shutil.which("soffice")
    mac = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    if not soffice and mac.exists():
        soffice = str(mac)
    ppm = shutil.which("pdftoppm")
    if not soffice or not ppm:
        raise PptxError("Rendering requires LibreOffice (soffice) and Poppler (pdftoppm). "
                        "Install them or set PPTX_SOFFICE to the soffice executable.")
    return soffice, ppm


def run(command, timeout, env=None):
    configured=(os.environ if env is None else env).get('PPTX_RENDER_TIMEOUT_SECONDS')
    if configured is not None:
        try:seconds=int(configured)
        except ValueError:raise PptxError('Invalid host render timeout') from None
        if not timeout<=seconds<=300:raise PptxError('Host render timeout must cover the native default and stay within 300 seconds')
        timeout=seconds
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise PptxError(f"Renderer failed: {exc}") from exc
    if proc.returncode:
        diagnostic=proc.stderr.strip() or proc.stdout.strip() or 'No renderer diagnostic; check executable permissions and host sandbox access.'
        raise PptxError(f"Renderer exited {proc.returncode}: {diagnostic[-3000:]}")
    return proc


def font_environment(stage, soffice):
    # Local macOS LibreOffice may discover only its bundled Latin fonts.
    # Keep the fix per-render and preserve an explicitly supplied host config.
    env=os.environ.copy()
    if sys.platform!='darwin' or env.get('FONTCONFIG_FILE') or Path(soffice).name!='soffice':return env
    directories=[Path('/Library/Fonts'),Path('/System/Library/Fonts'),Path(soffice).parent.parent/'Resources/fonts/truetype']
    config=stage/'fonts.conf'
    config.write_text('<?xml version="1.0"?><fontconfig>'+''.join('<dir>'+escape(str(p))+'</dir>' for p in directories if p.is_dir())+'<cachedir>'+escape(str(stage/'font-cache'))+'</cachedir></fontconfig>')
    env['FONTCONFIG_FILE']=str(config)
    return env


def render_package(pptx, destination, slide=None, expected_pages=None):
    started=time.monotonic()
    soffice, ppm = executables()
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".render-", dir=destination) as temp:
        stage = Path(temp)
        profile = stage / "profile"
        selection=os.environ.get('PPTX_RENDER_PAGE_RANGE','0')
        if selection not in ('0','1'):raise PptxError('Invalid selected-page render configuration')
        selected=slide is not None and selection=='1'
        options={'ExportHiddenSlides':{'type':'boolean','value':'true'}}
        if selected:
            if type(slide) is not int or not 1<=slide<=200:raise PptxError('Invalid selected page')
            options['PageRange']={'type':'string','value':str(slide)}
        conversion_started=time.monotonic()
        # Unique user profile prevents collisions with an open LibreOffice session.
        run([soffice, f"-env:UserInstallation={profile.as_uri()}", "--headless",
             "--convert-to", 'pdf:impress_pdf_Export:'+json.dumps(options,separators=(',',':')), "--outdir", str(stage),
             str(Path(pptx).resolve())], 90, env=font_environment(stage,soffice))
        pdf = stage / (Path(pptx).stem + ".pdf")
        if not pdf.is_file() or pdf.stat().st_size < 100:
            raise PptxError("LibreOffice produced no PDF")
        pdf_seconds=time.monotonic()-conversion_started
        if selected:
            info=shutil.which('pdfinfo')
            if not info:raise PptxError('Selected-page export requires Poppler pdfinfo')
            output=run([info,str(pdf)],30,env={**os.environ,'LC_ALL':'C'}).stdout
            match=re.search(r'^Pages:\s+(\d+)\s*$',output,re.MULTILINE)
            if not match or int(match[1])!=1:raise PptxError('Selected-page export did not produce exactly one PDF page')
        args = [ppm, "-png", "-r", "100"]
        if slide is not None:
            page=1 if selected else slide
            args += ["-f", str(page), "-l", str(page)]
        png_started=time.monotonic()
        run([*args, str(pdf), str(stage / "slide")], 90)
        png_seconds=time.monotonic()-png_started
        pngs = sorted(stage.glob("slide-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
        count = 1 if slide is not None else expected_pages
        if not pngs or (count is not None and len(pngs) != count):
            raise PptxError(f"Unexpected rendered page count: {len(pngs)}; expected {count}")
        for path in pngs:
            with Image.open(path) as picture:
                picture.verify()
        # Publish an immutable generation; old render reports remain valid.
        final = destination / ("render-" + stage.name.removeprefix(".render-"))
        final.mkdir()
        output = []
        for path in pngs:
            number = slide if selected else int(path.stem.split("-")[-1])
            dest = final / f"slide-{number}.png"
            shutil.move(path, dest)
            output.append(str(dest))
        shutil.move(pdf, final / "deck.pdf")
        environment_path=stage/'render-environment.json'
        environment=json.loads(environment_path.read_text()) if environment_path.is_file() else {
            'renderer_executable':str(soffice),'platform':sys.platform,'fontconfig':bool(font_environment(stage,soffice).get('FONTCONFIG_FILE')),
            'powerpoint_playback_verified':False}
        (final/'render-environment.json').write_text(json.dumps(environment,ensure_ascii=False,indent=2))
        host_timing=stage/'render-timings.json'
        timings={'pdf_request_seconds':round(pdf_seconds,4),'png_seconds':round(png_seconds,4),
                 'total_seconds':round(time.monotonic()-started,4)}
        if host_timing.is_file():timings['host']=json.loads(host_timing.read_text())
        (final/'render-timings.json').write_text(json.dumps(timings,indent=2))
    return {"at": now(), "source_hash": sha256(pptx), "pages": output,
            "pdf": str(final / "deck.pdf"), "renderer": "LibreOffice", "environment":environment,
            "timings":timings,"selected_page_export":selected,"ok": True}


def render(ws, slide=None):
    from .manifest import changed_paths, content_fingerprint, manifest
    from .package import pack
    from .relationships import slide_parts
    from .validator import validate
    with ws.lock():
        before = ws.refresh()
        validate(ws.root).require()
        total = len(slide_parts(ws.root))
        if slide is not None and not 1 <= slide <= total:
            raise PptxError(f"Slide must be between 1 and {total}")
        with tempfile.TemporaryDirectory(dir=ws.home / "output") as temp:
            pptx = Path(temp) / "preview.pptx"
            pack(ws.root, pptx)
            result = render_package(pptx, ws.home / "renders", slide, total)
        if changed_paths(before, manifest(ws.root)):
            raise PptxError("Workspace changed during rendering; render again")
        result['workspace_fingerprint'] = content_fingerprint(before)
        result['page_numbers'] = [slide] if slide is not None else list(range(1, total + 1))
        # Retain immutable per-page images for the author, including on resume.
        # This is observation evidence, not an aesthetic or playback verdict.
        previews = ws.state.setdefault('page_previews', {})
        parts = slide_parts(ws.root)
        for number, image in zip(result['page_numbers'], result['pages']):
            previews[str(number)] = {'part': parts[number - 1],
                'image': str(Path(image).relative_to(ws.home)), 'image_sha256': sha256(image),
                'workspace_fingerprint': result['workspace_fingerprint'],
                'source_hash': result['source_hash'], 'at': result['at']}
        ws.state["last_render"] = result
        ws.save()
        return result
