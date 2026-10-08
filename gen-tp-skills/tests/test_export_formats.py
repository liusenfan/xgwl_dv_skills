"""Format selection and lossless spreadsheet export regression tests."""
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_tp import formats, notes
from tp_contract import parse_document
from xlsx_check import verify, read_sheets


class FormatTests(unittest.TestCase):
    def test_default_aliases_and_invalid_selection(self):
        self.assertEqual(formats(), ['xlsx'])
        self.assertEqual(formats(['HTML,xslx', 'md', 'markdowm']), ['html','xlsx','markdown'])
        with self.assertRaises(ValueError):
            formats(['pdf'])

    def test_notes_preserve_metadata_and_table_rows(self):
        doc = {'title':'标题','meta':['状态：草案'], 'appendix':'## 来源\n| ID | 内容 |\n|---|---|\n| A | a\\|b |\n\n正文\n'}
        result = notes(doc)
        self.assertIn(['Document','metadata','状态：草案'], result)
        self.assertIn(['来源','A','内容: a|b'], result)
        self.assertIn(['来源','text','正文'], result)

    def test_text_only_selection_needs_no_node_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd = [sys.executable,'-B',str(ROOT/'scripts/export_tp.py'),str(ROOT/'examples/demo_st_tp.md'),'--out-dir',tmp,'--formats','html','markdown','--node','nonexistent-node']
            first = subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(first.returncode,0,first.stderr)
            self.assertEqual({p.suffix for p in Path(tmp).iterdir()}, {'.md','.html'})
            original = (Path(tmp)/'demo_st_tp.md').read_bytes()
            second = subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
            self.assertNotEqual(second.returncode,0)
            self.assertEqual((Path(tmp)/'demo_st_tp.md').read_bytes(),original)

    @unittest.skipUnless(os.environ.get('TP_NODE') and os.environ.get('TP_NODE_MODULES'), 'requires artifact runtime')
    def test_all_selected_sets_default_and_lossless_export(self):
        source_text = (ROOT/'examples/demo_st_tp.md').read_text(encoding='utf-8')
        # Literal formula-like text must survive without becoming executable.
        source_text += '\n## 文本保真\n=1+1\n\n' + '超长段落测试'*210 + '\n'
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base/'case.md'
            source.write_text(source_text,encoding='utf-8')
            doc = parse_document(source_text)
            doc['notes'] = notes(doc)
            profile = json.loads((ROOT/'assets/xlsx-style.json').read_text(encoding='utf-8'))
            selections = [None] + [list(c) for n in range(1,4) for c in itertools.combinations(['xlsx','html','markdown'],n)]
            for i, selected in enumerate(selections):
                with self.subTest(formats=selected):
                    out = base/str(i)
                    cmd = [sys.executable,'-B',str(ROOT/'scripts/export_tp.py'),str(source),'--out-dir',str(out)]
                    if selected:
                        cmd += ['--formats']+selected
                    result = subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
                    self.assertEqual(result.returncode,0,result.stderr)
                    expected = {'.md' if x=='markdown' else '.'+x for x in selected or ['xlsx']}
                    self.assertEqual({p.suffix for p in out.iterdir()},expected)
                    if '.xlsx' in expected:
                        self.assertEqual(verify(out/'case.xlsx',doc,profile),3)
                    if '.md' in expected:
                        self.assertEqual((out/'case.md').read_text(encoding='utf-8'),source_text)
                    if '.html' in expected:
                        self.assertIn('超长段落测试',(out/'case.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
