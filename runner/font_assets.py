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
SYSTEM_FONTS={
    'times-new-roman-regular':('Times New Roman','times.ttf','Times New Roman.ttf',0),
    'times-new-roman-bold':('Times New Roman','timesbd.ttf','Times New Roman Bold.ttf',0),
    'times-new-roman-italic':('Times New Roman','timesi.ttf','Times New Roman Italic.ttf',0),
    'times-new-roman-bold-italic':('Times New Roman','timesbi.ttf','Times New Roman Bold Italic.ttf',0),
    'simsun-regular':('SimSun','Simsun.ttc','simsun.ttc',0),
    # Secondary family for headings, numbers and display text: ships with Windows 10+, Office and WPS.
    'dengxian-regular':('DengXian','Deng.ttf','Deng.ttf',0),
    'dengxian-bold':('DengXian','Dengb.ttf','Dengb.ttf',0),
    'dengxian-light':('DengXian Light','Dengl.ttf','Dengl.ttf',0),
    'arial-regular':('Arial','arial.ttf','Arial.ttf',0),
    'arial-bold':('Arial','arialbd.ttf','Arial Bold.ttf',0),
}
# Approved on request (2026-11-21): installed by default on Windows and bundled with Office for
# Mac, so layouts match across both. Installed per task only when used (font-proxy.py ID),
# because the Chinese faces are 10-19 MB each.
OPTIONAL_SYSTEM_FONTS={
    'microsoft-yahei-light':('Microsoft YaHei Light','msyhl.ttc','msyhl.ttc',0),
    'microsoft-yahei-regular':('Microsoft YaHei','msyh.ttc','msyh.ttc',0),
    'microsoft-yahei-bold':('Microsoft YaHei','msyhbd.ttc','msyhbd.ttc',0),
    'simhei-regular':('SimHei','SimHei.ttf','SimHei.ttf',0),
    'kaiti-regular':('KaiTi','Kaiti.ttf','Kaiti.ttf',0),
    'fangsong-regular':('FangSong','Fangsong.ttf','Fangsong.ttf',0),
    'calibri-regular':('Calibri','Calibri.ttf','Calibri.ttf',0),
    'calibri-bold':('Calibri','Calibrib.ttf','Calibrib.ttf',0),
    'cambria-regular':('Cambria','Cambria.ttc','Cambria.ttc',0),
    'cambria-bold':('Cambria','Cambriab.ttf','Cambriab.ttf',0),
    'georgia-regular':('Georgia','georgia.ttf','Georgia.ttf',0),
    'georgia-bold':('Georgia','georgiab.ttf','Georgia Bold.ttf',0),
    'century-gothic-regular':('Century Gothic','Century Gothic.ttf','Century Gothic.ttf',0),
    'century-gothic-bold':('Century Gothic','Century Gothic Bold.ttf','Century Gothic Bold.ttf',0),
    'verdana-regular':('Verdana','Verdana.ttf','Verdana.ttf',0),
    'verdana-bold':('Verdana','Verdana Bold.ttf','Verdana Bold.ttf',0),
    'tahoma-regular':('Tahoma','tahoma.ttf','Tahoma.ttf',0),
    'tahoma-bold':('Tahoma','tahomabd.ttf','Tahoma Bold.ttf',0),
}
LINUX_SYSTEM_FONTS={
    'dejavu-serif-regular':('DejaVu Serif','/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',0),
    'noto-serif-sc-regular':('Noto Serif CJK SC','/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',2),
}
STARTER_IDS=tuple(LINUX_SYSTEM_FONTS) if os.sys.platform=='linux' else tuple(SYSTEM_FONTS)
SYSTEM_FONTS={**SYSTEM_FONTS,**OPTIONAL_SYSTEM_FONTS}  # all host faces; only STARTER_IDS are preinstalled

def deployment_defaults(platform=None):
    if (platform or os.sys.platform)=='linux':
        return {'latin':'DejaVu Serif','east_asian':'Noto Serif CJK SC','target':'Linux LibreOffice preview'}
    return {'latin':'Times New Roman','east_asian':'SimSun','target':'Windows WPS',
            'display_east_asian':'DengXian (等线: light, regular, bold) for headings, figures and display text',
            'display_latin':'Arial for Latin numerals and labels',
            'optional':'Font choice is open: any other family suits when it serves the language, register or requested '
                       'style (Japanese text in a Japanese face such as Yu Mincho, Yu Gothic or Hiragino; a handwriting or '
                       'bitmap face for a requested hand-drawn or pixel style). Install the actual file so previews match '
                       '(font-proxy.py host --family NAME, or a catalog ID such as microsoft-yahei-regular, kaiti-regular) '
                       'and list every family used in the completion summary; recipients are told to install missing fonts'}

