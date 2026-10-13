"""Freeze task-scoped render bytes and extract requested font names as data."""
import hashlib
import io
import zipfile
import subprocess
import os
import re
import stat
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from progress import read_scoped


def source_parts_sha256(data):
    """Identity of all actual package parts, excluding ZIP container metadata.

    XML/media/relationships are compared as exact bytes. No XML normalization,
    external reads or execution occurs. Timestamps, compression and ZIP order
    can change when a verified workspace is repacked without changing its parts.
    """
    digest=hashlib.sha256(b'pptx-render-parts-v1\0')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries=archive.infolist()
        if len(entries)>50000 or sum(x.file_size for x in entries)>2*1024**3:
            raise ValueError('Render source package exceeds native extraction limits')
        files={};seen=set()
        for entry in entries:
            name=entry.filename;path=PurePosixPath(name);mode=entry.external_attr>>16
            if (not name or path.is_absolute() or '..' in path.parts or '\\' in name
                    or ':' in name or '\0' in name or stat.S_ISLNK(mode)
                    or str(path).casefold() in seen or entry.flag_bits&1):
                raise ValueError('Unsafe or duplicate render source part')
            seen.add(str(path).casefold())
            if not entry.is_dir():files[name]=entry
        if not {'[Content_Types].xml','ppt/presentation.xml'}.issubset(files):
            raise ValueError('Render source is not a PowerPoint package')
        for name in sorted(files):
            entry=files[name];encoded=name.encode('utf-8')
            part=hashlib.sha256();size=0
            with archive.open(entry) as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):
                    size+=len(chunk)
                    if size>entry.file_size:raise ValueError('Render source part size changed')
                    part.update(chunk)
            if size!=entry.file_size:raise ValueError('Render source part is incomplete')
            digest.update(len(encoded).to_bytes(8,'big'));digest.update(encoded)
            digest.update(size.to_bytes(8,'big'));digest.update(part.digest())
    return digest.hexdigest()


def render_source_resolver(task_trajectory_roots):
    """Resolve a raw source hash using verified host-private render-input bytes.

    Only the specified task's archived inputs are read. Never trust a semantic
    identity asserted by a model-written render environment. Missing evidence
    returns None, leaving the original raw hash significant for review reuse.
    """
    roots=[Path(root).resolve(strict=True) for root in task_trajectory_roots]
    inspected={};identities={};evidence={}
    def resolve(raw_sha256):
        if not isinstance(raw_sha256,str) or not re.fullmatch('[0-9a-f]{64}',raw_sha256):return None
        if raw_sha256 in identities:
            root,relative=evidence[raw_sha256]
            try:
                data=read_scoped(root,relative,30*1024*1024)
                if hashlib.sha256(data).hexdigest()==raw_sha256:return identities[raw_sha256]
            except (OSError,ValueError):pass
            identities.pop(raw_sha256,None);evidence.pop(raw_sha256,None)
        for root in roots:
            for path in root.glob('*/artifacts/render-input/*.pptx'):
                try:
                    info=path.stat(follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode) or info.st_size>30*1024*1024:continue
                    key=(str(path),info.st_size,info.st_mtime_ns)
                    if key not in inspected:
                        data=read_scoped(root,path.relative_to(root),30*1024*1024)
                        actual=hashlib.sha256(data).hexdigest();inspected[key]=actual
                        if actual==raw_sha256:
                            identities[actual]=source_parts_sha256(data)
                            evidence[actual]=(root,path.relative_to(root))
                    if inspected[key]==raw_sha256:
                        if raw_sha256 not in identities:
                            data=read_scoped(root,path.relative_to(root),30*1024*1024)
                            if hashlib.sha256(data).hexdigest()!=raw_sha256:continue
                            identities[raw_sha256]=source_parts_sha256(data)
                            evidence[raw_sha256]=(root,path.relative_to(root))
                        return identities[raw_sha256]
                except (OSError,ValueError,zipfile.BadZipFile):continue
        return None
    return resolve

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
    return data,{'source_sha256':hashlib.sha256(data).hexdigest(),
                 'source_parts_sha256':source_parts_sha256(data),'requested_fonts':sorted(fonts)[:64],
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
