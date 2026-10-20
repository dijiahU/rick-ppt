"""Publish immutable native PPT previews/object locations; never render another deck."""
import hashlib,io,json,math,posixpath,time,zipfile,uuid
from pathlib import Path
from lxml import etree as ET
from progress import read_scoped

NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
IDENT=(1.,0.,0.,1.,0.,0.)
def multiply(a,b):
    x,y,z,w,e,f=a;u,v,s,t,g,h=b
    return (x*u+z*v,y*u+w*v,x*s+z*t,y*s+w*t,x*g+z*h+e,y*g+w*h+f)
def point(m,x,y):return (m[0]*x+m[2]*y+m[4],m[1]*x+m[3]*y+m[5])
def translate(x,y):return (1,0,0,1,x,y)
def scale(x,y):return (x,0,0,y,0,0)
def xml(data):
    if b'<!DOCTYPE' in data or b'<!ENTITY' in data:raise ValueError('XML declarations rejected')
    return ET.fromstring(data,ET.XMLParser(resolve_entities=False,no_network=True,load_dtd=False))
def tag(node):return ET.QName(node).localname if isinstance(node.tag,str) else ''
def native_pages(artifact):
    with zipfile.ZipFile(io.BytesIO(artifact)) as z:
        presentation=xml(z.read('ppt/presentation.xml'));rels=xml(z.read('ppt/_rels/presentation.xml.rels'))
        targets={r.get('Id'):posixpath.normpath(posixpath.join('ppt',r.get('Target',''))) if not r.get('Target','').startswith('/') else r.get('Target').lstrip('/') for r in rels if r.get('TargetMode')!='External'}
        size=presentation.find('p:sldSz',NS);width,height=int(size.get('cx')),int(size.get('cy'));pages=[]
        for n,slide in enumerate(presentation.findall('p:sldIdLst/p:sldId',NS),1):
            part=targets[slide.get('{'+NS['r']+'}id')];tree=xml(z.read(part));objects=[]
            def visit(node,parent=IDENT):
                kind=tag(node)
                if kind not in ('sp','pic','grpSp','cxnSp','graphicFrame'):
                    for child in node:visit(child,parent)
                    return
                nv=next((v for v in node if tag(v).startswith('nv')),None);prop=nv.find('p:cNvPr',NS) if nv is not None else None
                xfrm=node.find('p:spPr/a:xfrm',NS) if kind!='grpSp' else node.find('p:grpSpPr/a:xfrm',NS)
                if xfrm is None:xfrm=node.find('p:xfrm',NS)
                if xfrm is None:return  # Inherited geometry needs the layout; use region comments.
                off=xfrm.find('a:off',NS);ext=xfrm.find('a:ext',NS)
                if off is None or ext is None:return
                x,y,w,h=map(float,(off.get('x'),off.get('y'),ext.get('cx'),ext.get('cy')))
                if w<0 or h<0:return
                angle=float(xfrm.get('rot','0'))/60000*math.pi/180;rotation=(math.cos(angle),math.sin(angle),-math.sin(angle),math.cos(angle),0,0)
                frame=multiply(multiply(multiply(translate(x+w/2,y+h/2),rotation),scale(-1 if xfrm.get('flipH')=='1' else 1,-1 if xfrm.get('flipV')=='1' else 1)),translate(-w/2,-h/2));matrix=multiply(parent,frame)
                if kind=='grpSp':
                    ch=xfrm.find('a:chOff',NS);ce=xfrm.find('a:chExt',NS)
                    if ch is None or ce is None or float(ce.get('cx'))<=0 or float(ce.get('cy'))<=0:return
                    child_matrix=multiply(multiply(matrix,scale(w/float(ce.get('cx')),h/float(ce.get('cy')))),translate(-float(ch.get('x')),-float(ch.get('y'))))
                    for child in node:
                        if tag(child) in ('sp','pic','grpSp','cxnSp','graphicFrame'):visit(child,child_matrix)
                    return
                corners=[point(matrix,a,b) for a,b in ((0,0),(w,0),(0,h),(w,h))];x1=max(0,min(p[0] for p in corners)/width);y1=max(0,min(p[1] for p in corners)/height);x2=min(1,max(p[0] for p in corners)/width);y2=min(1,max(p[1] for p in corners)/height)
                if x2<=x1 or y2<=y1 or prop is None:return
                tx=node.find('p:txBody',NS);paragraphs=tx.findall('a:p',NS) if tx is not None else []
                text='\n'.join(''.join(t.text or '' for t in p.iter('{'+NS['a']+'}t')) for p in paragraphs)
                if not text:text=' '.join(t.text or '' for t in node.iter('{'+NS['a']+'}t'))
                editable=kind=='sp' and tx is not None and not node.findall('.//a:fld',NS) and not any(tag(v) in ('oMath','oMathPara') for v in node.iter()) and len(text)<=3000
                objects.append({'id':prop.get('id'),'name':prop.get('name','')[:300],'kind':kind,'text':text[:12000],'textEditable':bool(editable),'bounds':{'x':x1,'y':y1,'width':x2-x1,'height':y2-y1}})
            visit(tree)
            title=next((o['text'].split('\n')[0] for o in objects if o['text']),f'Slide {n}')
            pages.append({'number':n,'part':part,'title':title[:240],'width':width,'height':height,'objects':objects})
        return pages

