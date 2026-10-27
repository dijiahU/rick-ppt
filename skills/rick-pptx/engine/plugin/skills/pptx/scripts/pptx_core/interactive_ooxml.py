"""Thin content add-in mutations matching Microsoft's pinned content golden fixture."""
from __future__ import annotations
import copy
import json
import re
import uuid
from pathlib import Path
from lxml import etree
from PIL import Image
from .common import A,P,R,PR,CT,NS,PptxError,parse,local,sha256
from .relationships import relationships,rels_part,slide_parts
from .interactive_validate import config

WE='http://schemas.microsoft.com/office/webextensions/webextension/2010/11'
PCA='http://schemas.microsoft.com/office/powerpoint/2013/contentapp'
MC='http://schemas.openxmlformats.org/markup-compatibility/2006'
WEBREL='http://schemas.microsoft.com/office/2011/relationships/webextension'
WEBCT='application/vnd.ms-office.webextension+xml'


def write(path, tree):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(etree.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True))


def element(parent,namespace,tag,**attrs):
    return etree.SubElement(parent,f'{{{namespace}}}{tag}',{k:str(v) for k,v in attrs.items()})


def allocate(root, directory, stem, extension):
    for i in range(1,100001):
        name=f'{directory}/{stem}{i}.{extension}'
        if not (root/name).exists():return name
    raise PptxError('Part allocation limit exceeded')


def add_rel(root,owner,kind,target):
    path=root/rels_part(owner)
    tree=parse(path) if path.exists() else etree.Element(f'{{{PR}}}Relationships',nsmap={None:PR})
    used={n.get('Id') for n in tree}
    rid=next(f'rId{i}' for i in range(1,100001) if f'rId{i}' not in used)
    element(tree,PR,'Relationship',Id=rid,Type=kind,Target='/'+target)
    write(path,tree)
    return rid


def add_type(root,part,ctype):
    path=root/'[Content_Types].xml';tree=parse(path)
    existing=tree.find(f'{{{CT}}}Override[@PartName="/{part}"]')
    if existing is not None:
        if existing.get('ContentType')!=ctype:raise PptxError('Conflicting content type')
        return
    element(tree,CT,'Override',PartName='/'+part,ContentType=ctype);write(path,tree)


def bounds_check(root,bounds):
    size=parse(root/'ppt/presentation.xml').find('p:sldSz',NS)
    if size is None:raise PptxError('Missing slide dimensions')
    if set(bounds)!={'x','y','width','height'} or any(not isinstance(v,int) or isinstance(v,bool) for v in bounds.values()):raise PptxError('Bounds must be integer EMUs')
    x,y,w,h=(bounds[k] for k in ('x','y','width','height'))
    if min(x,y)<0 or min(w,h)<=0 or x+w>int(size.get('cx')) or y+h>int(size.get('cy')):raise PptxError('Interactive bounds exceed slide')


def picture(ident,name,rid,bounds):
    pic=etree.Element(f'{{{P}}}pic');nv=element(pic,P,'nvPicPr');element(nv,P,'cNvPr',id=ident,name=name);element(nv,P,'cNvPicPr');element(nv,P,'nvPr')
    fill=element(pic,P,'blipFill');blip=element(fill,A,'blip');blip.set(f'{{{R}}}embed',rid);element(element(fill,A,'stretch'),A,'fillRect')
    sp=element(pic,P,'spPr');xfrm=element(sp,A,'xfrm');set_bounds(xfrm,bounds);element(element(sp,A,'prstGeom',prst='rect'),A,'avLst');return pic


def set_bounds(xfrm,bounds):
    for tag,attrs in [('off',{'x':bounds['x'],'y':bounds['y']}),('ext',{'cx':bounds['width'],'cy':bounds['height']})]:
        node=xfrm.find(f'{{{A}}}{tag}')
        if node is None:node=element(xfrm,A,tag)
        for k,v in attrs.items():node.set(k,str(v))


