#!/usr/bin/env python3
"""Read-only validation for gen-tp-skills' single-table Markdown contract."""
import argparse
from collections import Counter
from pathlib import Path
import re
import sys
from tp_layout import make_layout

HEADERS = [
    '测试需求', '测试子需求(L1)', '测试子需求(L2)', '测试子需求(L3)',
    '测试点名', '测试点描述', '需求ID(s)', '关联用例名称',
    '功能覆盖率描述(Optional)', '直接用例激励描述(Optional)',
    '环境检查说明', '度量测试点覆盖', '标签',
]
POINT_SECTION = '测试点汇总表'
STAT_SECTION = '测试点统计'


class ContractError(ValueError):
    pass


def cells(line):
    """Explicit supported subset: escaped pipes and backslashes in one-line cells."""
    text = line.strip()
    if not text.startswith('|') or not text.endswith('|'):
        raise ContractError('表格每行须以 | 开始和结束')
    result, part = [], []
    i = 1
    while i < len(text) - 1:
        char = text[i]
        if char == '\\' and i + 1 < len(text) - 1 and text[i + 1] in '|\\':
            part.append(text[i + 1])
            i += 2
            continue
        if char == '|':
            result.append(''.join(part).strip())
            part = []
        else:
            part.append(char)
        i += 1
    result.append(''.join(part).strip())
    return result


def table(block, expected):
    start = next((i for i, (_, line) in enumerate(block) if line.strip().startswith('|')), None)
    if start is None or start + 1 >= len(block):
        raise ContractError('缺少表格或表头分隔行')
    number, header = block[start]
    if cells(header) != expected:
        raise ContractError(f'行 {number}: 表头不匹配，要求 {expected}')
    delimiters = cells(block[start + 1][1])
    if len(delimiters) != len(expected) or any(not re.fullmatch(r':?-{3,}:?', x) for x in delimiters):
        raise ContractError(f'行 {block[start + 1][0]}: 无效表头分隔行')
    rows, ended = [], False
    for number, line in block[start + 2:]:
        if not line.strip().startswith('|'):
            ended = True
            continue
        if ended:
            raise ContractError(f'行 {number}: 同一章节不允许第二张表或中断的表格')
        values = cells(line)
        if len(values) != len(expected):
            raise ContractError(f'行 {number}: 需要 {len(expected)} 列，实际 {len(values)} 列；检查管道转义')
        rows.append((number, values))
    return rows


