"""Minimal hand-built workbooks: shared strings, numbers, dates and a second sheet."""
import csv
import json
import zipfile

import read_workbook as tool

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def workbook(path, sheets, shared, styles=''):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr('xl/workbook.xml', f'<workbook xmlns="{M}" xmlns:r="{R}"><sheets>' + ''.join(
            f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i, (name, _) in enumerate(sheets, 1)) + '</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(
            f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1)) + '</Relationships>')
        z.writestr('xl/sharedStrings.xml', f'<sst xmlns="{M}">' + ''.join(f'<si><t>{s}</t></si>' for s in shared) + '</sst>')
        if styles:
            z.writestr('xl/styles.xml', styles)
        for i, (_, body) in enumerate(sheets, 1):
            z.writestr(f'xl/worksheets/sheet{i}.xml', f'<worksheet xmlns="{M}"><sheetData>{body}</sheetData></worksheet>')


def test_reads_values_dates_and_every_sheet(tmp_path):
    styles = f'<styleSheet xmlns="{M}"><cellXfs><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>'
    first = ('<row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="s"><v>1</v></c></row>'
             '<row r="2"><c r="A2" s="1"><v>46023</v></c><c r="B2"><v>98.40000000000001</v></c><c r="C2" t="b"><v>1</v></c></row>')
    second = '<row r="1"><c r="A1" t="inlineStr"><is><t>说明</t></is></c></row>'
    path = tmp_path / 'sales.xlsx'
    workbook(path, [('月度销售', first), ('备注', second)], ['月份', '营业额'], styles)
    sheets = tool.read(path)
    assert [s['name'] for s in sheets] == ['月度销售', '备注']
    assert sheets[0]['rows'] == [['月份', '', '营业额'], ['2026-01-01', '98.4', 'TRUE']]
    assert sheets[1]['rows'] == [['说明']]


def test_cli_writes_one_csv_per_sheet_and_refuses_macros(tmp_path, capsys, monkeypatch):
    path = tmp_path / 'a.xlsx'
    workbook(path, [('S', '<row r="1"><c r="A1"><v>3</v></c></row>')], [])
    monkeypatch.setattr('sys.argv', ['read_workbook.py', str(path), '--out', str(tmp_path / 'out')])
    assert tool.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result['sheets'][0]['rows'] == 1
    with open(result['sheets'][0]['csv'], encoding='utf-8-sig') as f:
        assert list(csv.reader(f)) == [['3']]
    with zipfile.ZipFile(path, 'a') as z:
        z.writestr('xl/vbaProject.bin', b'x')
    monkeypatch.setattr('sys.argv', ['read_workbook.py', str(path), '--out', str(tmp_path / 'out2')])
    assert tool.main() == 1
    assert 'Macro' in json.loads(capsys.readouterr().out)['error']
