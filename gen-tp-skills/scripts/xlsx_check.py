"""Read-only XLSX verification; standard-library OOXML, no authoring dependency."""
import re
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath

NS = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def text(value):
    return re.sub(r'<br\s*/?\s*>', '\n', str(value), flags=re.I)


def read_sheets(path):
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('损坏的 XLSX ZIP')
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(si.itertext()) for si in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        relationships = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        rels = {entry.get('Id'):entry.get('Target') for entry in relationships}
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        result = {}
        for sheet in workbook.find('s:sheets', NS):
            target = rels[sheet.get(RID)]
            target = target.lstrip('/') if target.startswith('/') else str(PurePosixPath('xl') / target)
            root = ET.fromstring(archive.read(target))
            rows = []
            for row in root.findall('s:sheetData/s:row', NS):
                record = {}
                for cell in row.findall('s:c', NS):
                    if cell.find('s:f', NS) is not None:
                        raise ValueError('计划文本导出不应生成公式')
                    value = cell.find('s:v', NS)
                    raw = '' if value is None else value.text or ''
                    if cell.get('t') == 's':
                        raw = shared[int(raw)]
                    elif cell.get('t') == 'inlineStr':
                        raw = ''.join(cell.find('s:is', NS).itertext())
                    record[re.match(r'[A-Z]+', cell.get('r'))[0]] = raw
                rows.append(record)
            result[sheet.get('name')] = rows
        return result


def verify(path, document, profile):
    sheets = read_sheets(path)
    expected = {row[4]: row for row in document['rows']}
    found = set()
    columns = profile['columns']
    layout = document.get('layout')
    issue_sheets = {s['name']: s for s in layout['issue_sheets']} if layout else {}
    if layout and list(sheets) != layout['categories'] + list(issue_sheets) + ['Plan Notes']:
        raise ValueError('新版 Excel 的 Sheet 集合或顺序错误')
    for name, rows in sheets.items():
        if name == 'Plan Notes':
            continue
        if name in issue_sheets:
            spec = issue_sheets[name]
            wanted_rows = [spec['headers']] + spec['rows']
            if len(rows) != len(wanted_rows):
                raise ValueError(f'Excel 问题表数量错误: {name}')
            for record, wanted_row in zip(rows, wanted_rows):
                for i, value in enumerate(wanted_row):
                    wanted = text(value)
                    actual = record.get(chr(65+i), '')
                    if actual != wanted and not (wanted.startswith('=') and actual == "'" + wanted):
                        raise ValueError(f'Excel 问题表字段不一致: {name}')
            continue
        headers = rows[0]
        if [headers.get(chr(65+i)) for i in range(len(columns))] != [col['name'] for col in columns]:
            raise ValueError(f'Excel表头错误: {name}')
        for record in rows[1:]:
            tp = record.get('A')
            if tp not in expected or tp in found:
                raise ValueError(f'Excel重复或未知测试点: {tp}')
            found.add(tp)
            if layout and expected[tp][0] != name:
                raise ValueError(f'Excel 测试点分类错误: {tp}')
            for i, col in enumerate(columns):
                if col['source'] == 'status':
                    status = next((re.sub(r'^规划状态[：:]\s*','',m).split('；')[0].split(';')[0] for m in document['meta'] if re.match(r'^规划状态[：:]',m)), '待确认')
                    if layout:
                        status = layout['point_status'][tp]
                    wanted = text(status)
                else:
                    wanted = text(expected[tp][col['source']])
                actual = record.get(chr(65+i), '')
                if actual != wanted and not (wanted.startswith('=') and actual == "'" + wanted):
                    raise ValueError(f'Excel字段不一致: {tp}/{col["name"]}')
    if found != set(expected):
        raise ValueError('Excel丢失测试点')
    exported_notes = iter(sheets.get('Plan Notes', [])[1:])
    for section, item, details in document['notes']:
        expected_text = text(details)
        combined = ''
        while True:
            record = next(exported_notes, None)
            if record is None or record.get('A','') != text(section) or record.get('B','') != text(item):
                raise ValueError('Excel附录缺失或顺序改变')
            combined += record.get('C','')
            if combined == expected_text:
                break
            if not expected_text.startswith(combined) or not record.get('C'):
                raise ValueError('Excel附录文本不一致')
    if next(exported_notes, None) is not None:
        raise ValueError('Excel附录含非来源内容')
    return len(found)
