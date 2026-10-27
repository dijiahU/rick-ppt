"""Deterministic scoped OOXML editing. No model, template rebuild or quota use."""
import copy,difflib,hashlib,io,json,math,posixpath,zipfile
from lxml import etree as E
from canvas_snapshot import NS,native_pages,tag,xml
from office_policy import archive,validate_delivery

A=NS['a'];P=NS['p'];R=NS['r'];REL='http://schemas.openxmlformats.org/package/2006/relationships'
def child(node,name):return node.find(name,NS)
def ensure(node,name):
    found=child(node,name)
    if found is not None:return found
    found=E.Element('{'+NS[name.split(':')[0]]+'}'+name.split(':')[1]);extension=child(node,'a:extLst')
    if extension is not None:node.insert(node.index(extension),found)
    else:node.append(found)
    return found
def xfrm(node):
    found=child(node,'p:spPr/a:xfrm')
    return found if found is not None else child(node,'p:xfrm')
def identity(node):
    nv=next((n for n in node if tag(n).startswith('nv')),None)
    return child(nv,'p:cNvPr') if nv is not None else None
def text_body(node):
    tx=child(node,'p:txBody')
    return tx if tx is not None else child(node,'a:txBody')
def simple_text(tx):return tx is not None and not any(tag(n) in ('oMath','oMathPara','fld') for n in tx.iter())
def content(tx):return '\n'.join(''.join(n.text or '' for n in p.iter('{'+A+'}t')) for p in tx.findall('a:p',NS))
def replace_text(tx,value):
    """Retain matched characters' run formatting, paragraph styles and hyperlinks."""
    if not simple_text(tx):raise ValueError('Complex text must be edited with a comment')
    original=tx.findall('a:p',NS);values=value.split('\n')
    for index,value in enumerate(values):
        template=original[min(index,len(original)-1)] if original else E.Element('{'+A+'}p')
        p=copy.deepcopy(template);old='';styles=[]
        for run in template:
            if tag(run)=='r':
                t=child(run,'a:t');part=t.text or '' if t is not None else '';style=child(run,'a:rPr');old+=part;styles.extend([style]*len(part))
            elif tag(run)=='br':old+='\n';styles.append(None)
        default=next((s for s in styles if s is not None),None);assigned=[default]*len(value)
        for op,a,b,c,d in difflib.SequenceMatcher(None,old,value,autojunk=False).get_opcodes():
            if op=='equal':assigned[c:d]=styles[a:b]
            elif op in ('replace','insert'):
                style=styles[min(a,len(styles)-1)] if styles else default;assigned[c:d]=[style]*(d-c)
        for n in list(p):
            if tag(n) not in ('pPr','endParaRPr'):p.remove(n)
        at=len(p)-(1 if child(p,'a:endParaRPr') is not None else 0);start=0
        while start<len(value):
            end=start+1
            while end<len(value) and assigned[end] is assigned[start]:end+=1
            run=E.Element('{'+A+'}r')
            if assigned[start] is not None:run.append(copy.deepcopy(assigned[start]))
            t=E.SubElement(run,'{'+A+'}t');t.text=value[start:end];t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');p.insert(at,run);at+=1;start=end
        if not value:E.SubElement(E.SubElement(p,'{'+A+'}r'),'{'+A+'}t').text=''
        if index<len(original):tx.replace(original[index],p)
        else:tx.append(p)
    for p in original[len(values):]:tx.remove(p)
def set_fill(node,value,opacity=None):
    for n in list(node):
        if tag(n) in ('noFill','solidFill','gradFill','blipFill','pattFill','grpFill'):node.remove(n)
    fill=E.Element('{'+A+'}'+('noFill' if value=='none' else 'solidFill'))
    if value!='none':
        color=E.SubElement(fill,'{'+A+'}srgbClr',val=value.upper())
        if opacity is not None:E.SubElement(color,'{'+A+'}alpha',val=str(round(opacity*100000)))
    # DrawingML shape ordering: transform, geometry, fill, line, effects.
    insertion=next((i for i,n in enumerate(node) if tag(n) in ('ln','effectLst','effectDag','highlight','uLnTx','uLn','uFillTx','uFill','latin','ea','cs','sym','hlinkClick','hlinkMouseOver','rtl','scene3d','sp3d','extLst')),len(node));node.insert(insertion,fill)