def parse_document(text, stage='planning'):
    if stage not in ('planning', 'handoff'):
        raise ContractError(f'未知阶段: {stage}')
    sections, current, metadata, title, fence = {}, None, [], None, None
    for number, line in enumerate(text.splitlines(), 1):
        mark = re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$', line)
        if mark:
            if fence is None:
                fence = (mark[1][0], len(mark[1]))
            elif mark[1][0] == fence[0] and len(mark[1]) >= fence[1] and not mark[2].strip():
                fence = None
            if current not in (None, POINT_SECTION, STAT_SECTION):
                sections[current].append((number, line))
            continue
        if fence:
            if current not in (None, POINT_SECTION, STAT_SECTION):
                sections[current].append((number, line))
            continue
        if line.startswith('# '):
            if title is not None:
                raise ContractError(f'行 {number}: 只允许一个文档 H1')
            title = line[2:].strip()
            continue
        if line.startswith('## '):
            current = line[3:].strip()
            if current in sections:
                raise ContractError(f'行 {number}: 重复章节 {current}')
            sections[current] = []
            continue
        if current is None:
            if line.startswith('> '):
                metadata.append(line[2:].strip())
        else:
            sections[current].append((number, line))
    if fence:
        raise ContractError('代码围栏未闭合')
    if not title:
        raise ContractError('缺少文档标题')
    if not {POINT_SECTION, STAT_SECTION}.issubset(sections):
        raise ContractError('缺少 测试点统计 或 测试点汇总表 章节')
    rows = table(sections[POINT_SECTION], HEADERS)
    if not rows:
        raise ContractError('没有测试点；空模板不能作为完成的测试点计划')
    seen = set()
    for number, row in rows:
        if any(not value for value in row):
            raise ContractError(f'行 {number}: 空单元格须按合同填 - 或待反填')
        if any(row[i] == '-' for i in (0, 1, 4, 5, 6, 7, 10, 11, 12)):
            raise ContractError(f'行 {number}: 必填字段不能为 -')
        name = row[4]
        if not re.fullmatch(r'[a-z][a-z0-9_]*', name) or name in seen:
            raise ContractError(f'行 {number}: 测试点名非法或重复: {name}')
        seen.add(name)
        if len(row[5]) > 200:
            raise ContractError(f'行 {number}: 测试点描述超过 200 字符')
        match = re.fullmatch(r'\[(cg|cp|p|t)\]\s+(.+)', row[11])
        if not match:
            raise ContractError(f'行 {number}: 无效度量格式')
        kind, target = match.groups()
        if row[9] == '-':
            raise ContractError(f'行 {number}: 第 10 列直接用例激励描述对所有主度量必填；旧表须按设计补齐必要操作与预期')
        if kind != 't' and row[8] == '-':
            raise ContractError(f'行 {number}: [{kind}] 的第 9 列功能覆盖率描述必填')
        placeholder = (kind == 't' and target == '待反填') or (
            kind != 't' and target.startswith('待设计:') and len(target) > len('待设计:'))
        if placeholder:
            if stage == 'handoff':
                raise ContractError(f'行 {number}: 交接前须确定度量目标: {target}')
        else:
            segment = r'[A-Za-z_][A-Za-z0-9_]*(?:\[\d+\])?'
            if not re.fullmatch(segment + r'(?:\.' + segment + r')*', target):
                raise ContractError(f'行 {number}: 无效具体目标: {target}')
            if len(target.split('.')) < {'t': 1, 'cg': 2, 'cp': 3, 'p': 2}[kind]:
                raise ContractError(f'行 {number}: 度量目标层级不足: {target}')
        if stage == 'handoff' and row[12] == '待确认':
            raise ContractError(f'行 {number}: DUT 版本尚未确认')
    totals = [re.fullmatch(r'总测试点数[：:]\s*(\d+)', x) for x in metadata]
    totals = [int(x[1]) for x in totals if x]
    if totals != [len(rows)]:
        raise ContractError('文档头须有唯一且正确的 总测试点数')
    statistics = table(sections[STAT_SECTION], ['测试需求', '测试点数量'])
    actual = Counter(row[0] for _, row in rows)
    expected = dict(actual)
    if '合计' in expected:
        raise ContractError('测试需求不能命名为统计保留项 合计')
    expected['合计'] = len(rows)
    found = {}
    for number, (category, count) in statistics:
        if category in found or not re.fullmatch(r'\d+', count):
            raise ContractError(f'行 {number}: 统计分类重复或计数非法')
        found[category] = int(count)
    if found != expected:
        raise ContractError(f'统计不一致: 应为 {expected}，实际 {found}')
    appendix = '\n\n'.join('## ' + name + '\n' + '\n'.join(line for _, line in block)
                           for name, block in sections.items()
                           if name not in (POINT_SECTION, STAT_SECTION))
    document = {'title': title, 'meta': metadata, 'rows': [r for _, r in rows], 'appendix': appendix}
    try:
        layout = make_layout(document, sections, table)
    except ValueError as error:
        raise ContractError(str(error)) from error
    if layout is not None:
        document['layout'] = layout
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('markdown', type=Path)
    parser.add_argument('--stage', choices=['planning', 'handoff'], default='planning')
    args = parser.parse_args()
    try:
        document = parse_document(args.markdown.read_text(encoding='utf-8-sig'), args.stage)
    except (OSError, UnicodeError, ContractError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    print(f'OK: {len(document["rows"])} points; stage={args.stage}; structure only, not approval or coverage evidence')
    return 0


if __name__ == '__main__':
    sys.exit(main())
