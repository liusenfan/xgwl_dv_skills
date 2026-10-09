"""Six-topic layout, issue lifecycle, legacy compatibility and export checks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from tp_contract import parse_document, ContractError
from tp_layout import CATEGORIES
from export_tp import notes
from xlsx_check import read_sheets, verify


class OutlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT/'examples/classified_st_tp.md').read_text(encoding='utf-8')

    def test_issue_views_keep_points_and_all_relations(self):
        doc = parse_document(self.text)
        self.assertEqual(len(doc['rows']), 3)
        self.assertEqual(doc['layout']['categories'], CATEGORIES)
        issues, lifecycle = doc['layout']['issue_sheets']
        self.assertEqual(len(issues['rows']), 3)
        self.assertEqual(len(lifecycle['rows']), 7)
        self.assertEqual({r[0] for r in lifecycle['rows']}, {r[4] for r in doc['rows']})
        self.assertTrue(all(v == 'draft' for v in doc['layout']['point_status'].values()))
        self.assertFalse(any(row[0] == '规格缺口' for row in notes(doc)))

    def test_resolved_and_unlinked_issues_do_not_block_other_points(self):
        source = self.text.replace('| DEMO-G01 | open |', '| DEMO-G01 | resolved |')
        source = source.replace('demo_length_001,demo_stable_002,demo_reset_003 |', '- |')
        source += '\n## 测试点状态\n\n| TP_ID | lifecycle_status |\n|---|---|\n| demo_length_001 | reviewed |\n'
        doc = parse_document(source)
        self.assertEqual(len(doc['rows']), 3)
        self.assertEqual(len(doc['layout']['issue_sheets'][0]['rows']), 3)
        self.assertEqual(len(doc['layout']['issue_sheets'][1]['rows']), 1)
        self.assertEqual(doc['layout']['point_status']['demo_length_001'], 'reviewed')
        self.assertEqual(doc['layout']['point_status']['demo_stable_002'], 'draft')

    def test_open_issue_rejects_finalized_state(self):
        source = self.text + '\n## 测试点状态\n\n| TP_ID | lifecycle_status |\n|---|---|\n| demo_length_001 | complete |\n'
        with self.assertRaisesRegex(ContractError, 'open'):
            parse_document(source)

    def test_bad_links_and_missing_base_assessment_are_rejected(self):
        cases = [
            self.text.replace('demo_length_001,demo_stable_002,demo_reset_003 |', 'unknown_point |'),
            self.text.replace('| DEMO-G02 | open |', '| DEMO-G01 | open |'),
            self.text.replace('| Register Access | 规格待补充 | demo-spec 未提供寄存器及访问属性，无法据此断言完整 DUT 无寄存器 |\n', ''),
            self.text.replace('| Dynamic Input | 有测试点 |', '| Dynamic Input | 不适用 |'),
            self.text.replace('Scenario |', 'Internal FIFO |'),
        ]
        for source in cases:
            with self.subTest(source=source[-100:]), self.assertRaises(ContractError):
                parse_document(source)

    def content_plan(self, status='complete'):
        source = self.text.replace('> 分类体系：base-cross-scenario',
                                   '> 分类体系：base-cross-scenario\n> 状态口径：内容完整性')
        source = source.replace('| open |', '| resolved |')
        source += '\n## 测试点状态\n\n| TP_ID | lifecycle_status |\n|---|---|\n'
        for tp in ('demo_length_001', 'demo_stable_002', 'demo_reset_003'):
            source += f'| {tp} | {status} |\n'
        return source

    def test_explicit_complete_with_implementation_todos(self):
        # Synthetic state fixture; the parser must preserve decisions, not judge prose.
        source = self.content_plan()
        self.assertIn('[cp] 待设计:', source)
        self.assertIn('[t] 待反填', source)
        doc = parse_document(source)
        self.assertEqual(set(doc['layout']['point_status'].values()), {'complete'})
        self.assertEqual(doc['layout']['issue_sheets'][1]['rows'], [])

    def test_content_policy_requires_all_explicit_states(self):
        source = self.content_plan()
        for candidate in (source.split('\n## 测试点状态')[0],
                          source.replace('| demo_stable_002 | complete |\n', '')):
            with self.subTest(candidate=candidate[-80:]), self.assertRaisesRegex(ContractError, '逐点'):
                parse_document(candidate)

    def test_content_policy_rejects_conflicting_or_legacy_states(self):
        cases = [self.content_plan().replace('| DEMO-G03 | resolved |', '| DEMO-G03 | open |'),
                 self.content_plan('reviewed'),
                 self.content_plan().replace('状态口径：内容完整性', '状态口径：automatic'),
                 self.content_plan().replace('> 状态口径：内容完整性',
                                             '> 状态口径：内容完整性\n> 状态口径：内容完整性'),
                 self.content_plan().replace('> 分类体系：base-cross-scenario\n', '')]
        for source in cases:
            with self.subTest(source=source[-80:]), self.assertRaises(ContractError):
                parse_document(source)

    def test_resolution_does_not_automatically_promote_draft(self):
        doc = parse_document(self.content_plan('draft'))
        self.assertEqual(set(doc['layout']['point_status'].values()), {'draft'})
        self.assertEqual(doc['layout']['issue_sheets'][1]['rows'], [])

    def test_reordering_rows_preserves_ids_and_statuses(self):
        source = self.content_plan().replace('| demo_stable_002 | complete |',
                                             '| demo_stable_002 | draft |')
        old = parse_document(source)
        lines = source.splitlines()
        indexes = [i for i, line in enumerate(lines)
                   if line.startswith(('| Scenario | 端到端', '| Dynamic Input | 反压', '| Scenario | 事务中'))]
        reversed_rows = [lines[i] for i in reversed(indexes)]
        for i, row in zip(indexes, reversed_rows):
            lines[i] = row
        new = parse_document('\n'.join(lines))
        self.assertEqual(old['layout']['point_status'], new['layout']['point_status'])
        self.assertEqual({r[4]: r for r in old['rows']}, {r[4]: r for r in new['rows']})

    def test_content_status_example_keeps_platform_todos_separate(self):
        doc = parse_document((ROOT/'examples/content-status-tp.md').read_text(encoding='utf-8'))
        self.assertEqual(doc['layout']['point_status'],
                         {'demo_backpressure': 'complete', 'demo_throughput': 'draft'})
        self.assertEqual([r[0] for r in doc['layout']['issue_sheets'][1]['rows']],
                         ['demo_throughput'])

    @unittest.skipUnless(os.environ.get('TP_OUTLINE_NODE') and os.environ.get('TP_OUTLINE_MODULES'), 'requires artifact runtime')
    def test_content_status_survives_all_format_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = ROOT/'examples/content-status-tp.md'
            out = Path(tmp)/'out'
            cmd = [sys.executable, '-X', 'utf8', '-B', str(ROOT/'scripts/export_tp.py'), str(source),
                   '--out-dir', str(out), '--formats', 'xlsx', 'html', 'markdown',
                   '--node', os.environ['TP_OUTLINE_NODE'], '--node-modules', os.environ['TP_OUTLINE_MODULES']]
            run = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(run.returncode, 0, run.stderr)
            doc = parse_document(source.read_text(encoding='utf-8'))
            doc['notes'] = notes(doc)
            profile = json.loads((ROOT/'assets/xlsx-style.json').read_text(encoding='utf-8'))
            self.assertEqual(verify(out/'content-status-tp.xlsx', doc, profile), 2)
            sheets = read_sheets(out/'content-status-tp.xlsx')
            self.assertEqual(sheets['Dynamic Input'][1]['B'], 'complete')
            self.assertEqual(sheets['Performance'][1]['B'], 'draft')
            self.assertEqual(len(sheets['lifecycle missing-input']), 2)
            self.assertEqual((out/'content-status-tp.md').read_text(encoding='utf-8'),
                             source.read_text(encoding='utf-8'))
            html = (out/'content-status-tp.html').read_text(encoding='utf-8')
            self.assertIn('complete', html)
            self.assertIn('demo_backpressure', html)

    def test_empty_issues_and_legacy_layout(self):
        source = '\n'.join(line for line in self.text.splitlines() if not line.startswith('| DEMO-G'))
        doc = parse_document(source)
        self.assertEqual(doc['layout']['issue_sheets'][0]['rows'], [])
        self.assertEqual(doc['layout']['issue_sheets'][1]['rows'], [])
        old = parse_document((ROOT/'examples/demo_st_tp.md').read_text(encoding='utf-8'))
        self.assertNotIn('layout', old)
        self.assertEqual(old['rows'][0][0], '数据传输')

    @unittest.skipUnless(os.environ.get('TP_OUTLINE_NODE') and os.environ.get('TP_OUTLINE_MODULES'), 'requires artifact runtime')
    def test_nine_sheet_lossless_export_and_all_text_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            source=base/'outline.md'
            # Check literal formula-like issue text is not executable.
            text=self.text.replace('未给出延迟/吞吐门限，不能由测试看门狗推定设计失败', '=literal-not-a-formula')
            source.write_text(text,encoding='utf-8')
            cmd=[sys.executable,'-X','utf8','-B',str(ROOT/'scripts/export_tp.py'),str(source),
                 '--out-dir',str(base/'out'),'--formats','xlsx','html','markdown',
                 '--node',os.environ['TP_OUTLINE_NODE'],'--node-modules',os.environ['TP_OUTLINE_MODULES']]
            run=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(run.returncode,0,run.stderr)
            doc=parse_document(text)
            doc['notes']=notes(doc)
            profile=json.loads((ROOT/'assets/xlsx-style.json').read_text(encoding='utf-8'))
            self.assertEqual(verify(base/'out/outline.xlsx',doc,profile),3)
            sheets=read_sheets(base/'out/outline.xlsx')
            self.assertEqual(list(sheets),CATEGORIES+['Scenario missing-input','lifecycle missing-input','Plan Notes'])
            self.assertEqual(len(sheets['Register Access']),1)
            self.assertEqual(len(sheets['Scenario missing-input']),4)
            self.assertEqual(len(sheets['lifecycle missing-input']),8)
            self.assertEqual((base/'out/outline.md').read_text(encoding='utf-8'),text)
            html=(base/'out/outline.html').read_text(encoding='utf-8')
            self.assertEqual(html.count('class="tpname"'),3)
            self.assertIn('DEMO-G01',html)


if __name__ == '__main__':
    unittest.main()
