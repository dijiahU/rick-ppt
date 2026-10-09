"""Freeze task-scoped render bytes and extract requested font names as data."""
import hashlib
import io
import zipfile
import subprocess
import os
import uuid
import xml.etree.ElementTree as ET
from progress import read_scoped

def render_input(job,source):
    data=read_scoped(job,source.relative_to(job),30*1024*1024)
    fonts=set();expanded=0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for item in archive.infolist():
            if not item.filename.startswith('ppt/') or not item.filename.endswith('.xml'):continue
            expanded+=item.file_size
            if expanded>100*1024*1024 or item.file_size>8*1024*1024:raise ValueError('Render XML size limit exceeded')
            blob=archive.read(item)
            if b'<!DOCTYPE' in blob.upper() or b'<!ENTITY' in blob.upper():raise ValueError('Render XML entities forbidden')
            tree=ET.fromstring(blob)
            for element in tree.iter():
                font=element.get('typeface')
                if font and not font.startswith('+') and len(font)<=128 and not any(ord(c)<32 for c in font):fonts.add(font)
    return data,{'source_sha256':hashlib.sha256(data).hexdigest(),'requested_fonts':sorted(fonts)[:64],
                 'renderer_image':'pptx-lab-renderer:1','measurement_environment':'Host installed-font estimates; production uses container fonts',
                 'font_diagnostic_scope':'Fontconfig family candidates; per-glyph fallback and PowerPoint fonts may differ',
                 'powerpoint_playback_verified':False}

def renderer_font_catalog():
    command=['/usr/local/bin/docker','run','--rm','--network','none','--read-only','--cap-drop','ALL',
             '--security-opt','no-new-privileges','--entrypoint','fc-list','pptx-lab-renderer:1',':','family']
    result=subprocess.run(command,capture_output=True,text=True,timeout=30,check=True)
    families=sorted({x.strip() for line in result.stdout.splitlines() for x in line.split(',') if x.strip()})
    if not families or len(families)>500:raise ValueError('Invalid production font catalog')
    return {'image':'pptx-lab-renderer:1','families':families,'scope':'Available renderer families, not PowerPoint installation or glyph-coverage proof'}

def publish_pdf(job,destination,name,data):
    if '/' in name or not name.endswith('.pdf'):raise ValueError('Invalid rendered filename')
    fd=os.open(job,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    pending='.render-'+uuid.uuid4().hex+'.pending'
    try:
        for part in destination.relative_to(job).parts:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=child
        child=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
        with os.fdopen(child,'wb') as stream:stream.write(data)
        os.replace(pending,name,src_dir_fd=fd,dst_dir_fd=fd)
    finally:
        try:os.unlink(pending,dir_fd=fd)
        except FileNotFoundError:pass
        os.close(fd)
