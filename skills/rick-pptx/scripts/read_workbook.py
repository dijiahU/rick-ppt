"""Read an .xlsx attachment into one UTF-8 CSV per worksheet (values only).

No third-party dependency: the workbook is read with zipfile + lxml. Formulas
are not evaluated; the cached value Excel saved is used. Dates stored as serial
numbers are converted when the cell style is a date format. Merged cells, charts
and styling are ignored. The original attachment is never modified.
"""
import argparse
import csv
from datetime import datetime, timedelta
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile

from lxml import etree

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REL_NS = '{http://schemas.openxmlformats.org/package/2006/relationships}'
DATE_IDS = set(range(14, 23)) | {45, 46, 47}
MAX_PART = 64 * 1024 * 1024
PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


def _xml(z, name):
    info = z.getinfo(name)
    if info.file_size > MAX_PART:
        raise ValueError(f'{name} is too large to read')
    return etree.fromstring(z.read(name), PARSER)


def _column(ref):
    letters = re.match(r'[A-Z]+', ref or 'A').group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def _date_styles(z):
    if 'xl/styles.xml' not in z.namelist():
        return set()
    root = _xml(z, 'xl/styles.xml')
    custom = {int(f.get('numFmtId')): f.get('formatCode', '') for f in root.iterfind('m:numFmts/m:numFmt', NS)}
    dates = set()
    for index, xf in enumerate(root.iterfind('m:cellXfs/m:xf', NS)):
        fid = int(xf.get('numFmtId', '0'))
        code = re.sub(r'"[^"]*"|\[[^\]]*\]', '', custom.get(fid, ''))
        if fid in DATE_IDS or (fid in custom and re.search(r'[yd]|m{1,2}(?![a-z])', code, re.I) and 'h' not in code.lower()[:1]):
            dates.add(index)
    return dates


def _serial_to_date(value):
    day = datetime(1899, 12, 30) + timedelta(days=float(value))
    return day.strftime('%Y-%m-%d') if day.hour == day.minute == 0 else day.strftime('%Y-%m-%d %H:%M')


def read(path):
    with zipfile.ZipFile(path) as z:
        if len(z.namelist()) > 5000:
            raise ValueError('Workbook has too many parts')
        if any('vbaproject' in n.lower() for n in z.namelist()):
            raise ValueError('Macro workbooks are not supported')
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            shared = [''.join(si.itertext()) for si in _xml(z, 'xl/sharedStrings.xml').iterfind('m:si', NS)]
        dates = _date_styles(z)
        rels = {r.get('Id'): r.get('Target') for r in _xml(z, 'xl/_rels/workbook.xml.rels').iter(REL_NS + 'Relationship')}
        sheets = []
        for sheet in _xml(z, 'xl/workbook.xml').iterfind('m:sheets/m:sheet', NS):
            target = rels.get(sheet.get('{%s}id' % NS['r']), '')
            part = str(PurePosixPath('xl') / target) if not target.startswith('/') else target.lstrip('/')
            if part not in z.namelist():
                continue
            rows = []
            for row in _xml(z, part).iterfind('m:sheetData/m:row', NS):
                cells = {}
                for c in row.iterfind('m:c', NS):
                    kind, v = c.get('t'), c.findtext('m:v', default='', namespaces=NS)
                    if kind == 's':
                        value = shared[int(v)] if v.isdigit() and int(v) < len(shared) else ''
                    elif kind == 'inlineStr':
                        value = ''.join(c.find('m:is', NS).itertext()) if c.find('m:is', NS) is not None else ''
                    elif kind == 'b':
                        value = 'TRUE' if v == '1' else 'FALSE'
                    elif v and int(c.get('s', '0')) in dates:
                        try:
                            value = _serial_to_date(v)
                        except (ValueError, OverflowError):
                            value = v
                    elif kind in (None, 'n') and v:
                        try:
                            value = format(float(v), '.15g')  # drop binary float noise like 98.40000000000001
                        except ValueError:
                            value = v
                    else:
                        value = v
                    cells[_column(c.get('r'))] = value
                rows.append([cells.get(i, '') for i in range(max(cells) + 1)] if cells else [])
            sheets.append({'name': sheet.get('name', f'Sheet{len(sheets) + 1}'), 'rows': rows})
    return sheets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', help='Task-local .xlsx attachment')
    parser.add_argument('--out', required=True, help='Fresh task-local output directory for the CSV files')
    args = parser.parse_args()
    out = Path(args.out)
    try:
        if out.exists() and any(out.iterdir()):
            raise ValueError('Output directory must be new or empty')
        sheets = read(args.workbook)
        out.mkdir(parents=True, exist_ok=True)
        summary = []
        for i, sheet in enumerate(sheets, 1):
            safe = re.sub(r'[^\w一-鿿-]+', '_', sheet['name']).strip('_') or f'sheet{i}'
            target = out / f'{i:02d}-{safe}.csv'
            with open(target, 'w', newline='', encoding='utf-8-sig') as f:
                csv.writer(f).writerows(sheet['rows'])
            summary.append({'sheet': sheet['name'], 'csv': str(target), 'rows': len(sheet['rows']),
                            'columns': max((len(r) for r in sheet['rows']), default=0),
                            'header': sheet['rows'][0][:20] if sheet['rows'] else []})
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, etree.XMLSyntaxError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({'ok': True, 'sheets': summary,
                      'meaning': 'Values as saved in the workbook (formulas not recalculated). Check totals yourself before quoting them.'},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
