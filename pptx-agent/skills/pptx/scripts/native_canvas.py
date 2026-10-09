"""Native text metrics, image layering and editable one-unit bar charts.

No slide templates, card backgrounds, automatic font shrinking or style defaults.
Choose composition yourself; snapshot, validate, render and inspect afterward.
"""
import argparse
import io
import json
import math
import os
from pathlib import Path
import posixpath
import re
import shutil
import uuid
import zipfile
from lxml import etree as E
from PIL import Image,ImageFont

P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
C='http://schemas.openxmlformats.org/drawingml/2006/chart'
PKG='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
EMU=914400


def node(parent,ns,tag,**attrs):return E.SubElement(parent,'{'+ns+'}'+tag,**{k:str(v) for k,v in attrs.items()})
def write(path,tree):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.pending')
    try:
        pending.write_bytes(E.tostring(tree,encoding='UTF-8',xml_declaration=True,standalone=True))
        os.replace(pending,path)
    finally:pending.unlink(missing_ok=True)
def parse(path):return E.parse(str(path),E.XMLParser(resolve_entities=False,no_network=True))
def color(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9A-Fa-f]{6}',value):raise ValueError('Specify a six-digit RGB color')
    return value.upper()
def solid(parent,value):node(node(parent,A,'solidFill'),A,'srgbClr',val=color(value))
def scoped(root,relative):
    root=Path(root).resolve(strict=True);path=root/relative
    if not path.resolve().is_relative_to(root):raise ValueError('Path escaped native workspace')
    current=root
    for part in Path(relative).parts:
        current=current/part
        if current.is_symlink():raise ValueError('Native workspace symlink is forbidden')
    return path

def page(workspace,number):
    root=Path(workspace).resolve(strict=True);pres=parse(scoped(root,'ppt/presentation.xml'))
    slides=pres.findall('{'+P+'}sldIdLst/{'+P+'}sldId')
    if not 1<=number<=len(slides):raise ValueError('Slide number out of range')
    rid=slides[number-1].get('{'+R+'}id');rels=parse(scoped(root,'ppt/_rels/presentation.xml.rels'))
    rel=next(r for r in rels.getroot() if r.get('Id')==rid)
    if rel.get('TargetMode')=='External':raise ValueError('External slide forbidden')
    target=rel.get('Target');part=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('ppt',target))
    path=scoped(root,part);tree=parse(path);shapes=tree.find('{'+P+'}cSld/{'+P+'}spTree')
    if shapes is None:raise ValueError('Slide has no object tree')
    return root,path,tree,shapes

def transform(parent,box,ns=A):
    if len(box)!=4 or not all(math.isfinite(x) for x in box) or min(box[2:])<=0:raise ValueError('Invalid native object box')
    x,y,w,h=box;xf=node(parent,ns,'xfrm');node(xf,A,'off',x=round(x*EMU),y=round(y*EMU));node(xf,A,'ext',cx=round(w*EMU),cy=round(h*EMU));return xf

def next_id(tree):return max((int(n.get('id')) for n in tree.iter('{'+P+'}cNvPr')),default=1)+1

def handle(workspace,number,ident):
    return {'workspace':str(Path(workspace).resolve()),'slide':number,'shape_id':int(ident)}

def target(workspace,number,value):
    if isinstance(value,dict):
        if value.get('workspace')!=str(Path(workspace).resolve()) or value.get('slide')!=number:
            raise ValueError('Native handle belongs to a different workspace or slide')
        value=value.get('shape_id')
    if type(value) is not int or value<=0:raise ValueError('Use a returned native handle or positive object ID')
    return value

