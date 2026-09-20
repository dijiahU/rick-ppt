"""Best-effort background upload of the latest complete, task-scoped PPTX export.

Draft availability is not independent-review approval. No source/workspace is
packed here and no original, export, or failed candidate is modified or deleted.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import threading
import time
from urllib.parse import unquote, urlsplit

from office_policy import archive, validate_delivery, xml
from outline import MAX_SLIDES


MAX_BYTES = 30 * 1024 * 1024
MAX_ENTRIES = 20000
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
PRESENTATION_TYPE = 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'


def _parts(value):
    if (not isinstance(value, str) or not value or value.startswith('/') or
            any(c in value for c in ('\\', '\x00')) or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError('Unsafe draft path')
    return tuple(value.split('/'))


def _directory(root, parts=()):
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        return fd
    except BaseException:
        os.close(fd); raise


def _read(root, relative, limit):
    parts = _parts(relative)
    parent = _directory(root, parts[:-1])
    try:
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= limit:
                raise ValueError('Unsafe or oversized draft file')
            data = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            signature = lambda item: (item.st_dev,item.st_ino,item.st_size,item.st_mtime_ns,item.st_ctime_ns)
            if len(data) > limit or len(data) != before.st_size or signature(before) != signature(after):
                raise ValueError('Draft file changed while reading')
            return data, after
    finally:
        os.close(parent)


def _target(owner, target):
    if not isinstance(target, str) or not target or '\\' in target or '\x00' in target:
        raise ValueError('Invalid native relationship target')
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.query:
        raise ValueError('Invalid internal native relationship')
    path = unquote(parsed.path)
    if '\\' in path or '\x00' in path:
        raise ValueError('Invalid escaped native relationship')
    resolved = posixpath.normpath(path.lstrip('/') if path.startswith('/') else posixpath.join(posixpath.dirname(owner),path))
    if resolved in ('', '.', '..') or resolved.startswith('../'):
        raise ValueError('Native relationship escapes package')
    return resolved


def validate_native(data):
    """Check complete ZIP/XML/OPC links and actual slide count, without rendering."""
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES:
        raise ValueError('Draft exceeds the PPTX upload limit')
    validate_delivery(data)
    with archive(data) as package:
        names = set(package.namelist())
        if not {'[Content_Types].xml','_rels/.rels','ppt/presentation.xml','ppt/_rels/presentation.xml.rels'} <= names:
            raise ValueError('Incomplete native presentation')
        trees = {}
        for name in names:
            if name.endswith('/'):
                continue
            body = package.read(name)  # Read every part: truncated bytes/CRC fail here.
            if name.endswith(('.xml','.rels')):
                trees[name] = xml(body)
        types = trees['[Content_Types].xml']
        if types.tag != '{'+CT+'}Types':
            raise ValueError('Invalid native content types')
        defaults, overrides = {}, {}
        for node in types:
            if node.tag == '{'+CT+'}Default':
                key=node.get('Extension','').lower();target=defaults
            elif node.tag == '{'+CT+'}Override':
                raw=node.get('PartName','')
                if not raw.startswith('/'):raise ValueError('Invalid content type override')
                key=raw[1:];target=overrides
                if key not in names:raise ValueError('Missing content type part')
            else:raise ValueError('Invalid content type entry')
            if not key or key in target or not node.get('ContentType'):raise ValueError('Duplicate or empty content type')
            target[key]=node.get('ContentType')
        if overrides.get('ppt/presentation.xml') != PRESENTATION_TYPE:
            raise ValueError('Draft must be a native, non-macro PowerPoint presentation')
        for name in names:
            if name.endswith('/') or name == '[Content_Types].xml':continue
            if name not in overrides and name.rsplit('.',1)[-1].lower() not in defaults:
                raise ValueError('Missing native part content type')
        relationships = {}
        for name, tree in trees.items():
            if not name.endswith('.rels'):continue
            if tree.tag != '{'+REL+'}Relationships':raise ValueError('Invalid relationship XML')
            if name == '_rels/.rels':owner=''
            else:
                path=PurePosixPath(name)
                if path.parent.name != '_rels':raise ValueError('Invalid relationship part path')
                owner=(path.parent.parent/path.name[:-5]).as_posix()
                if owner not in names:raise ValueError('Missing relationship owner')
            items={}
            for node in tree:
                identifier=node.get('Id');kind=node.get('Type','');mode=node.get('TargetMode','Internal')
                if (node.tag!='{'+REL+'}Relationship' or not identifier or identifier in items or
                        not kind or mode not in ('Internal','External')):
                    raise ValueError('Invalid native relationship entry')
                target=node.get('Target')
                if mode=='Internal':
                    target=_target(owner,target)
                    if target not in names:raise ValueError('Broken internal native relationship')
                elif not target:raise ValueError('Empty external relationship')
                items[identifier]=(kind,target,mode)
            relationships[owner]=items
        office=[entry for entry in relationships[''].values() if entry[0]==R+'/officeDocument']
        if office != [(R+'/officeDocument','ppt/presentation.xml','Internal')]:
            raise ValueError('Invalid native presentation root')
        presentation=trees['ppt/presentation.xml']
        if presentation.tag!='{'+P+'}presentation':raise ValueError('Invalid native presentation XML')
        slides=presentation.find('{'+P+'}sldIdLst')
        if slides is None or not 1<=len(slides)<=MAX_SLIDES:
            raise ValueError('Invalid draft slide count')
        identifiers=set();targets=set()
        for slide in slides:
            identifier=slide.get('id','');rid=slide.get('{'+R+'}id')
            entry=relationships['ppt/presentation.xml'].get(rid)
            if (slide.tag!='{'+P+'}sldId' or not identifier.isdecimal() or not 256<=int(identifier)<2**31 or
                    identifier in identifiers or not entry or entry[0]!=R+'/slide' or entry[2]!='Internal' or
                    entry[1] in targets or trees.get(entry[1]) is None or trees[entry[1]].tag!='{'+P+'}sld'):
                raise ValueError('Invalid or missing native slide')
            identifiers.add(identifier);targets.add(entry[1])
        return len(slides)


class DraftProgress:
    def __init__(self, cfg, task, job, send, *, clock=time.monotonic):
        self.cfg,self.task,self.root,self.send,self.clock=cfg,task,Path(job),send,clock
        self.next_poll=0.0;self.thread=None;self.lock=threading.Lock()
        self.uploaded=set();self.latest=None;self.last_error=None

    def context(self):
        revision=self.task.get('input_revision',self.task.get('revision',0))
        if type(revision) is not int or revision<0:revision=0
        aliases={self.root.resolve()}
        task_id=self.task.get('id','')
        if not isinstance(task_id,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',task_id):
            raise ValueError('Invalid task identity')
        state_root=Path(self.cfg.get('state_directory',Path(__file__).parent/'state')).resolve()
        # A model-writable file must never authorize an old absolute path.
        if state_root==self.root.resolve() or state_root.is_relative_to(self.root.resolve()):
            raise ValueError('Draft context must be host-owned')
        try:
            raw,_=_read(state_root,task_id+'/state.json',32*1024*1024)
            state=json.loads(raw)['state']
            if state.get('task_id')!=task_id:raise ValueError('Draft journal task mismatch')
            if type(state.get('input_revision')) is not int or state['input_revision']<0:
                raise ValueError('Invalid draft journal revision')
            revision=state['input_revision']
            for recovery in state.get('recoveries',{}).values():
                for key in ('previous_workspace','workspace'):
                    path=recovery.get(key)
                    if isinstance(path,str) and Path(path).is_absolute():aliases.add(Path(path))
        except FileNotFoundError:
            pass
        return revision,aliases

    def candidates(self, aliases):
        paths={};visited=0
        def walk(parts,depth=0):
            nonlocal visited
            if depth>32:return
            try:fd=_directory(self.root,parts)
            except OSError:return
            try:
                for name in sorted(os.listdir(fd)):
                    visited+=1
                    if visited>MAX_ENTRIES:raise ValueError('Draft scan limit exceeded')
                    if name.startswith('.'):continue  # Never publish .pptx-export-*/candidate.pptx.
                    try:info=os.stat(name,dir_fd=fd,follow_symlinks=False)
                    except OSError:continue
                    child=parts+(name,)
                    if stat.S_ISDIR(info.st_mode):walk(child,depth+1)
                    elif stat.S_ISREG(info.st_mode) and name.lower().endswith('.pptx'):
                        paths['/'.join(child)]=info.st_mtime_ns
            finally:os.close(fd)
        walk(('exports',))
        try:
            fd=_directory(self.root,('.pptx-agent',))
            try:homes=sorted(os.listdir(fd))
            finally:os.close(fd)
        except OSError:homes=[]
        for home in homes[:MAX_ENTRIES]:walk(('.pptx-agent',home,'exports'))
        try:
            raw,_=_read(self.root,'delivery.json',65536)
            value=json.loads(raw).get('path')
            if not isinstance(value,str):raise ValueError('Invalid delivery path')
            source=Path(value)
            if source.is_absolute():
                matched=[root for root in aliases if source.is_relative_to(root)]
                if not matched:raise ValueError('Delivery path outside task')
                source=source.relative_to(max(matched,key=lambda root:len(root.parts)))
            relative=source.as_posix();parts=_parts(relative)
            if source.suffix.lower()!='.pptx':raise ValueError('Delivery must be a PPTX')
            parent=_directory(self.root,parts[:-1])
            try:info=os.stat(parts[-1],dir_fd=parent,follow_symlinks=False)
            finally:os.close(parent)
            if stat.S_ISREG(info.st_mode):paths[relative]=info.st_mtime_ns
        except (OSError,ValueError,TypeError,AttributeError):
            pass
        return sorted(paths,key=lambda name:(paths[name],name),reverse=True)

    def synchronize(self):
        """One bounded attempt; called on a background thread by poll()."""
        try:
            revision,aliases=self.context()
            for relative in self.candidates(aliases):
                try:
                    data,info=_read(self.root,relative,MAX_BYTES)
                    exported_at=info.st_mtime_ns//1_000_000
                    if not 0<exported_at<=int(time.time()*1000)+60000:raise ValueError('Invalid export timestamp')
                    sha=hashlib.sha256(data).hexdigest()
                    if sha in self.uploaded:return
                    if self.latest and info.st_mtime_ns<self.latest['exportedNs']:return
                    pages=validate_native(data)
                except Exception as error:
                    # An incomplete/newer export must not hide an older valid one.
                    self.last_error=type(error).__name__
                    continue
                query=f'?sha256={sha}&pages={pages}&revision={revision}&exportedAt={exported_at}'
                response=self.send(self.cfg,f'/api/worker/{self.task["id"]}/draft'+query,data,self.task['lease'])
                if not isinstance(response,dict) or response.get('ok') is not True:
                    raise ValueError('Draft upload was not acknowledged')
                self.uploaded.add(sha)
                self.latest={'sha256':sha,'pages':pages,'revision':revision,'exportedAt':exported_at,'exportedNs':info.st_mtime_ns}
                self.last_error=None
                return
        except Exception as error:
            self.last_error=type(error).__name__  # No paths, response bodies or credentials.

    def poll(self, *, force=False):
        with self.lock:
            now=self.clock()
            if self.thread is not None and self.thread.is_alive():return
            if not force and now<self.next_poll:return
            self.next_poll=now+15
            self.thread=threading.Thread(target=self.synchronize,name='pptx-draft-progress',daemon=True)
            self.thread.start()

    def finish(self, timeout=2):
        self.poll(force=True)
        thread=self.thread
        if thread is not None:thread.join(timeout=max(0,min(float(timeout),5)))