def system_font_candidates(font_id):
    if font_id in LINUX_SYSTEM_FONTS:return [Path(LINUX_SYSTEM_FONTS[font_id][1])]
    _,office,system,_=SYSTEM_FONTS[font_id]
    return [Path('/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts')/office,
            Path('/System/Library/Fonts/Supplemental')/system,
            Path('C:/Windows/Fonts')/office.lower()]

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
        if os.sys.platform=='linux' and os.geteuid()==0:
            owner=os.stat(root);os.fchown(child,owner.st_uid,owner.st_gid)
            # Host-created task font directories must be traversable by that
            # task uid while an existing shell waits for its broker response.
            os.fchown(fd,owner.st_uid,owner.st_gid)
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
                'glyphs':len(cmap),'embedding_flags':bits,'subsetting_allowed':not bool(bits & 0x100),
                'editable_embedding_allowed':not bool(bits & 0x206),'missing_characters':missing,
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
    if font_id in SYSTEM_FONTS or font_id in LINUX_SYSTEM_FONTS:
        if descriptor:raise ValueError('Host font IDs cannot be replaced by a download descriptor')
        return install_system_font(root,font_id,text=text)
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

def install_system_font(root,font_id,*,text=''):
    """Copy a genuine installed host face for private task metrics/rendering.

    No proprietary font is downloaded, renamed, relicensed as OFL, globally
    installed or embedded into a presentation by this operation.
    """
    from fontTools.ttLib import TTFont
    if font_id in LINUX_SYSTEM_FONTS:expected,_,face_index=LINUX_SYSTEM_FONTS[font_id]
    else:expected,_,_,face_index=SYSTEM_FONTS[font_id]
    source=next((p for p in system_font_candidates(font_id) if p.is_file()),None)
    if source is None:raise FileNotFoundError('Actual host font unavailable: '+expected)
    if source.stat().st_size>MAX_FONT:raise ValueError('Host font exceeds size limit')
    original=source.read_bytes()
    with TTFont(io.BytesIO(original),fontNumber=face_index,lazy=False) as font:
        if font['name'].getDebugName(1)!=expected:raise ValueError('Host font family mismatch')
        license_description=font['name'].getDebugName(13) or ''
        license_url=font['name'].getDebugName(14) or ''
        if original[:4]==b'ttcf':
            output=io.BytesIO();font.save(output);data=output.getvalue()
        else:data=original
    meta=inspect(data,text);index=manifest(root)
    if sum(x.get('size',0) for x in index['fonts'])+len(data)>MAX_TOTAL or len(index['fonts'])>=32:raise ValueError('Task font limit reached')
    filename='fonts/'+font_id+'-'+meta['sha256'][:12]+'.'+meta['format']
    provenance_file='fonts/'+font_id+'-provenance.json'
    provenance=json.dumps({'source_kind':'host-installed-font','source_file':str(source),
        'source_sha256':hashlib.sha256(original).hexdigest(),'collection_face':face_index if original[:4]==b'ttcf' else None,
        'family':meta['family'],'style':meta['style'],'license_description':license_description,
        'license_url':license_url,'use':'Private authoring metrics and rendering; not an OFL download or a font-embedding receipt.'},ensure_ascii=False,indent=2).encode()
    record={**meta,'id':font_id,'file':filename,'source_kind':'host-installed-font',
        'source_sha256':hashlib.sha256(original).hexdigest(),'provenance_file':provenance_file,
        'provenance_sha256':hashlib.sha256(provenance).hexdigest(),'license':'host-installed; see original font licensing metadata',
        'extracted_collection_face':original[:4]==b'ttcf'}
    record.pop('missing_characters')
    publish(root,filename,data);publish(root,provenance_file,provenance)
    index['fonts'].append(record);publish(root,'fonts/index.json',json.dumps(index,ensure_ascii=False,indent=2).encode())
    configure(root)
    return {**record,'missing_characters':meta['missing_characters'],'cache_hit':False}