def add_shape(workspace,number,box,*,geometry,fill,stroke,line_width,name):
    # Every visual choice is explicit. A semantic object need not be a card.
    if geometry not in ('rect','roundRect','ellipse','triangle','diamond'):raise ValueError('Unsupported explicit geometry')
    if fill is not None:color(fill)
    if stroke is not None:color(stroke)
    if not math.isfinite(line_width) or line_width<=0:raise ValueError('Positive line width required')
    if not isinstance(name,str) or not name.strip():raise ValueError('Name the native object')
    _,path,tree,shapes=page(workspace,number);ident=next_id(tree)
    sp=node(shapes,P,'sp');nv=node(sp,P,'nvSpPr');node(nv,P,'cNvPr',id=ident,name=name);node(nv,P,'cNvSpPr');node(nv,P,'nvPr')
    pr=node(sp,P,'spPr');transform(pr,box);node(node(pr,A,'prstGeom',prst=geometry),A,'avLst')
    solid(pr,fill) if fill is not None else node(pr,A,'noFill')
    ln=node(pr,A,'ln',w=round(line_width*12700));solid(ln,stroke) if stroke is not None else node(ln,A,'noFill')
    write(path,tree);return handle(workspace,number,ident)

def add_connector(workspace,number,start,end,*,points,start_site,end_site,ink,line_width,arrow,name):
    from native_structure import anchor
    if len(points)!=4 or not all(math.isfinite(v) for v in points):raise ValueError('Specify exact start/end coordinates')
    if not math.isfinite(line_width) or line_width<=0:raise ValueError('Positive line width required')
    if arrow not in ('none','triangle'):raise ValueError('Choose arrow none/triangle')
    color(ink);start=target(workspace,number,start);end=target(workspace,number,end)
    _,path,tree,shapes=page(workspace,number);ident=next_id(tree)
    cx=node(shapes,P,'cxnSp');nv=node(cx,P,'nvCxnSpPr');node(nv,P,'cNvPr',id=ident,name=name);node(nv,P,'cNvCxnSpPr');node(nv,P,'nvPr')
    pr=node(cx,P,'spPr');x1,y1,x2,y2=points
    if x1==x2 and y1==y2:raise ValueError('Connector must have a length')
    xf=transform(pr,(min(x1,x2),min(y1,y2),max(abs(x2-x1),1/EMU),max(abs(y2-y1),1/EMU)))
    if x2<x1:xf.set('flipH','1')
    if y2<y1:xf.set('flipV','1')
    node(node(pr,A,'prstGeom',prst='line'),A,'avLst');ln=node(pr,A,'ln',w=round(line_width*12700));solid(ln,ink);node(ln,A,'tailEnd',type=arrow)
    anchor(tree,ident,start,end,start_site,end_site)
    write(path,tree);return handle(workspace,number,ident)

def semantic_group(workspace,number,members,*,name):
    from native_structure import group
    _,path,tree,_=page(workspace,number)
    ident=group(tree,[target(workspace,number,m) for m in members],name)
    write(path,tree);return handle(workspace,number,int(ident))

def reveal(workspace,number,steps,*,replace=False):
    from native_builds import set_builds
    _,path,tree,_=page(workspace,number)
    ids=[[target(workspace,number,m) for m in step] for step in steps]
    set_builds(tree.getroot(),ids,replace=replace);write(path,tree)
    return {'slide':number,'steps':ids,'playback_verified':False}

def text_measure(text,font_file,size,width,*,index=0,padding=.04,line_spacing=1.12):
    if not isinstance(text,str) or not text.strip() or not all(math.isfinite(x) for x in (size,width,padding,line_spacing)) or size<=0 or width<=2*padding or padding<0 or line_spacing<1:
        raise ValueError('Invalid text measurement input')
    font=ImageFont.truetype(str(font_file),round(size*4),index=index)
    available=(width-2*padding)*72*4;lines=[]
    for paragraph in text.split('\n'):
        chunks=[]
        for token in re.findall(r'[^ \t]+|[ \t]+',paragraph):
            if any('\u3400'<=ch<='\u9fff' or '\u3040'<=ch<='\u30ff' for ch in token):
                for ch in token:
                    if ch in '，。！？；：、）】》」』' and chunks:chunks[-1]+=ch
                    else:chunks.append(ch)
            else:chunks.append(token)
        current=''
        for chunk in chunks:
            candidate=current+chunk
            if font.getlength(candidate)<=available:current=candidate;continue
            if not chunk.strip():continue
            if current.strip():lines.append(current.rstrip());current=chunk.lstrip()
            else:current=chunk
            if font.getlength(current)>available:raise ValueError('Unbreakable text exceeds the chosen width; widen, shorten or add a meaningful break')
        lines.append(current.rstrip())
    ascent,descent=font.getmetrics();line_points=max(size,(ascent+descent)/4)*line_spacing
    family,style=font.getname()
    return {'lines':lines,'height':len(lines)*line_points/72+2*padding,
            'line_points':line_points,'font_family':family,'bold':'bold' in style.lower() or 'demi' in style.lower(),'italic':'italic' in style.lower() or 'oblique' in style.lower(),
            'size':size,'width':width,'padding':padding,'measurement':'Installed-font estimate; actual native render still required'}

