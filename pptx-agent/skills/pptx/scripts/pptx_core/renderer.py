from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
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
    soffice, ppm = executables()
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".render-", dir=destination) as temp:
        stage = Path(temp)
        profile = stage / "profile"
        # Unique user profile prevents collisions with an open LibreOffice session.
        run([soffice, f"-env:UserInstallation={profile.as_uri()}", "--headless",
             "--convert-to", 'pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"true"}}', "--outdir", str(stage),
             str(Path(pptx).resolve())], 90, env=font_environment(stage,soffice))
        pdf = stage / (Path(pptx).stem + ".pdf")
        if not pdf.is_file() or pdf.stat().st_size < 100:
            raise PptxError("LibreOffice produced no PDF")
        args = [ppm, "-png", "-r", "100"]
        if slide is not None:
            args += ["-f", str(slide), "-l", str(slide)]
        run([*args, str(pdf), str(stage / "slide")], 90)
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
            number = int(path.stem.split("-")[-1])
            dest = final / f"slide-{number}.png"
            shutil.move(path, dest)
            output.append(str(dest))
        shutil.move(pdf, final / "deck.pdf")
    return {"at": now(), "source_hash": sha256(pptx), "pages": output,
            "pdf": str(final / "deck.pdf"), "renderer": "LibreOffice", "ok": True}


def render(ws, slide=None):
    from .manifest import changed_paths, manifest
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
        ws.state["last_render"] = result
        ws.save()
        return result