def axis_parent(node):
    for parent in node.iterancestors():
        if tag(parent)=='grpSp':
            xf=child(parent,'p:grpSpPr/a:xfrm')
            if xf is None or int(xf.get('rot','0'))%21600000 or xf.get('flipH')=='1' or xf.get('flipV')=='1':return False
    return True
def connected(tree,identifier):return any(n.get('id')==identifier for n in tree.iter() if tag(n) in ('stCxn','endCxn'))
def referenced(tree,identifier):return connected(tree,identifier) or any(n.get('spid')==identifier for n in tree.iter())
def set_geometry(node,patch,page):
    xf=xfrm(node)
    if xf is None or not axis_parent(node):raise ValueError('Inherited or rotated group geometry requires a scoped comment')
    # Keep native connector bindings safe: arbitrary custom sites need a geometry author.
    if tag(node)=='cxnSp':raise ValueError('Use a comment to reshape this anchored connector')
    if 'box' in patch:
        if connected(node.getroottree().getroot(),identity(node).get('id')):raise ValueError('This object has anchored arrows; use a scoped comment to move it safely')
        b=patch['box'];xx=b['x']*page['width'];yy=b['y']*page['height'];ww=b['width']*page['width'];hh=b['height']*page['height']
        # Invert axis-aligned ancestor transforms from the outermost group inward.
        for parent in reversed(list(node.iterancestors())):
            if tag(parent)!='grpSp':continue
            p=child(parent,'p:grpSpPr/a:xfrm');off=child(p,'a:off');ext=child(p,'a:ext');ch=child(p,'a:chOff');ce=child(p,'a:chExt')
            sx=float(ext.get('cx'))/float(ce.get('cx'));sy=float(ext.get('cy'))/float(ce.get('cy'))
            xx=(xx-float(off.get('x')))/sx+float(ch.get('x'));yy=(yy-float(off.get('y')))/sy+float(ch.get('y'));ww/=sx;hh/=sy
        off=ensure(xf,'a:off');ext=ensure(xf,'a:ext');off.set('x',str(round(xx)));off.set('y',str(round(yy)));ext.set('cx',str(max(1,round(ww))));ext.set('cy',str(max(1,round(hh))))
    if 'rotation' in patch:
        if connected(node.getroottree().getroot(),identity(node).get('id')):raise ValueError('Rotating a connected node requires a scoped comment')
        xf.set('rot',str(round((patch['rotation']%360)*60000)))
def style_text(tx,patch):
    fields=set(patch)&{'fontFace','fontSize','fontColor','bold','italic','underline','align','valign'}
    if not fields:return
    if not simple_text(tx):raise ValueError('Complex text formatting requires a scoped comment')
    if 'valign' in patch:ensure(tx,'a:bodyPr').set('anchor',patch['valign'])
    for p in tx.findall('a:p',NS):
        ppr=child(p,'a:pPr')
        if ppr is None:ppr=E.Element('{'+A+'}pPr');p.insert(0,ppr)
        if 'align' in patch:ppr.set('algn',patch['align'])
        properties=[ensure(ppr,'a:defRPr'),ensure(p,'a:endParaRPr')]
        for run in p.findall('a:r',NS):
            rpr=child(run,'a:rPr')
            if rpr is None:rpr=E.Element('{'+A+'}rPr');run.insert(0,rpr)
            properties.append(rpr)
        for rpr in properties:
            for key,attr in [('bold','b'),('italic','i'),('underline','u')]:
                if key in patch:rpr.set(attr,('sng' if patch[key] else 'none') if key=='underline' else ('1' if patch[key] else '0'))
            if 'fontSize' in patch:rpr.set('sz',str(round(patch['fontSize']*100)))
            if 'fontColor' in patch:set_fill(rpr,patch['fontColor'])
            if 'fontFace' in patch:
                for name in ('latin','ea','cs'):ensure(rpr,'a:'+name).set('typeface','SimSun' if name=='ea' else 'Times New Roman')
                order={'ln':0,'noFill':1,'solidFill':1,'gradFill':1,'blipFill':1,'pattFill':1,'grpFill':1,'effectLst':2,'effectDag':2,'highlight':3,'uLnTx':4,'uLn':4,'uFillTx':5,'uFill':5,'latin':6,'ea':7,'cs':8,'sym':9,'hlinkClick':10,'hlinkMouseOver':11,'rtl':12,'extLst':99}
                rpr[:]=sorted(rpr,key=lambda n:order.get(tag(n),98))
