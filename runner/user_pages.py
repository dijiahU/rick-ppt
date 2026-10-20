"""Preserve user-owned finished pages while the author builds later pages."""
import hashlib,io,json,posixpath,zipfile
from urllib.parse import urlsplit
from lxml import etree as E
from office_policy import archive,validate_delivery,xml
from canvas_snapshot import native_pages
from draft_progress import _target

CT='http://schemas.openxmlformats.org/package/2006/content-types'
def relpart(part):return posixpath.join(posixpath.dirname(part),'_rels',posixpath.basename(part)+'.rels')
def fingerprint(data,page):
    """Page/resource identity independent of harmless OPC dependency relocation."""
    with archive(data) as z:
        pages=native_pages(data);slides={p['part']:i+1 for i,p in enumerate(pages)};names=set(z.namelist());cache={}
        def part_hash(part,stack):
            if part in cache:return cache[part]
            raw=z.read(part);body=hashlib.sha256(raw).hexdigest()
            if part in stack:return 'cycle:'+body
            h=hashlib.sha256(b'rickppt-page-resource-v2\0'+body.encode());rp=relpart(part)
            if rp in names:
                for rel in sorted(xml(z.read(rp)),key=lambda n:n.get('Id','')):
                    mode=rel.get('TargetMode','Internal');target=rel.get('Target','')
                    if mode!='External':
                        target=_target(part,target);target='slide:'+str(slides[target]) if target in slides else part_hash(target,stack|{part})
                    h.update(json.dumps([rel.get('Id'),rel.get('Type'),mode,target],separators=(',',':')).encode())
            cache[part]=h.hexdigest();return cache[part]
        h=hashlib.sha256(b'rickppt-page-parts-v2\0'+part_hash(pages[page-1]['part'],set()).encode())
        if 'ppt/tableStyles.xml' in names:h.update(hashlib.sha256(z.read('ppt/tableStyles.xml')).digest())
        return h.hexdigest()