def discover_content_addins(root):
    found=[]
    for number,part in enumerate(slide_parts(root),1):
        tree=parse(root/part);rels={r['id']:r for r in relationships(root,part)}
        for frame in tree.findall(f'.//{{{P}}}graphicFrame'):
            reference=frame.find(f'.//{{{WE}}}webextensionref')
            if reference is None:continue
            rid=reference.get(f'{{{R}}}id');rel=rels.get(rid,{})
            xfrm=frame.find(f'{{{P}}}xfrm');off=xfrm.find(f'{{{A}}}off') if xfrm is not None else None;ext=xfrm.find(f'{{{A}}}ext') if xfrm is not None else None
            props=frame.find(f'.//{{{P}}}cNvPr')
            record={'slide':number,'part':part,'relationship':rid,'webextension':rel.get('resolved'),'shapeId':props.get('id') if props is not None else None,'bounds':{'x':int(off.get('x',0)) if off is not None else 0,'y':int(off.get('y',0)) if off is not None else 0,'width':int(ext.get('cx',0)) if ext is not None else 0,'height':int(ext.get('cy',0)) if ext is not None else 0}}
            record['managed'] = props is not None and props.get('name', '').startswith('Interactive ')
            alternate = next((n for n in frame.iterancestors() if local(n) == 'AlternateContent'), None)
            record['nativeFallback'] = alternate is not None and alternate.find(f'{{{MC}}}Fallback/{{{P}}}pic') is not None
            target=rel.get('resolved')
            if target and (root/target).is_file():
                web=parse(root/target);app=web.find(f'{{{WE}}}reference');record['instanceId']=web.get('id','').strip('{}');record['webextensionId']=record['instanceId'];record['addinId']=app.get('id') if app is not None else None
                for setting in web.findall(f'{{{WE}}}properties/{{{WE}}}property'):
                    try:value=json.loads(setting.get('value','null'))
                    except ValueError:value=setting.get('value')
                    if setting.get('name') in ('deckId','sceneId','instanceId','schemaVersion','specHash'):record[setting.get('name')]=value
                snapshot=web.find(f'{{{WE}}}snapshot');srid=snapshot.get(f'{{{R}}}embed') if snapshot is not None else None
                record['snapshot']=next((r['resolved'] for r in relationships(root,target) if r['id']==srid),None)
            found.append(record)
    return found


def attach_content_addin(root,slide,metadata,bounds,snapshot):
    root=Path(root);bounds_check(root,bounds)
    parts=slide_parts(root)
    if not 1<=slide<=len(parts):raise PptxError('Invalid slide')
    with Image.open(snapshot) as image:
        if image.format!='PNG':raise PptxError('Fallback must be PNG')
        image.verify()
    part=parts[slide-1];path=root/part;tree=parse(path);sp_tree=tree.find('p:cSld/p:spTree',NS)
    if sp_tree is None:raise PptxError('Slide shape tree missing')
    used={int(n.get('id')) for n in tree.iter() if local(n)=='cNvPr'};ident=max(used,default=0)+1
    instance=metadata.get('instanceId') or str(uuid.uuid4());metadata={**metadata,'instanceId':instance}
    media=allocate(root,'ppt/media','interactive','png');(root/media).parent.mkdir(parents=True,exist_ok=True);(root/media).write_bytes(Path(snapshot).read_bytes());add_type(root,media,'image/png')
    image_rid=add_rel(root,part,R+'/image',media);webpart=allocate(root,'ppt/slides/udata','interactive','xml')
    snapshot_rid=add_rel(root,webpart,R+'/image',media)
    web=etree.Element(f'{{{WE}}}webextension',nsmap={'we':WE,'r':R},id='{'+instance+'}')
    cfg=config();element(web,WE,'reference',id=cfg['addinId'],version=cfg['version'],store='developer',storeType='Registry');element(web,WE,'alternateReferences');properties=element(web,WE,'properties')
    for key in ('deckId','sceneId','instanceId','schemaVersion','specHash'):
        if key not in metadata:raise PptxError(f'Missing content identity {key}')
        element(properties,WE,'property',name=key,value=json.dumps(metadata[key],ensure_ascii=False))
    element(web,WE,'bindings');element(web,WE,'snapshot').set(f'{{{R}}}embed',snapshot_rid);write(root/webpart,web);add_type(root,webpart,WEBCT);web_rid=add_rel(root,part,WEBREL,webpart)
    # Native underlay remains visible if Office recognizes but cannot load the add-in.
    sp_tree.append(picture(ident,'Interactive static '+instance,image_rid,bounds));ident+=1
    alternate=element(sp_tree,MC,'AlternateContent');choice=etree.SubElement(alternate,f'{{{MC}}}Choice',nsmap={'we':WE,'pca':PCA},Requires='we pca')
    frame=element(choice,P,'graphicFrame');nv=element(frame,P,'nvGraphicFramePr');element(nv,P,'cNvPr',id=ident,name='Interactive '+instance);element(element(nv,P,'cNvGraphicFramePr'),A,'graphicFrameLocks',noGrp='1');element(nv,P,'nvPr');set_bounds(element(frame,P,'xfrm'),bounds)
    data=element(element(frame,A,'graphic'),A,'graphicData',uri=WE);element(data,WE,'webextensionref').set(f'{{{R}}}id',web_rid)
    element(alternate,MC,'Fallback').append(picture(ident,'Interactive '+instance,image_rid,bounds));write(path,tree)
    return next(i for i in discover_content_addins(root) if i.get('instanceId')==instance)


