"""Untrusted media decoding runs only inside a no-network, limited container."""
import io
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import warnings
import xml.etree.ElementTree as ET
from PIL import Image, ImageOps

ROOT=Path('/work');SOURCE=ROOT/'input';LIMIT=28*1024*1024
Image.MAX_IMAGE_PIXELS=16777216
warnings.simplefilter('error',Image.DecompressionBombWarning)

def run(args,timeout=100):
    return subprocess.run(args,capture_output=True,check=True,timeout=timeout).stdout

def probe(path):
    return json.loads(run(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-show_entries','format=format_name,duration:stream=codec_type,codec_name,width,height','-of','json',str(path)],20))

def image_result(image,original_format,animated=False):
    image.seek(0);image=ImageOps.exif_transpose(image);image.thumbnail((4096,4096))
    image.convert('RGBA').save(ROOT/'poster.png')
    if animated:shutil.copyfile(SOURCE,ROOT/'media.gif');name='media.gif'
    else:shutil.copyfile(ROOT/'poster.png',ROOT/'media.png');name='media.png'
    return dict(kind='gif' if animated else 'image',file=name,poster='poster.png',originalFormat=original_format,animated=animated,width=image.width,height=image.height)

def main():
    data=SOURCE.read_bytes()
    if len(data)>30*1024*1024:raise ValueError('Input exceeds 30 MB')
    try:image=Image.open(io.BytesIO(data))
    except (OSError,ValueError):image=None
    if image is not None:
        fmt=image.format
        if fmt not in ('PNG','JPEG','GIF','WEBP','AVIF','BMP','TIFF'):raise ValueError('Unsupported image format')
        if image.width*image.height>16777216:raise ValueError('Image exceeds 16 megapixels')
        frames=getattr(image,'n_frames',1)
        if frames>600:raise ValueError('Animation exceeds 600 frames')
        if frames>1 and fmt!='GIF':raise ValueError('Animated non-GIF image requires explicit conversion; not flattened')
        # Validate every GIF frame while retaining the original animation bytes.
        for frame in range(frames):image.seek(frame);image.load()
        # Older Pillow TIFF decoders close their stream after load(). Reopen
        # for the poster pass instead of seeking on an exhausted decoder.
        result=image_result(Image.open(io.BytesIO(data)),fmt,fmt=='GIF' and frames>1)
    elif data[4:8]==b'ftyp' and data[8:12]==b'avif':
        run(['avifdec',str(SOURCE),str(ROOT/'decoded.png')],20)
        image=Image.open(ROOT/'decoded.png')
        if image.width*image.height>16777216:raise ValueError('Image exceeds 16 megapixels')
        result=image_result(image,'AVIF')
    elif b'<svg' in data[:4096].lower():
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('SVG entities forbidden')
        root=ET.fromstring(data)
        for node in root.iter():
            if node.tag.split('}')[-1] in ('script','foreignObject'):raise ValueError('Active SVG forbidden')
            for key,value in node.attrib.items():
                if key.split('}')[-1].lower().startswith('on'):raise ValueError('SVG handlers forbidden')
                if key.split('}')[-1]=='href' and not value.startswith('#'):raise ValueError('External SVG resource forbidden')
        if re.search(rb'url\(\s*[\x22\x27]?(?!#)',data,re.I):raise ValueError('SVG URL resources forbidden')
        import cairosvg
        # Explicit raster fallback, never claim the SVG stayed vector-editable.
        png=cairosvg.svg2png(bytestring=data,output_width=1920,unsafe=False)
        result=image_result(Image.open(io.BytesIO(png)),'SVG')
        result['conversion']='SVG raster fallback'
    else:
        info=probe(SOURCE);formats=set(info['format']['format_name'].split(','))
        allowed={'mov','mp4','m4a','3gp','3g2','mj2','matroska','webm','avi','mpeg','ogg','mp3','wav','flac','asf','aac'}
        if not formats&allowed:raise ValueError('Unsupported media container; playlists/documents/executables refused')
        duration=float(info['format'].get('duration',0))
        if not math.isfinite(duration) or not 0<duration<=120:raise ValueError('Clip must have known duration <=120 seconds')
        video=next((s for s in info['streams'] if s['codec_type']=='video'),None)
        if video and video.get('width',0)*video.get('height',0)>16777216:raise ValueError('Video frame too large')
        base=['ffmpeg','-v','error','-nostdin','-y','-protocol_whitelist','file,pipe','-threads','1','-i',str(SOURCE)]
        if video:
            name='media.mp4'
            run(base+['-map','0:v:0','-map','0:a:0?','-vf','scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2','-filter_threads','1','-c:v','libx264','-threads','1','-preset','veryfast','-pix_fmt','yuv420p','-crf','23','-maxrate','1500k','-bufsize','3000k','-c:a','aac','-b:a','96k','-movflags','+faststart','-fs',str(LIMIT),str(ROOT/name)])
            run(['ffmpeg','-v','error','-y','-i',str(ROOT/name),'-frames:v','1','-threads','1',str(ROOT/'poster.png')],20)
            result=dict(kind='video',file=name,poster='poster.png',conversion='H.264/AAC MP4')
        else:
            name='media.mp3';run(base+['-vn','-map','0:a:0','-c:a','libmp3lame','-b:a','128k','-threads','1','-fs',str(LIMIT),str(ROOT/name)])
            result=dict(kind='audio',file=name,conversion='MP3')
        checked=probe(ROOT/name)
        if abs(float(checked['format'].get('duration',0))-duration)>1:raise ValueError('Converted clip is incomplete')
        result.update(duration=duration,originalFormat=info['format']['format_name'])
    if (ROOT/result['file']).stat().st_size>LIMIT:raise ValueError('Output exceeds limit')
    result['playbackVerified']=False
    (ROOT/'result.json').write_text(json.dumps(result))

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(type(error).__name__+': '+str(error)[:200]);raise SystemExit(1)