def collect(job,artifact,lease):
    job=Path(job).resolve();digest=hashlib.sha256(artifact).hexdigest();state=None
    for path in job.rglob('state.json'):
        if not (path.parent/'workspace/ppt/presentation.xml').is_file():continue
        try:
            candidate=json.loads(read_scoped(job,path,8*1024*1024));output=Path(candidate.get('latest_output',''))
            if not output.is_absolute():output=job/output
            if hashlib.sha256(read_scoped(job,output,30*1024*1024)).hexdigest()!=digest:continue
            if candidate.get('last_compatibility',{}).get('artifact_sha256') not in (None,digest):continue
            state=candidate;break
        except (ValueError,OSError,KeyError):continue
    if not state or not state.get('last_render'):raise ValueError('No export-matched native render for this artifact')
    pages=native_pages(artifact);images=state['last_render']['pages']
    if len(images)!=len(pages):raise ValueError('Native render page count differs from artifact')
    pngs=[]
    for page,path in zip(pages,images):
        body=read_scoped(job,Path(path),2*1024*1024)
        if not body.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Canvas preview must be PNG')
        page['imageSha256']=hashlib.sha256(body).hexdigest();pngs.append(body)
    return {'schema':'rickppt-canvas/v1','sha256':digest,'versionId':str(uuid.uuid5(uuid.NAMESPACE_URL,'rickppt-canvas:'+digest)),'createdAt':int(time.time()*1000),'pages':pages},pngs

def publish(cfg,task,job,artifact,send,rendered=None):
    if rendered:
        from render_inputs import source_parts_sha256
        digest=hashlib.sha256(artifact).hexdigest();environment=rendered.get('environment',{})
        if rendered.get('source_hash')!=digest and environment.get('source_parts_sha256')!=source_parts_sha256(artifact):raise ValueError('Final canvas render does not match the reviewed artifact')
        pages=native_pages(artifact);images=[]
        if len(pages)!=len(rendered['pages']):raise ValueError('Final canvas page count differs')
        for page,path in zip(pages,rendered['pages']):
            path=Path(path);data=read_scoped(path.parent,path.name,2*1024*1024)
            if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('PNG required')
            page['imageSha256']=hashlib.sha256(data).hexdigest();images.append(data)
        snapshot={'schema':'rickppt-canvas/v1','sha256':digest,'versionId':str(uuid.uuid5(uuid.NAMESPACE_URL,'rickppt-canvas:'+digest)),'createdAt':int(time.time()*1000),'pages':pages}
    else:snapshot,images=collect(job,artifact,task['lease'])
    base=f'/api/worker/{task["id"]}/canvas?sha256={snapshot["sha256"]}'
    from concurrent.futures import ThreadPoolExecutor
    def upload(entry):
        n,body=entry;send(cfg,base+f'&action=page&page={n}',body,task['lease'])
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(upload,enumerate(images,1)))
    send(cfg,base+'&action=manifest',json.dumps(snapshot,separators=(',',':'),ensure_ascii=False).encode(),task['lease'])
    return {'sha256':snapshot['sha256'],'pages':len(images)}

def scoped_requests(journal,job):
    """Only explicit, verified canvas revisions may reuse existing planning."""
    if journal is None:return None
    pending=[m for m in journal.state['inbox'].values() if m['changes_input'] and m['state']!='applied']
    if not pending:return None
    result=[]
    for message in pending:
        marker='[RICKPPT_VISUAL_EDITS_V1]\n'
        if marker not in message['text']:return None
        try:
            request=json.loads(message['text'].split(marker,1)[1].split('\n',1)[0])
            if request.get('schema')!='rickppt-visual-edits/v1' or request.get('scope')!='selected_objects_and_pages' or not request.get('changes'):return None
            source=read_scoped(Path(job),f'visual-inputs/{message["id"]}/baseline.pptx',30*1024*1024)
            if hashlib.sha256(source).hexdigest()!=request['baseSha256']:raise ValueError('Visual request baseline changed')
            result.append(request)
        except (ValueError,KeyError,IndexError,OSError):return None
    return result