def find_instance(root,instance):
    matches=[i for i in discover_content_addins(root) if i.get('instanceId')==instance]
    if len(matches)!=1:raise PptxError('Instance not uniquely found')
    return matches[0]


def resize_content_addin(root,instance,bounds):
    record=find_instance(root,instance);bounds_check(root,bounds);path=root/record['part'];tree=parse(path)
    for shape in tree.iter():
        if local(shape) not in ('pic','graphicFrame'):continue
        props=shape.find(f'.//{{{P}}}cNvPr')
        if props is not None and props.get('name') in ('Interactive '+instance,'Interactive static '+instance):
            for xfrm in shape.iter():
                if local(xfrm)=='xfrm':set_bounds(xfrm,bounds)
    write(path,tree);return find_instance(root,instance)


def update_content_addin(root,instance,metadata,snapshot=None):
    record=find_instance(root,instance);webpath=root/record['webextension'];tree=parse(webpath)
    for prop in tree.findall(f'{{{WE}}}properties/{{{WE}}}property'):
        key=prop.get('name')
        if key in metadata and key!='instanceId':prop.set('value',json.dumps(metadata[key]))
    if snapshot is not None:
        with Image.open(snapshot) as im:
            if im.format!='PNG':raise PptxError('Fallback must be PNG')
            im.verify()
        # Each attachment owns its fallback part; never change shared user media.
        (root/record['snapshot']).write_bytes(Path(snapshot).read_bytes())
    write(webpath,tree);return find_instance(root,instance)


def remove_content_addin(root,instance):
    record=find_instance(root,instance);path=root/record['part'];tree=parse(path)
    for node in list(tree.iter()):
        if local(node)=='AlternateContent' and any(n.get('name')=='Interactive '+instance for n in node.iter() if local(n)=='cNvPr'):
            node.getparent().remove(node)
    # Keep native snapshot and orphan parts for recovery; detach removes only the live region.
    write(path,tree);return {'detached':instance,'fallback_retained':True}


def clone_content_addin(root,instance,slide,bounds=None):
    record=find_instance(root,instance)
    meta={k:record[k] for k in ('deckId','sceneId','schemaVersion','specHash')}
    return attach_content_addin(root,slide,meta,bounds or record['bounds'],root/record['snapshot'])


def validate_ooxml(root):
    errors=[];instances=set()
    try:
        ct=parse(root/'[Content_Types].xml');types={n.get('PartName'):n.get('ContentType') for n in ct if local(n)=='Override'}
        for item in discover_content_addins(root):
            if item.get('addinId')!=config()['addinId'] and not item.get('managed'):
                # Unknown user add-ins are preserved and only native structural checks apply.
                continue
            instance=item.get('instanceId')
            if item.get('addinId')!=config()['addinId']:errors.append('Managed add-in ID does not match manifest')
            if not item.get('nativeFallback'):errors.append('Missing native fallback picture')
            if instance != item.get('webextensionId'):errors.append('Instance property differs from webextension ID')
            try:uuid.UUID(instance)
            except (ValueError,TypeError,AttributeError):errors.append('Invalid content instanceId')
            if not re.fullmatch('[a-f0-9]{64}',str(item.get('specHash',''))):errors.append('Invalid scene SHA256')
            if instance in instances:errors.append('Duplicate content instanceId')
            instances.add(instance)
            bounds_check(root,item['bounds'])
            rel=next((r for r in relationships(root,item['part']) if r['id']==item['relationship']),{})
            if rel.get('type')!=WEBREL or rel.get('external'):errors.append('Invalid content relationship')
            part=item.get('webextension')
            if not part or not (root/part).is_file():errors.append('Missing webextension part');continue
            if types.get('/'+part)!=WEBCT:errors.append('Invalid webextension content type')
            web=parse(root/part);ref=web.find(f'{{{WE}}}reference')
            if web.tag!=f'{{{WE}}}webextension' or ref is None:errors.append('Invalid webextension structure');continue
            if ref.get('version')!=config()['version'] or ref.get('storeType') not in ('Registry','FileSystem','OMEX') or not ref.get('store'):errors.append('Invalid app reference version/store')
            for key in ('deckId','sceneId','instanceId','specHash','schemaVersion'):
                if not item.get(key):errors.append(f'Missing content identity {key}')
            if item.get('schemaVersion')!=1:errors.append('Unsupported content schemaVersion')
            if not item.get('snapshot') or not (root/item['snapshot']).is_file():errors.append('Missing static fallback')
            else:
                with Image.open(root/item['snapshot']) as im:
                    if im.format != 'PNG':errors.append('Static fallback must be PNG')
                    im.verify()
    except (ValueError,OSError,PptxError,etree.Error) as error:errors.append(str(error))
    return errors
