"""Validate the opt-in six-topic outline and derive its issue views."""
import re

MARKER = '分类体系：base-cross-scenario'
CATEGORIES = ['Register Access', 'Config Space', 'Dynamic Input', 'Performance', 'Cross', 'Scenario']
ISSUE_HEADERS = ['issue_id', 'issue_status', 'affected_parameter', 'scenario_context',
                 'unresolved_item', 'missing_content', 'completion_condition', 'source', 'affected_tp_ids']
LIFECYCLE_HEADERS = ['affected_tp_id', 'lifecycle_status', 'missing_content',
                     'completion_or_unblock_condition', 'issue_id']


def make_layout(document, sections, table):
    """No guessing/reclassification: legacy documents retain their original layout."""
    markers = [m for m in document['meta'] if re.match(r'^分类体系[：:]', m)]
    if not markers:
        return None
    if len(markers) != 1 or re.sub(r'^分类体系[：:]\s*', '', markers[0]) != 'base-cross-scenario':
        raise ValueError('未知或重复的分类体系')
    rows = document['rows']
    ids = {row[4] for row in rows}
    categories = {row[0] for row in rows}
    if not categories.issubset(CATEGORIES):
        raise ValueError('新版主表仅允许六类: ' + ', '.join(CATEGORIES))
    if 'base 适用性' not in sections or '规格缺口' not in sections:
        raise ValueError('新版须包含 base 适用性 和 规格缺口 表')
    applicability = table(sections['base 适用性'], ['category', 'disposition', 'basis'])
    seen = set()
    for _, (category, disposition, basis) in applicability:
        if category not in CATEGORIES[:4] or category in seen:
            raise ValueError('base 适用性须四类各一行')
        seen.add(category)
        if disposition not in ('有测试点', '规格待补充', '不适用') or not basis or basis == '-':
            raise ValueError('base 适用性须给出明确结论及依据')
        if disposition == '有测试点' and category not in categories:
            raise ValueError(f'{category} 声明有测试点但主表无点')
        if disposition == '不适用' and category in categories:
            raise ValueError(f'{category} 不适用与主表测试点冲突')
    if seen != set(CATEGORIES[:4]):
        raise ValueError('base 适用性缺少必查类别')
    statuses = {tp: 'draft' for tp in ids}
    if '测试点状态' in sections:
        state_seen = set()
        for _, (tp, status) in table(sections['测试点状态'], ['TP_ID', 'lifecycle_status']):
            if tp not in ids or tp in state_seen or status not in ('draft', 'reviewed', 'complete'):
                raise ValueError('测试点状态含未知/重复 TP 或非法文档状态')
            state_seen.add(tp)
            statuses[tp] = status
    issues, lifecycle, issue_ids = [], [], set()
    for _, row in table(sections['规格缺口'], ISSUE_HEADERS):
        key, state, parameter, context, unresolved, missing, condition, source, affected = row
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', key) or key in issue_ids:
            raise ValueError('问题 ID 非法或重复')
        issue_ids.add(key)
        if state not in ('open', 'resolved') or any(not value for value in row):
            raise ValueError('规格问题状态或必填字段无效')
        if any(value == '-' for value in (unresolved, missing, condition, source)):
            raise ValueError('规格问题须保留具体问题、缺失内容/结论、解除条件和来源')
        targets = [] if affected == '-' else [v.strip() for v in affected.split(',')]
        if len(targets) != len(set(targets)) or not set(targets).issubset(ids):
            raise ValueError('规格问题关联未知或重复的 TP_ID')
        issues.append(row)
        if state == 'open':
            for tp in targets:
                if statuses[tp] != 'draft':
                    raise ValueError(f'{tp} 存在 open 规格问题，文档状态须为 draft')
                lifecycle.append([tp, 'draft', missing, condition, key])
    return {
        'categories': CATEGORIES, 'point_status': statuses,
        'issue_sheets': [
            {'name': 'Scenario missing-input', 'headers': ISSUE_HEADERS, 'rows': issues,
             'widths': [18, 16, 32, 40, 60, 72, 72, 50, 42]},
            {'name': 'lifecycle missing-input', 'headers': LIFECYCLE_HEADERS, 'rows': lifecycle,
             'widths': [42, 18, 72, 72, 18]},
        ],
    }
