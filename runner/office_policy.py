"""Accept passive embedded chart workbooks, never arbitrary embedded payloads."""
import io
from pathlib import PurePosixPath
import posixpath
import zipfile
from lxml import etree


def archive(data,maximum=120*1024*1024):
    z=zipfile.ZipFile(io.BytesIO(data));seen=set();total=0
    if len(z.infolist())>10000:raise ValueError('Too many Office parts')
    for item in z.infolist():
        path=PurePosixPath(item.filename)
        if path.is_absolute() or '..' in path.parts or '\\' in item.filename or item.filename.lower() in seen or item.flag_bits&1:raise ValueError('Unsafe Office archive')
        if (item.external_attr>>16)&0o170000==0o120000:raise ValueError('Office symlink rejected')
        seen.add(item.filename.lower());total+=item.file_size
        if item.file_size>maximum or total>maximum:raise ValueError('Office archive too large')
    return z


def xml(data):
    parser=etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False)
    tree=etree.fromstring(data,parser)
    if tree.getroottree().docinfo.doctype:raise ValueError('Office DTD rejected')
    return tree


def validate_workbook(data):
    with archive(data,30*1024*1024) as z:
        names=z.namelist()
        if 'xl/workbook.xml' not in names or '[Content_Types].xml' not in names:raise ValueError('Chart data must be an XLSX workbook')
        for name in names:
            lower=name.lower()
            if any(part in lower for part in ('vbaproject','activex','embeddings/','externallinks/','connections.xml','customui/')) or lower.endswith(('.bin','.exe','.dll','.js','.vbs')):raise ValueError('Active workbook content rejected')
            if lower.endswith('.rels'):
                if any(n.get('TargetMode','').lower()=='external' for n in xml(z.read(name))):raise ValueError('External workbook relationships rejected')
        types=xml(z.read('[Content_Types].xml'))
        if any('macroenabled' in n.get('ContentType','').lower() for n in types):raise ValueError('Macro workbook rejected')
        for name in names:
            if name.endswith('.xml'):
                tree=xml(z.read(name))
                if any(etree.QName(n).localname in ('ddeLink','oleLink') for n in tree.iter() if isinstance(n.tag,str)):raise ValueError('Active workbook link rejected')


def validate_delivery(data):
    with archive(data) as z:
        embedded={n for n in z.namelist() if '/embeddings/' in n.lower() and not n.endswith('/')}
        chart_targets=set()
        for name in z.namelist():
            low=name.lower()
            if any(t in low for t in ('vbaproject','activex/')):raise ValueError('Active presentation content rejected')
            if low.endswith('.rels'):
                tree=xml(z.read(name))
                for rel in tree:
                    typ=rel.get('Type','').rsplit('/',1)[-1]
                    if typ in ('oleObject','control','vbaProject'):raise ValueError('Executable/active embedding rejected')
                    if name.startswith('ppt/charts/_rels/') and typ=='package' and rel.get('TargetMode','Internal')=='Internal':
                        target=posixpath.normpath(posixpath.join('ppt/charts',rel.get('Target','')))
                        chart_targets.add(target)
        for name in embedded:
            if name not in chart_targets or not name.lower().endswith('.xlsx'):raise ValueError('Only chart data workbooks may be embedded')
            validate_workbook(z.read(name))