def graft(candidate,overlays):
    """Copy protected slide parts and their OPC dependency closures, never later pages."""
    if not overlays:return candidate
    validate_delivery(candidate,single_file=True)
    with archive(candidate) as z:parts={n:z.read(n) for n in z.namelist()}
    pages=native_pages(candidate);types=xml(parts['[Content_Types].xml']);overrides={n.get('PartName'):n for n in types if n.tag=='{'+CT+'}Override'};defaults={n.get('Extension'):n for n in types if n.tag=='{'+CT+'}Default'}
    for overlay in overlays:
        source=overlay['artifact'];validate_delivery(source,single_file=True);source_pages=native_pages(source);sha=hashlib.sha256(source).hexdigest()
        with archive(source) as z:original={n:z.read(n) for n in z.namelist()}
        source_types=xml(original['[Content_Types].xml']);source_overrides={n.get('PartName','').lstrip('/'):n.get('ContentType') for n in source_types if n.tag=='{'+CT+'}Override'}
        for n in source_types:
            if n.tag=='{'+CT+'}Default' and n.get('Extension') not in defaults:
                copied=E.SubElement(types,'{'+CT+'}Default',**dict(n.attrib));defaults[n.get('Extension')]=copied
        slide_map={p['part']:pages[i]['part'] for i,p in enumerate(source_pages) if i<len(pages)}
        all_slides={p['part'] for p in source_pages};mapped={};copied=set()
        for number in overlay['pages']:
            if not 1<=number<=len(pages) or number>len(source_pages) or pages[number-1]['part']!=source_pages[number-1]['part']:raise ValueError('A protected page changed its presentation identity; explicit reconciliation is required')
            mapped[source_pages[number-1]['part']]=pages[number-1]['part']
        def destination(part):
            if part in all_slides:
                if part not in slide_map:raise ValueError('Protected navigation points to an unavailable slide')
                return slide_map[part]
            if part in parts and parts[part]==original[part] and parts.get(relpart(part))==original.get(relpart(part)):return part
            return mapped.setdefault(part,'ppt/user-edits/'+sha[:20]+'/'+hashlib.sha256(part.encode()).hexdigest()[:12]+'-'+posixpath.basename(part))
        def copy_part(part):
            if part in copied:return
            copied.add(part);dest=destination(part);parts[dest]=original[part]
            content_type=source_overrides.get(part)
            if content_type=='application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml' and dest!=part:
                presentation=xml(parts['ppt/presentation.xml']);presentation_rels=xml(parts['ppt/_rels/presentation.xml.rels']);rel_id='rIdUserMaster'+hashlib.sha256(dest.encode()).hexdigest()[:16]
                if not any(n.get('Id')==rel_id for n in presentation_rels):
                    R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';P='http://schemas.openxmlformats.org/presentationml/2006/main';REL='http://schemas.openxmlformats.org/package/2006/relationships'
                    E.SubElement(presentation_rels,'{'+REL+'}Relationship',Id=rel_id,Type=R+'/slideMaster',Target=posixpath.relpath(dest,'ppt'));listing=presentation.find('{'+P+'}sldMasterIdLst')
                    if listing is None:listing=E.Element('{'+P+'}sldMasterIdLst');presentation.insert(0,listing)
                    number=max([int(n.get('id','2147483647')) for n in listing]+[2147483647])+1;E.SubElement(listing,'{'+P+'}sldMasterId',id=str(number),attrib={'{'+R+'}id':rel_id});parts['ppt/presentation.xml']=E.tostring(presentation,xml_declaration=True,encoding='UTF-8',standalone=True);parts['ppt/_rels/presentation.xml.rels']=E.tostring(presentation_rels,xml_declaration=True,encoding='UTF-8',standalone=True)
            if content_type:
                key='/'+dest
                if key in overrides:overrides[key].set('ContentType',content_type)
                else:overrides[key]=E.SubElement(types,'{'+CT+'}Override',PartName=key,ContentType=content_type)
            rp=relpart(part)
            if rp not in original:return
            rels=xml(original[rp])
            for rel in rels:
                if rel.get('TargetMode')=='External':continue
                raw=rel.get('Target');target=_target(part,raw);target_dest=destination(target)
                rel.set('Target',posixpath.relpath(target_dest,posixpath.dirname(dest))+('#'+urlsplit(raw).fragment if urlsplit(raw).fragment else ''))
                if target not in all_slides:copy_part(target)
            parts[relpart(dest)]=E.tostring(rels,xml_declaration=True,encoding='UTF-8',standalone=True)
        for number in overlay['pages']:copy_part(source_pages[number-1]['part'])
    parts['[Content_Types].xml']=E.tostring(types,xml_declaration=True,encoding='UTF-8',standalone=True);out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for part,data in parts.items():
            item=zipfile.ZipInfo(part,date_time=(1980,1,1,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED;z.writestr(item,data)
    result=out.getvalue();validate_delivery(result,single_file=True);return result

def load(cfg,task,send,*,images=False):
    base=f'/api/worker/{task["id"]}/canvas?sha256='+('0'*64)
    state=send(cfg,base+'&action=locks',b'{}',task['lease']);groups={}
    class Locks(list):pass
    locks=Locks(state.get('locks',[]));locks.head_sha=(state.get('head') or {}).get('sha256','')
    for lock in locks:
        sha=lock['sha256']
        if sha not in groups:
            artifact=send(cfg,f'/api/worker/{task["id"]}/canvas?sha256={sha}&action=source&locked=1',b'{}',task['lease'],raw=True)
            if hashlib.sha256(artifact).hexdigest()!=sha:raise ValueError('Protected source checksum differs')
            groups[sha]={'artifact':artifact,'pages':[]}
        groups[sha]['pages'].append(lock['page'])
        if images:lock['png']=send(cfg,f'/api/worker/{task["id"]}/canvas?sha256={sha}&action=lock-image&page={lock["page"]}',b'{}',task['lease'],raw=True)
    return list(groups.values()),locks
