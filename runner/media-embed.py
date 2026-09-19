"""Add a native picture/GIF/video/audio object to an unpacked OOXML workspace.

Uses Microsoft's p14:media embedding pattern; it does not verify playback.
Run the existing snapshot/validate/render/export workflow around this helper.
"""
import argparse
import json
from pathlib import Path
import shutil
import uuid
from lxml import etree as E
from PIL import Image

P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PK='http://schemas.openxmlformats.org/package/2006/relationships'
P14='http://schemas.microsoft.com/office/powerpoint/2010/main'
CT='http://schemas.openxmlformats.org/package/2006/content-types'

def embed(workspace,slide_number,media,poster,box,fit='contain'):
    root=Path(workspace).resolve();media=Path(media).resolve()
    suffix=media.suffix.lower();mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.mp4':'video/mp4','.mp3':'audio/mpeg'}
    if suffix not in mime:raise ValueError('Use normalized media from the broker')
    if len(box)!=4 or not all(__import__('math').isfinite(v) for v in box) or min(box[2:])<=0:raise ValueError('Invalid box')
    parser=E.XMLParser(resolve_entities=False,no_network=True)
    presentation=E.parse(str(root/'ppt/presentation.xml'),parser)
    slides=presentation.findall(f'.//{{{P}}}sldId')
    if not 1<=slide_number<=len(slides):raise ValueError('Slide number out of range')
    rels=E.parse(str(root/'ppt/_rels/presentation.xml.rels'),parser)
    rid=slides[slide_number-1].get(f'{{{R}}}id')
    rel=next(r for r in rels.getroot() if r.get('Id')==rid)
    if rel.get('TargetMode')=='External':raise ValueError('External slide not supported')
    target=rel.get('Target');part=(root/target.lstrip('/') if target.startswith('/') else root/'ppt'/target).resolve()
    if not part.is_relative_to(root):raise ValueError('Outside workspace')
    tree=E.parse(str(part),parser);shapes=tree.find(f'.//{{{P}}}spTree')
    if shapes is None:raise ValueError('No shape tree')
    relpath=part.parent/'_rels'/(part.name+'.rels')
    slide_rels=E.parse(str(relpath),parser) if relpath.exists() else E.ElementTree(E.Element(f'{{{PK}}}Relationships',nsmap={None:PK}))
    types=E.parse(str(root/'[Content_Types].xml'),parser)
    def asset(path,content_type):
        path=Path(path);name='import-'+uuid.uuid4().hex+path.suffix.lower()
        dest=root/'ppt/media'/name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(path,dest)
        ext=path.suffix.lower().lstrip('.')
        if not any(t.get('Extension')==ext for t in types.getroot()):E.SubElement(types.getroot(),f'{{{CT}}}Default',Extension=ext,ContentType=content_type)
        return '../media/'+name
    def relation(kind,target):
        rid='rId'+uuid.uuid4().hex
        E.SubElement(slide_rels.getroot(),f'{{{PK}}}Relationship',Id=rid,Type=kind,Target=target)
        return rid
    def node(parent,namespace,tag,**attrs):return E.SubElement(parent,f'{{{namespace}}}{tag}',**{k:str(v) for k,v in attrs.items()})
    is_media=suffix in ('.mp4','.mp3')
    if is_media and (not poster or Path(poster).suffix.lower()!='.png'):raise ValueError('Video/audio needs a PNG poster or icon')
    if fit not in ('contain','cover','stretch'):raise ValueError('Invalid fit')
    with Image.open(poster if is_media else media) as image:iw,ih=image.size
    x,y,w,h=box;crop=None
    if fit=='contain':
        scale=min(w/iw,h/ih);nw,nh=iw*scale,ih*scale
        box=(x+(w-nw)/2,y+(h-nh)/2,nw,nh)
    elif fit=='cover':
        source_ratio=iw/ih;target_ratio=w/h
        if source_ratio>target_ratio:
            trim=round((1-target_ratio/source_ratio)*50000);crop={'l':trim,'r':trim}
        else:
            trim=round((1-source_ratio/target_ratio)*50000);crop={'t':trim,'b':trim}
    target=asset(media,mime[suffix]);picture_target=asset(poster,'image/png') if is_media else target
    shape_id=max([int(x.get('id')) for x in tree.findall(f'.//{{{P}}}cNvPr')]+[1])+1
    pic=node(shapes,P,'pic');nv=node(pic,P,'nvPicPr');cn=node(nv,P,'cNvPr',id=shape_id,name='Imported '+media.stem)
    if is_media:node(cn,A,'hlinkClick',action='ppaction://media').set(f'{{{R}}}id','')
    node(node(nv,P,'cNvPicPr'),A,'picLocks',noChangeAspect='1')
    nvp=node(nv,P,'nvPr')
    if is_media:
        kind='video' if suffix=='.mp4' else 'audio'
        node(nvp,A,kind+'File').set(f'{{{R}}}link',relation(R+'/'+kind,target))
        ext=node(node(nvp,P,'extLst'),P,'ext',uri='{DAA4B4D4-6D71-4841-9C94-3DE7FCFB9230}')
        node(ext,P14,'media').set(f'{{{R}}}embed',relation('http://schemas.microsoft.com/office/2007/relationships/media',target))
    fill=node(pic,P,'blipFill');node(fill,A,'blip').set(f'{{{R}}}embed',relation(R+'/image',picture_target))
    if crop:node(fill,A,'srcRect',**crop)
    node(node(fill,A,'stretch'),A,'fillRect')
    pr=node(pic,P,'spPr');xf=node(pr,A,'xfrm');x,y,w,h=[round(v*914400) for v in box]
    node(xf,A,'off',x=x,y=y);node(xf,A,'ext',cx=w,cy=h);node(node(pr,A,'prstGeom',prst='rect'),A,'avLst')
    relpath.parent.mkdir(exist_ok=True)
    for xml,path in ((tree,part),(slide_rels,relpath),(types,root/'[Content_Types].xml')):xml.write(str(path),encoding='UTF-8',xml_declaration=True,standalone=True)
    return {'shapeId':shape_id,'slide':slide_number,'nativeMedia':is_media,'playbackVerified':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('workspace');p.add_argument('slide',type=int);p.add_argument('media');p.add_argument('--poster');p.add_argument('--fit',choices=('contain','cover','stretch'),default='contain');p.add_argument('--box',nargs=4,type=float,required=True,metavar=('X','Y','W','H'));a=p.parse_args()
    print(json.dumps(embed(a.workspace,a.slide,a.media,a.poster,a.box,a.fit)))