def add_text(workspace,number,text,font_file,size,ink,*,x,y,width,max_height,index=0,padding=.04,name='Editable text'):
    color(ink);measure=text_measure(text,font_file,size,width,index=index,padding=padding)
    if not math.isfinite(max_height) or max_height<=0 or measure['height']>max_height:raise ValueError(f"Text exceeds its allocated height: needs {measure['height']:.3f} inches for {len(measure['lines'])} lines in {measure['font_family']}; available {max_height:.3f}. Shorten, enlarge or recompose instead of clipping/shrinking")
    _,path,tree,shapes=page(workspace,number);ident=next_id(tree)
    sp=node(shapes,P,'sp');nv=node(sp,P,'nvSpPr');node(nv,P,'cNvPr',id=ident,name=name);node(nv,P,'cNvSpPr',txBox=1);node(nv,P,'nvPr')
    pr=node(sp,P,'spPr');transform(pr,(x,y,width,measure['height']));node(node(pr,A,'prstGeom',prst='rect'),A,'avLst');node(pr,A,'noFill');node(node(pr,A,'ln'),A,'noFill')
    body=node(sp,P,'txBody');node(body,A,'bodyPr',wrap='none',anchor='t',lIns=round(padding*EMU),rIns=round(padding*EMU),tIns=round(padding*EMU),bIns=round(padding*EMU));node(body,A,'lstStyle')
    for line in measure['lines']:
        p=node(body,A,'p');pp=node(p,A,'pPr');node(node(pp,A,'lnSpc'),A,'spcPts',val=round(measure['line_points']*100));node(node(pp,A,'spcAft'),A,'spcPts',val=0)
        run=node(p,A,'r');rp=node(run,A,'rPr',sz=round(size*100),b=int(measure['bold']),i=int(measure['italic']));solid(rp,ink)
        for kind in ('latin','ea','cs'):node(rp,A,kind,typeface=measure['font_family'])
        node(run,A,'t').text=line;node(p,A,'endParaRPr',sz=round(size*100))
    write(path,tree);return {**handle(workspace,number,ident),**measure}

def relations(root,path):
    relpath=path.parent/'_rels'/(path.name+'.rels')
    return relpath,parse(relpath) if relpath.exists() else E.ElementTree(E.Element('{'+PKG+'}Relationships',nsmap={None:PKG}))