STYLE_PREFERENCE=('regular','w3','book','normal','roman','medium','w4','light')
# Windows family names used in decks, mapped to the macOS faces so previews match.
PREVIEW_ALIASES={'Yu Mincho':'YuMincho','游明朝':'YuMincho','Yu Gothic':'YuGothic','游ゴシック':'YuGothic',
    'Yu Gothic UI':'YuGothic','Meiryo':'Hiragino Sans','メイリオ':'Hiragino Sans','Meiryo UI':'Hiragino Sans',
    'MS Mincho':'Hiragino Mincho ProN','ＭＳ 明朝':'Hiragino Mincho ProN','MS PMincho':'Hiragino Mincho ProN',
    'MS Gothic':'Hiragino Sans','ＭＳ ゴシック':'Hiragino Sans','MS PGothic':'Hiragino Sans',
    'BIZ UDMincho':'Hiragino Mincho ProN','BIZ UDGothic':'Hiragino Sans','Malgun Gothic':'Apple SD Gothic Neo',
    'Segoe UI':'Helvetica Neue'}

def host_font_id(family,style):
    """Stable task font ID for a host-installed family (2026-11-26: any installed font may be used)."""
    def slug(value):
        text=re.sub('[^a-z0-9]+','-',value.lower()).strip('-')
        return text or 'f'+hashlib.sha256(value.encode()).hexdigest()[:10]
    return ('host-'+slug(family)+'-'+slug(style or 'regular'))[:80].rstrip('-')

def find_host_face(family,style=None):
    """Locate an installed face by family name (any localized name) with fontconfig."""
    import shutil,subprocess
    fc=shutil.which('fc-list') or next((p for p in ('/opt/homebrew/bin/fc-list','/usr/local/bin/fc-list','/usr/bin/fc-list') if Path(p).is_file()),None)
    if not fc:raise FileNotFoundError('fc-list is unavailable on this host')
    if not isinstance(family,str) or not family.strip() or len(family)>128 or any(c in family for c in ':\n\\'):raise ValueError('Invalid font family')
    done=subprocess.run([fc,family.strip(),'file','index','family','style'],capture_output=True,text=True,timeout=60)
    rows=[]
    for line in done.stdout.splitlines():
        try:path,rest=line.split(': ',1)
        except ValueError:continue
        fields=dict(x.split('=',1) for x in rest.split(':') if '=' in x)
        rows.append((path,int(fields.get('index','0') or 0),fields.get('family',''),fields.get('style','')))
    if not rows:raise FileNotFoundError('No installed font family named '+family)
    wanted=(style or '').strip().lower()
    def rank(row):
        styles=[s.strip().lower() for s in row[3].split(',') if s.strip()]
        primary=styles[0] if styles else 'regular'  # fontconfig appends a generic "Regular" to named weights
        if wanted:return (0 if primary==wanted else 1 if wanted in styles or wanted in primary else 2,row[1],row[0])
        return (STYLE_PREFERENCE.index(primary) if primary in STYLE_PREFERENCE else len(STYLE_PREFERENCE),row[1],row[0])
    path,index,_,styles=sorted(rows,key=rank)[0]
    if wanted and rank((path,index,'',styles))[0]==2:raise FileNotFoundError(f'{family} has no {style} style; installed: '+'; '.join(sorted({r[3].split(",")[0] for r in rows})))
    return Path(path),index