def apply(source,patches,pictures=None):
    """Return a new PPTX. Untouched ZIP parts and all original object IDs survive."""
    pictures=pictures or {};validate_delivery(source,single_file=True)
    pages=native_pages(source);changed={};touched=set();pictures_added={}
    with archive(source) as z:
        trees={};types=xml(z.read('[Content_Types].xml'));types_changed=False
        for patch in patches:
            page=pages[patch['page']-1];part=page['part'];tree=trees.setdefault(part,xml(z.read(part)));touched.add(patch['page'])
            if patch['objectId']=='page':
                cs=child(tree,'p:cSld');bg=child(cs,'p:bg')
                if bg is None:bg=E.Element('{'+P+'}bg');cs.insert(0,bg)
                for n in list(bg):bg.remove(n)
                set_fill(E.SubElement(bg,'{'+P+'}bgPr'),patch['background']);continue
            found=[n for n in tree.iter() if tag(n) in ('sp','pic','cxnSp','graphicFrame') and identity(n) is not None and identity(n).get('id')==patch['objectId']]
            if len(found)!=1:raise ValueError('Object does not identify a unique native element')
            node=found[0];kind=tag(node);tx=text_body(node)
            if patch.get('delete'):
                if referenced(tree,patch['objectId']) or kind=='cxnSp':raise ValueError('Animated or connected objects cannot be deleted directly; use a comment')
                node.getparent().remove(node);continue
            if 'text' in patch:
                if kind!='sp' or not simple_text(tx):raise ValueError('Text object is not directly editable')
                replace_text(tx,patch['text'])
            if 'box' in patch or 'rotation' in patch:set_geometry(node,patch,page)
            if any(k in patch for k in ('fontFace','fontSize','fontColor','bold','italic','underline','align','valign')):style_text(tx,patch)
            if any(k in patch for k in ('fill','lineColor','lineWidth','fillOpacity','headEnd','tailEnd')):
                if kind not in ('sp','cxnSp'):raise ValueError('Only native shapes and connectors support these paint controls')
                sp=ensure(node,'p:spPr')
                if 'fill' in patch:set_fill(sp,patch['fill'],patch.get('fillOpacity'))
                elif 'fillOpacity' in patch:
                    solid=child(sp,'a:solidFill')
                    if solid is None or len(solid)!=1:raise ValueError('Use a solid fill before adjusting its opacity')
                    for n in list(solid[0]):
                        if tag(n)=='alpha':solid[0].remove(n)
                    E.SubElement(solid[0],'{'+A+'}alpha',val=str(round(patch['fillOpacity']*100000)))
                if 'lineColor' in patch:set_fill(ensure(sp,'a:ln'),patch['lineColor'])
                if 'lineWidth' in patch:ensure(sp,'a:ln').set('w',str(round(patch['lineWidth']*12700)))
                for ending in ('headEnd','tailEnd'):
                    if ending in patch:ensure(ensure(sp,'a:ln'),'a:'+ending).set('type',patch[ending])
                line=child(sp,'a:ln')
                if line is not None:
                    order={'noFill':0,'solidFill':0,'gradFill':0,'pattFill':0,'prstDash':1,'custDash':1,'round':2,'bevel':2,'miter':2,'headEnd':3,'tailEnd':4,'extLst':99};line[:]=sorted(line,key=lambda n:order.get(tag(n),98))
            if 'cells' in patch:
                table=child(node,'a:graphic/a:graphicData/a:tbl')
                if table is None:raise ValueError('Charts and formulas are not table cells')
                rows=table.findall('a:tr',NS)
                for c in patch['cells']:
                    try:cell=rows[c['row']].findall('a:tc',NS)[c['column']]
                    except IndexError:raise ValueError('Table cell is unavailable')
                    if cell.get('hMerge')=='1' or cell.get('vMerge')=='1':raise ValueError('Edit the first cell of a merged region')
                    replace_text(child(cell,'a:txBody'),c['text'])
            if 'crop' in patch or 'image' in patch:
                if kind!='pic':raise ValueError('Select a picture first')
                fill=child(node,'p:blipFill');blip=child(fill,'a:blip') if fill is not None else None
                if blip is None:raise ValueError('Unsupported picture source')
                if 'crop' in patch:
                    crop=child(fill,'a:srcRect')
                    if crop is None:crop=E.Element('{'+A+'}srcRect');fill.insert(list(fill).index(blip)+1,crop)
                    for key,val in patch['crop'].items():crop.set(key,str(round(val*100000)))
                if 'image' in patch:
                    image=pictures.get(patch['image']['id'])
                    if not image:raise ValueError('Replacement picture missing')
                    from PIL import Image
                    img=Image.open(io.BytesIO(image));img.verify();ext={'PNG':'png','JPEG':'jpg'}.get(img.format)
                    if not ext:raise ValueError('Only genuine PNG/JPG pictures are supported')
                    digest=hashlib.sha256(image).hexdigest();media='ppt/media/native-'+digest+'.'+ext;pictures_added[media]=image
                    relpart=posixpath.join(posixpath.dirname(part),'_rels',posixpath.basename(part)+'.rels')
                    rels=xml(changed.get(relpart,z.read(relpart)))
                    rid='rIdNative'+digest[:20]+patch['objectId'];existing=next((n for n in rels if n.get('Id')==rid),None)
                    if existing is None:E.SubElement(rels,'{'+REL+'}Relationship',Id=rid,Type=R+'/image',Target='../media/'+posixpath.basename(media))
                    blip.set('{'+R+'}embed',rid);blip.attrib.pop('{'+R+'}link',None);changed[relpart]=E.tostring(rels,xml_declaration=True,encoding='UTF-8',standalone=True)
                    if not any(n.get('Extension')==ext for n in types):E.SubElement(types,'{'+types.nsmap[None]+'}Default',Extension=ext,ContentType='image/'+('jpeg' if ext=='jpg' else 'png'));types_changed=True
            if 'layer' in patch:
                parent=node.getparent();siblings=[n for n in parent if tag(n) in ('sp','pic','grpSp','cxnSp','graphicFrame')];index=siblings.index(node)
                other=siblings[-1] if patch['layer']=='front' else siblings[0] if patch['layer']=='back' else siblings[min(len(siblings)-1,index+1)] if patch['layer']=='forward' else siblings[max(0,index-1)]
                if other is not node:
                    parent.remove(node);index=parent.index(other)+(1 if patch['layer'] in ('front','forward') else 0);parent.insert(index,node)
        for part,tree in trees.items():changed[part]=E.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True)
        if types_changed:changed['[Content_Types].xml']=E.tostring(types,xml_declaration=True,encoding='UTF-8',standalone=True)
        changed.update(pictures_added);output=io.BytesIO()
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as result:
            for item in z.infolist():result.writestr(item,changed.pop(item.filename,z.read(item.filename)))
            for name,data in changed.items():
                info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;result.writestr(info,data)
    artifact=output.getvalue();validate_delivery(artifact,single_file=True);return artifact,sorted(touched)
