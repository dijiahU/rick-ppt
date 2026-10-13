"""Actual font acquisition and task-local installation; no presentation restyling."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import uuid
from urllib.parse import urlsplit
from urllib.request import urlopen

MAX_FONT=30*1024*1024
MAX_TOTAL=180*1024*1024
STARTER_IDS=('noto-sans-sc-regular','noto-sans-sc-bold','inter-regular','inter-bold')

def catalog_path():
    here=Path(__file__).resolve().parent
    return here/'font-catalog.json' if (here/'font-catalog.json').is_file() else here.parent/'assets/font-catalog.json'

def catalog():
    return json.loads(catalog_path().read_text())

def scoped(root,name):
    root=Path(root).resolve(strict=True);path=root/name
    if Path(name).is_absolute() or '..' in Path(name).parts or not path.resolve().is_relative_to(root):raise ValueError('Font path outside task')
    current=root
    for part in Path(name).parts:
        current=current/part
        if current.is_symlink():raise ValueError('Font symlink forbidden')
    return path

def read(root,name,limit=MAX_FONT):
    scoped(root,name)
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in Path(name).parts[:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
        child=os.open(Path(name).name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        with os.fdopen(child,'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('Regular font resource required')
            data=stream.read(limit+1)
    finally:os.close(fd)
    if len(data)>limit:raise ValueError('Font resource size limit exceeded')
    return data

def publish(root,name,data):
    scoped(root,name);pending='.font-'+uuid.uuid4().hex+'.pending'
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in Path(name).parts[:-1]:
            try:os.mkdir(part,mode=0o700,dir_fd=fd)
            except FileExistsError:pass
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
        child=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
        with os.fdopen(child,'wb') as stream:stream.write(data)
        os.replace(pending,Path(name).name,src_dir_fd=fd,dst_dir_fd=fd)
    finally:
        try:os.unlink(pending,dir_fd=fd)
        except FileNotFoundError:pass
        os.close(fd)

def manifest(root):
    path=scoped(root,'fonts/index.json')
    if not path.exists():return {'version':1,'fonts':[]}
    data=json.loads(read(root,'fonts/index.json',1024*1024))
    if data.get('version')!=1 or not isinstance(data.get('fonts'),list) or len(data['fonts'])>32:raise ValueError('Invalid font manifest')
    return data

def inspect(data,text=''):
    from fontTools.ttLib import TTFont
    if not 0<len(data)<=MAX_FONT or data[:4] not in (b'\x00\x01\x00\x00',b'OTTO'):raise ValueError('Use an actual TTF/OTF font, not HTML/WOFF/archive')
    with TTFont(io.BytesIO(data),lazy=False) as font:
        if 'fvar' in font:raise ValueError('Instantiate a static font before installation')
        names=font['name'];family=names.getDebugName(1);style=names.getDebugName(2)
        if not family or not style or len(family)>128 or any(ord(c)<32 for c in family+style):raise ValueError('Invalid font naming')
        cmap=font.getBestCmap() or {};weight=font['OS/2'].usWeightClass;bits=font['OS/2'].fsType
        if not cmap or not 1<=weight<=1000:raise ValueError('Invalid font metadata')
        missing=sorted({c for c in text if not c.isspace() and ord(c) not in cmap})
        return {'family':family,'style':style,'weight':weight,'format':'otf' if data[:4]==b'OTTO' else 'ttf',
                'glyphs':len(cmap),'editable_embedding_allowed':not bool(bits & 0x206),'missing_characters':missing,
                'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}

def static_font(data,weight):
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    if not 0<len(data)<=MAX_FONT or data[:4] not in (b'\x00\x01\x00\x00',b'OTTO'):raise ValueError('Use an actual TTF/OTF file')
    with TTFont(io.BytesIO(data),lazy=False) as font:
        if 'fvar' not in font:return data
        axes={a.axisTag:a.defaultValue for a in font['fvar'].axes}
        if 'wght' in axes:axes['wght']=weight
        font=instantiateVariableFont(font,axes,inplace=True,updateFontNames=True)
        result=io.BytesIO();font.save(result);return result.getvalue()

def direct_download(url):
    # Standalone catalog URLs only. Production injects its pinned public-HTTPS broker.
    if urlsplit(url).scheme!='https' or urlsplit(url).hostname!='raw.githubusercontent.com':raise ValueError('Standalone downloads use the official catalog; use host broker for another source')
    with urlopen(url,timeout=60) as response:
        if urlsplit(response.geturl()).scheme!='https':raise ValueError('HTTPS required')
        data=response.read(MAX_FONT+1)
    if len(data)>MAX_FONT:raise ValueError('Download exceeds font size limit')
    return data,url,''

def install(root,font_id,*,downloader=direct_download,descriptor=None,text=''):
    root=Path(root).resolve(strict=True)
    if not isinstance(font_id,str) or not re.fullmatch('[a-z0-9][a-z0-9-]{0,79}',font_id):raise ValueError('Invalid font ID')
    index=manifest(root)
    existing=next((x for x in index['fonts'] if x.get('id')==font_id),None)
    if existing:
        meta=inspect(read(root,existing['file']),text)
        if meta['sha256']!=existing['sha256']:raise ValueError('Installed font changed; refusing silent substitution')
        return {**existing,'missing_characters':meta['missing_characters'],'cache_hit':True}
    spec=descriptor or next((x for x in catalog()['fonts'] if x['id']==font_id),None)
    if not spec:raise ValueError('Unknown font; supply a direct official font URL and OFL license URL')
    license_data,license_url,_=downloader(spec['license_url'])
    if len(license_data)>128*1024:raise ValueError('Font license exceeds size limit')
    license_text=license_data.decode('utf-8')
    if 'SIL OPEN FONT LICENSE' not in license_text.upper():raise ValueError('This downloader requires an OFL font and its actual license file')
    original,source_url,_=downloader(spec['url'])
    data=static_font(original,spec.get('weight',400));meta=inspect(data,text)
    if sum(x.get('size',0) for x in index['fonts'])+len(data)>MAX_TOTAL or len(index['fonts'])>=32:raise ValueError('Task font limit reached')
    if descriptor and spec.get('family') not in (meta['family'],):raise ValueError('Downloaded family differs from requested family')
    filename='fonts/'+font_id+'-'+meta['sha256'][:12]+'.'+meta['format']
    license_file='fonts/'+font_id+'-OFL.txt'
    record={**meta,'id':font_id,'file':filename,'license_file':license_file,'license':'OFL-1.1','license_url':license_url,
            'license_sha256':hashlib.sha256(license_data).hexdigest(),'source_url':source_url,'source_page':spec.get('source_page',source_url),
            'source_sha256':hashlib.sha256(original).hexdigest(),'instantiated_static':data!=original}
    record.pop('missing_characters')
    publish(root,filename,data);publish(root,license_file,license_data)
    index['fonts'].append(record);publish(root,'fonts/index.json',json.dumps(index,ensure_ascii=False,indent=2).encode())
    configure(root)
    return {**record,'missing_characters':meta['missing_characters'],'cache_hit':False}

def verified_files(root):
    result={}
    for item in manifest(root)['fonts']:
        data=read(root,item['file']);license_data=read(root,item['license_file'],128*1024)
        if hashlib.sha256(data).hexdigest()!=item['sha256'] or hashlib.sha256(license_data).hexdigest()!=item['license_sha256']:raise ValueError('Font or license bytes changed')
        if not item['file'].startswith('fonts/') or not item['license_file'].startswith('fonts/'):raise ValueError('Invalid font resource path')
        result[item['file']]=data;result[item['license_file']]=license_data
    return result

def copy_fonts(source,target,ids=None):
    index=manifest(source);items=[x for x in index['fonts'] if ids is None or x['id'] in ids]
    files=verified_files(source)
    current=manifest(target);by_id={x['id']:x for x in current['fonts']}
    for item in items:
        if item['id'] in by_id and by_id[item['id']]['sha256']!=item['sha256']:raise ValueError('Existing task font is immutable')
        for key in ('file','license_file'):publish(target,item[key],files[item[key]])
        by_id[item['id']]=item
    publish(target,'fonts/index.json',json.dumps({'version':1,'fonts':list(by_id.values())},ensure_ascii=False,indent=2).encode())
    configure(target)

def configure(root):
    from xml.sax.saxutils import escape
    root=Path(root).resolve(strict=True)
    xml='<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>/System/Library/Fonts</dir><dir>/Library/Fonts</dir><dir>'+escape(str(root/'fonts'))+'</dir><cachedir>'+escape(str(root/'font-cache'))+'</cachedir></fontconfig>'
    publish(root,'fonts.conf',xml.encode())

def coverage(root,ids,text):
    from fontTools.ttLib import TTFont
    files=verified_files(root);available=set();selected=[]
    for item in manifest(root)['fonts']:
        if ids and item['id'] not in ids:continue
        with TTFont(io.BytesIO(files[item['file']])) as font:available.update((font.getBestCmap() or {}).keys())
        selected.append(item['id'])
    missing=sorted({c for c in text if not c.isspace() and ord(c) not in available})
    return {'ok':bool(selected) and not missing,'font_ids':selected,'missing_characters':missing}

def user_install(root,ids):
    # Standalone callers opt in. Public jobs have no broker operation or write
    # permission for this directory.
    target=Path.home()/'Library/Fonts' if os.sys.platform=='darwin' else Path.home()/'.local/share/fonts'
    target.mkdir(parents=True,exist_ok=True);files=verified_files(root);installed=[]
    for item in manifest(root)['fonts']:
        if item['id'] not in ids:continue
        name='rick-ppt-'+Path(item['file']).name
        publish(target,name,files[item['file']]);installed.append(str(target/name))
    return installed

def set_theme(root,workspace,latin,east_asian):
    from lxml import etree as E
    families={x['family'] for x in manifest(root)['fonts']}
    if latin not in families or east_asian not in families:raise ValueError('Theme fonts must be actual installed families')
    workspace=Path(workspace).resolve(strict=True);ns='http://schemas.openxmlformats.org/drawingml/2006/main';changed=[]
    for path in (workspace/'ppt/theme').glob('theme*.xml'):
        relative=path.relative_to(workspace).as_posix();data=read(workspace,relative,8*1024*1024)
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('Theme entities forbidden')
        tree=E.fromstring(data,E.XMLParser(resolve_entities=False,no_network=True))
        for branch in tree.findall('.//{'+ns+'}fontScheme/*'):
            if branch.tag not in ('{'+ns+'}majorFont','{'+ns+'}minorFont'):continue
            for tag,family in [('latin',latin),('ea',east_asian)]:
                item=branch.find('{'+ns+'}'+tag)
                if item is None:raise ValueError('Invalid theme font scheme')
                item.set('typeface',family)
            for item in branch.findall('{'+ns+'}font'):
                if item.get('script')=='Hans':item.set('typeface',east_asian)
        publish(workspace,relative,E.tostring(tree,encoding='UTF-8',xml_declaration=True,standalone=True));changed.append(relative)
    if not changed:raise ValueError('No existing native theme found')
    return {'changed_theme_parts':changed,'latin':latin,'east_asian':east_asian}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path.cwd());commands=p.add_subparsers(dest='command',required=True)
    commands.add_parser('list');s=commands.add_parser('ensure');s.add_argument('ids',nargs='+');s.add_argument('--text',default='');s.add_argument('--user-install',action='store_true')
    s=commands.add_parser('check');s.add_argument('--ids',nargs='*');s.add_argument('--text',required=True)
    s=commands.add_parser('theme');s.add_argument('--workspace',type=Path,required=True);s.add_argument('--latin',required=True);s.add_argument('--east-asian',required=True)
    args=p.parse_args()
    if args.command=='list':result={'catalog':catalog(),'installed':manifest(args.root)}
    elif args.command=='ensure':
        result={'fonts':[install(args.root,x,text=args.text) for x in args.ids]}
        if args.user_install:result['installed_user_files']=user_install(args.root,args.ids)
    elif args.command=='check':result=coverage(args.root,args.ids,args.text)
    else:result=set_theme(args.root,args.workspace,args.latin,args.east_asian)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result.get('ok',True) else 1

if __name__=='__main__':raise SystemExit(main())