def install_host_family(root,family,style=None,*,text=''):
    """Copy any installed host face, found by family name, into the task so previews and reviews
    render the chosen font. Recipients still need the font; nothing is embedded or downloaded."""
    from fontTools.ttLib import TTFont
    root=Path(root).resolve(strict=True)
    source,face_index=find_host_face(family,style)
    if source.stat().st_size>MAX_FONT*4:raise ValueError('Host font collection exceeds size limit')
    original=source.read_bytes()
    with TTFont(io.BytesIO(original),fontNumber=face_index,lazy=False) as font:
        names={n.toUnicode() for n in font['name'].names if n.nameID in (1,4,16) and n.isUnicode()}
        actual_family=font['name'].getDebugName(16) or font['name'].getDebugName(1)
        actual_style=font['name'].getDebugName(17) or font['name'].getDebugName(2) or 'Regular'
        if 'fvar' in font:raise ValueError('Variable host fonts are not supported; choose a static style')
        if original[:4]==b'ttcf':
            output=io.BytesIO();font.save(output);data=output.getvalue()
        else:data=original
    font_id=host_font_id(actual_family,actual_style)
    index=manifest(root)
    existing=next((x for x in index['fonts'] if x.get('id')==font_id),None)
    if existing:return {**existing,'missing_characters':inspect(read(root,existing['file']),text)['missing_characters'],'cache_hit':True}
    if len(data)>MAX_FONT:raise ValueError('Host font face exceeds size limit')
    meta=inspect(data,text)
    if sum(x.get('size',0) for x in index['fonts'])+len(data)>MAX_TOTAL or len(index['fonts'])>=32:raise ValueError('Task font limit reached')
    filename='fonts/'+font_id+'-'+meta['sha256'][:12]+'.'+meta['format']
    provenance_file='fonts/'+font_id+'-provenance.json'
    provenance=json.dumps({'source_kind':'host-installed-font','source_file':str(source),'requested_family':family,
        'source_sha256':hashlib.sha256(original).hexdigest(),'collection_face':face_index if original[:4]==b'ttcf' else None,
        'family':meta['family'],'style':meta['style'],'names':sorted(names)[:12],
        'use':'Private authoring metrics and rendering; recipients need this font installed. Not embedded.'},ensure_ascii=False,indent=2).encode()
    record={**meta,'id':font_id,'file':filename,'source_kind':'host-installed-font','requested_family':family,
        'source_sha256':hashlib.sha256(original).hexdigest(),'provenance_file':provenance_file,
        'provenance_sha256':hashlib.sha256(provenance).hexdigest(),'license':'host-installed; see original font licensing metadata',
        'extracted_collection_face':original[:4]==b'ttcf'}
    record.pop('missing_characters')
    publish(root,filename,data);publish(root,provenance_file,provenance)
    index['fonts'].append(record);publish(root,'fonts/index.json',json.dumps(index,ensure_ascii=False,indent=2).encode())
    configure(root)
    return {**record,'missing_characters':meta['missing_characters'],'cache_hit':False}

def prepare_default_fonts(root):
    available=[];missing=[]
    for font_id in STARTER_IDS:
        try:install(root,font_id);available.append(font_id)
        except FileNotFoundError:missing.append(font_id)
    return {'available':available,'missing':missing}

def auxiliary_file(item):
    keys=('provenance_file','provenance_sha256') if item.get('source_kind')=='host-installed-font' else ('license_file','license_sha256')
    if not all(isinstance(item.get(key),str) and item[key] for key in keys):raise ValueError('Font license/provenance record is incomplete')
    return item[keys[0]],item[keys[1]]

def verified_files(root):
    result={}
    for item in manifest(root)['fonts']:
        auxiliary,digest=auxiliary_file(item)
        data=read(root,item['file']);auxiliary_data=read(root,auxiliary,128*1024)
        if hashlib.sha256(data).hexdigest()!=item['sha256'] or hashlib.sha256(auxiliary_data).hexdigest()!=digest:raise ValueError('Font or license/provenance bytes changed')
        if not item['file'].startswith('fonts/') or not auxiliary.startswith('fonts/'):raise ValueError('Invalid font resource path')
        result[item['file']]=data;result[auxiliary]=auxiliary_data
    return result

def copy_fonts(source,target,ids=None):
    index=manifest(source);items=[x for x in index['fonts'] if ids is None or x['id'] in ids]
    files=verified_files(source)
    current=manifest(target);by_id={x['id']:x for x in current['fonts']}
    for item in items:
        if item['id'] in by_id and by_id[item['id']]['sha256']!=item['sha256']:raise ValueError('Existing task font is immutable')
        for relative in (item['file'],auxiliary_file(item)[0]):publish(target,relative,files[relative])
        by_id[item['id']]=item
    publish(target,'fonts/index.json',json.dumps({'version':1,'fonts':list(by_id.values())},ensure_ascii=False,indent=2).encode())
    configure(target)

def configure(root):
    from xml.sax.saxutils import escape
    root=Path(root).resolve(strict=True)
    system='<include>/etc/fonts/fonts.conf</include>' if os.sys.platform=='linux' else '<dir>/System/Library/Fonts</dir><dir>/Library/Fonts</dir>'
    aliases=dict(PREVIEW_ALIASES)
    try:
        for item in manifest(root)['fonts']:
            if item.get('source_kind')=='host-installed-font' and item.get('requested_family'):
                aliases.setdefault(item['requested_family'],item['family'])
    except (ValueError,OSError):pass
    alias=''.join('<alias binding="same"><family>'+escape(a)+'</family><prefer><family>'+escape(b)+'</family></prefer></alias>'
                  for a,b in aliases.items() if a!=b)
    xml=('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>'+system+'<dir>'+escape(str(root/'fonts'))
         +'</dir><cachedir>'+escape(str(root/'font-cache'))+'</cachedir>'+alias+'</fontconfig>')
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
