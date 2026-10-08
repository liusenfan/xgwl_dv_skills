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