def add_image(workspace,number,source,box,*,fit,layer,task_root=None):
    if fit not in ('contain','cover') or layer not in ('back','front'):raise ValueError('Choose fit contain/cover and layer back/front')
    source=Path(source).resolve(strict=True);task_root=Path(task_root or Path.cwd()).resolve()
    if not source.is_relative_to(task_root):raise ValueError('Image must be task-scoped')
    with Image.open(source) as image:iw,ih=image.size;fmt=image.format
    suffix,mime={'PNG':('.png','image/png'),'JPEG':('.jpg','image/jpeg'),'GIF':('.gif','image/gif')}[fmt]
    if len(box)!=4 or not all(math.isfinite(v) for v in box) or min(box[2:])<=0:raise ValueError('Invalid image box')
    x,y,w,h=box;crop=None
    if fit=='contain':
        scale=min(w/iw,h/ih);nw,nh=iw*scale,ih*scale;box=(x+(w-nw)/2,y+(h-nh)/2,nw,nh)
    elif iw/ih>w/h:trim=round((1-(w/h)/(iw/ih))*50000);crop={'l':trim,'r':trim}
    else:trim=round((1-(iw/ih)/(w/h))*50000);crop={'t':trim,'b':trim}
    root,path,tree,shapes=page(workspace,number);ident=next_id(tree);relpath,rels=relations(root,path)
    name='canvas-'+uuid.uuid4().hex+suffix;dest=scoped(root,'ppt/media')/name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(source,dest)
    rid='rIdCanvas'+uuid.uuid4().hex;node(rels.getroot(),PKG,'Relationship',Id=rid,Type=R+'/image',Target='../media/'+name)
    pic=node(shapes,P,'pic');nv=node(pic,P,'nvPicPr');node(nv,P,'cNvPr',id=ident,name='Selected image');node(node(nv,P,'cNvPicPr'),A,'picLocks',noChangeAspect=1);node(nv,P,'nvPr')
    fill=node(pic,P,'blipFill');node(fill,A,'blip').set('{'+R+'}embed',rid)
    if crop:node(fill,A,'srcRect',**crop)
    node(node(fill,A,'stretch'),A,'fillRect');pr=node(pic,P,'spPr');transform(pr,box);node(node(pr,A,'prstGeom',prst='rect'),A,'avLst')
    if layer=='back':shapes.remove(pic);shapes.insert(2,pic)
    types=parse(scoped(root,'[Content_Types].xml'))
    if not any(t.get('Extension')==suffix[1:] for t in types.getroot()):node(types.getroot(),CT,'Default',Extension=suffix[1:],ContentType=mime)
    write(path,tree);write(relpath,rels);write(scoped(root,'[Content_Types].xml'),types)
    return {**handle(workspace,number,ident),'fit':fit,'layer':layer,'media':'ppt/media/'+name}

