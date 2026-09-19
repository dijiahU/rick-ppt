"""Real isolated decoder tests using synthetic fixtures, not customer artwork."""
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from PIL import Image
from web_media import normalize

for fmt in ('PNG','JPEG','WEBP','BMP','TIFF'):
    b=io.BytesIO();Image.new('RGB',(64,48),'orange').save(b,format=fmt)
    meta,files=normalize(b.getvalue());assert meta['kind']=='image' and meta['width']==64
    print('PASS',fmt,flush=True)
avif=Path(__file__).resolve().parent.parent/'builds/sts2-build/assets/cast.avif'
if avif.exists():
    meta,files=normalize(avif.read_bytes());assert meta['originalFormat']=='AVIF';print('PASS AVIF',flush=True)
meta,files=normalize(b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="48"><rect width="64" height="48" fill="orange"/></svg>')
assert meta['conversion']=='SVG raster fallback';print('PASS SVG explicit fallback',flush=True)
for bad in (b'<html>not an image</html>',b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',b'<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///etc/passwd"/></svg>'):
    try:normalize(bad)
    except ValueError:pass
    else:raise AssertionError('Unsafe content accepted')
print('PASS corrupt/active/external resources rejected',flush=True)
with tempfile.TemporaryDirectory(prefix='pptx-media-fixtures-') as directory:
    root=Path(directory)
    docker=['/usr/local/bin/docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--memory','1g','--cpus','1','--user',f'{os.getuid()}:{os.getgid()}','--mount',f'type=bind,source={root},target=/work','--entrypoint','ffmpeg','pptx-lab-media:1','-v','error','-y']
    for fmt,extra in [('webm',['-c:v','libvpx-vp9']),('mov',['-c:v','libx264']),('avi',['-c:v','mpeg4'])]:
        subprocess.run(docker+['-f','lavfi','-i','color=c=blue:s=160x90:d=1','-threads','1',*extra,'/work/fixture.'+fmt],check=True,timeout=30)
        meta,files=normalize((root/('fixture.'+fmt)).read_bytes());assert meta['kind']=='video';print('PASS',fmt,'→ MP4',flush=True)
    for fmt in ('wav','flac','ogg','m4a'):
        subprocess.run(docker+['-f','lavfi','-i','sine=frequency=440:duration=1','-threads','1','/work/fixture.'+fmt],check=True,timeout=30)
        meta,files=normalize((root/('fixture.'+fmt)).read_bytes());assert meta['kind']=='audio';print('PASS',fmt,'→ MP3',flush=True)