def workbook(labels,values,unit):
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';sheet=E.Element('{'+ns+'}worksheet',nsmap={None:ns});data=node(sheet,ns,'sheetData')
    for i,row in enumerate([['Category',unit],*zip(labels,values)],1):
        record=node(data,ns,'row',r=i)
        for col,value in zip(('A','B'),row):
            cell=node(record,ns,'c',r=col+str(i),t='n' if isinstance(value,(int,float)) else 'inlineStr')
            if isinstance(value,(int,float)):node(cell,ns,'v').text=str(value)
            else:node(node(cell,ns,'is'),ns,'t').text=value
    content=E.Element('{'+CT+'}Types',nsmap={None:CT});node(content,CT,'Default',Extension='rels',ContentType='application/vnd.openxmlformats-package.relationships+xml');node(content,CT,'Default',Extension='xml',ContentType='application/xml')
    for part,kind in [('/xl/workbook.xml','sheet.main'),('/xl/worksheets/sheet1.xml','worksheet')]:node(content,CT,'Override',PartName=part,ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.'+kind+'+xml')
    book=E.Element('{'+ns+'}workbook',nsmap={None:ns,'r':R});s=node(node(book,ns,'sheets'),ns,'sheet',name='Data',sheetId=1);s.set('{'+R+'}id','rId1')
    package=E.Element('{'+PKG+'}Relationships',nsmap={None:PKG});node(package,PKG,'Relationship',Id='rId1',Type=R+'/officeDocument',Target='xl/workbook.xml')
    links=E.Element('{'+PKG+'}Relationships',nsmap={None:PKG});node(links,PKG,'Relationship',Id='rId1',Type=R+'/worksheet',Target='worksheets/sheet1.xml')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,xml in [('[Content_Types].xml',content),('_rels/.rels',package),('xl/workbook.xml',book),('xl/_rels/workbook.xml.rels',links),('xl/worksheets/sheet1.xml',sheet)]:z.writestr(name,E.tostring(xml,encoding='UTF-8',xml_declaration=True))
    return stream.getvalue()

def add_bar_chart(workspace,number,labels,values,unit,colors,box,*,font_family,font_size):
    if not labels or len(labels)!=len(values) or len(labels)!=len(colors) or any(not isinstance(x,str) or not x.strip() for x in labels) or not isinstance(unit,str) or not unit.strip():raise ValueError('Specify categories, one unit and matching series values/colors')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in values) or max(values)<=0:raise ValueError('Use finite nonnegative values; negative/stacked charts require a different explicit implementation')
    if not font_family or not math.isfinite(font_size) or font_size<=0:raise ValueError('Specify chart typography')
    colors=[color(c) for c in colors]
    root,path,tree,shapes=page(workspace,number);chart=E.Element('{'+C+'}chartSpace',nsmap={'c':C,'a':A,'r':R});node(chart,C,'lang',val='en-US')
    actual=node(chart,C,'chart');plot=node(actual,C,'plotArea');node(plot,C,'layout');bars=node(plot,C,'barChart');node(bars,C,'barDir',val='bar');node(bars,C,'grouping',val='clustered');series=node(bars,C,'ser');node(series,C,'idx',val=0);node(series,C,'order',val=0);node(node(series,C,'tx'),C,'v').text=unit
    for i,c in enumerate(colors):point=node(series,C,'dPt');node(point,C,'idx',val=i);solid(node(point,C,'spPr'),c)
    for kind,tag,formula,data in [('cat','strRef',f'Data!$A$2:$A${len(labels)+1}',labels),('val','numRef',f'Data!$B$2:$B${len(values)+1}',values)]:
        ref=node(node(series,C,kind),C,tag);node(ref,C,'f').text=formula;cache=node(ref,C,'strCache' if kind=='cat' else 'numCache')
        if kind=='val':node(cache,C,'formatCode').text='0.##'
        node(cache,C,'ptCount',val=len(data))
        for i,v in enumerate(data):node(node(cache,C,'pt',idx=i),C,'v').text=str(v)
    dl=node(bars,C,'dLbls');node(dl,C,'dLblPos',val='outEnd');node(dl,C,'showLegendKey',val=0);node(dl,C,'showVal',val=1);node(dl,C,'showCatName',val=0);node(dl,C,'showSerName',val=0)
    node(bars,C,'gapWidth',val=70);node(bars,C,'axId',val=101);node(bars,C,'axId',val=102)
    for typ,ident,cross,pos in [('catAx',101,102,'l'),('valAx',102,101,'b')]:
        axis=node(plot,C,typ);node(axis,C,'axId',val=ident);scale=node(axis,C,'scaling');node(scale,C,'orientation',val='maxMin' if typ=='catAx' else 'minMax')
        if typ=='valAx':node(scale,C,'min',val=0);node(scale,C,'max',val=max(values)*1.15)
        node(axis,C,'delete',val=0);node(axis,C,'axPos',val=pos);node(axis,C,'majorTickMark',val='none');node(axis,C,'minorTickMark',val='none');node(axis,C,'tickLblPos',val='nextTo')
        tx=node(axis,C,'txPr');node(tx,A,'bodyPr');node(tx,A,'lstStyle');p=node(tx,A,'p');pr=node(node(p,A,'pPr'),A,'defRPr',sz=round(font_size*100));node(pr,A,'latin',typeface=font_family);node(pr,A,'ea',typeface=font_family);node(p,A,'endParaRPr',sz=round(font_size*100))
        node(axis,C,'crossAx',val=cross);node(axis,C,'crosses',val='autoZero')
        if typ=='valAx':node(axis,C,'crossBetween',val='between')
    node(actual,C,'plotVisOnly',val=1)
    folder=scoped(root,'ppt/charts');folder.mkdir(exist_ok=True);n=1
    while (folder/f'chart{n}.xml').exists():n+=1
    stem=f'chart{n}';rid='rIdChart'+uuid.uuid4().hex
    ed=node(chart,C,'externalData');ed.set('{'+R+'}id','rIdWorkbook');node(ed,C,'autoUpdate',val=0)
    write(folder/(stem+'.xml'),chart)
    embeddings=scoped(root,'ppt/embeddings');embeddings.mkdir(exist_ok=True);(embeddings/(stem+'.xlsx')).write_bytes(workbook(labels,values,unit))
    links=E.Element('{'+PKG+'}Relationships',nsmap={None:PKG});node(links,PKG,'Relationship',Id='rIdWorkbook',Type=R+'/package',Target='../embeddings/'+stem+'.xlsx');write(folder/'_rels'/(stem+'.xml.rels'),links)
    relpath,rels=relations(root,path);node(rels.getroot(),PKG,'Relationship',Id=rid,Type=R+'/chart',Target='../charts/'+stem+'.xml')
    ident=next_id(tree);frame=node(shapes,P,'graphicFrame');nv=node(frame,P,'nvGraphicFramePr');node(nv,P,'cNvPr',id=ident,name='Editable '+unit+' chart');node(nv,P,'cNvGraphicFramePr');node(nv,P,'nvPr');transform(frame,box,P);data=node(node(frame,A,'graphic'),A,'graphicData',uri=C);node(data,C,'chart').set('{'+R+'}id',rid)
    types=parse(scoped(root,'[Content_Types].xml'));node(types.getroot(),CT,'Override',PartName='/ppt/charts/'+stem+'.xml',ContentType='application/vnd.openxmlformats-officedocument.drawingml.chart+xml')
    if not any(x.get('Extension')=='xlsx' for x in types.getroot()):node(types.getroot(),CT,'Default',Extension='xlsx',ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    write(path,tree);write(relpath,rels);write(scoped(root,'[Content_Types].xml'),types)
    return {**handle(workspace,number,ident),'chart':'ppt/charts/'+stem+'.xml','workbook':'ppt/embeddings/'+stem+'.xlsx','unit':unit,'baseline':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);commands=p.add_subparsers(dest='command',required=True)
    for kind in ('measure','text'):
        s=commands.add_parser(kind);s.add_argument('--text',required=True);s.add_argument('--font',required=True);s.add_argument('--font-index',type=int,default=0);s.add_argument('--size',type=float,required=True);s.add_argument('--width',type=float,required=True)
        if kind=='text':
            s.add_argument('--workspace',required=True);s.add_argument('--slide',type=int,required=True);s.add_argument('--x',type=float,required=True);s.add_argument('--y',type=float,required=True);s.add_argument('--max-height',type=float,required=True);s.add_argument('--color',required=True)
    image=commands.add_parser('image');image.add_argument('--workspace',required=True);image.add_argument('--slide',type=int,required=True);image.add_argument('--file',required=True);image.add_argument('--box',type=float,nargs=4,required=True);image.add_argument('--fit',choices=('contain','cover'),required=True);image.add_argument('--layer',choices=('back','front'),required=True)
    bars=commands.add_parser('bars');bars.add_argument('--workspace',required=True);bars.add_argument('--slide',type=int,required=True);bars.add_argument('--data',required=True);bars.add_argument('--box',type=float,nargs=4,required=True);bars.add_argument('--font-family',required=True);bars.add_argument('--font-size',type=float,required=True)
    a=p.parse_args()
    if a.command=='measure':result=text_measure(a.text,a.font,a.size,a.width,index=a.font_index)
    elif a.command=='text':result=add_text(a.workspace,a.slide,a.text,a.font,a.size,a.color,x=a.x,y=a.y,width=a.width,max_height=a.max_height,index=a.font_index)
    elif a.command=='image':result=add_image(a.workspace,a.slide,a.file,a.box,fit=a.fit,layer=a.layer)
    else:
        data=json.loads(Path(a.data).read_text());result=add_bar_chart(a.workspace,a.slide,data['labels'],data['values'],data['unit'],data['colors'],a.box,font_family=a.font_family,font_size=a.font_size)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
