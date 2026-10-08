"""Tool contract regression tests; use unittest discovery from the skill root."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from tp_contract import ContractError, cells, parse_document


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / 'examples/demo_st_tp.md').read_text(encoding='utf-8')

    def test_planning_preserves_fields_and_escaped_pipe(self):
        doc = parse_document(self.text)
        self.assertEqual(len(doc['rows']), 3)
        self.assertEqual(doc['rows'][0][1:4], ['端到端传输', '合法长度', '-'])
        self.assertIn('|=>', doc['rows'][1][8])
        self.assertIn('DEMO-01/02/03', doc['appendix'])

    def test_duplicate_name_rejected(self):
        with self.assertRaisesRegex(ContractError, '重复'):
            parse_document(self.text.replace('demo_stable_002', 'demo_length_001'))

    def test_wrong_column_count_rejected(self):
        with self.assertRaisesRegex(ContractError, '列'):
            parse_document(self.text.replace('\\|=>', '|=>'))

    def test_statistics_and_total_both_checked(self):
        for old, new in [('总测试点数：3', '总测试点数：4'), ('| 数据传输 | 1 |', '| 数据传输 | 2 |')]:
            with self.subTest(old=old), self.assertRaises(ContractError):
                parse_document(self.text.replace(old, new))

    def changed_row(self, **fields):
        lines = self.text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith('| 数据传输 | 端到端传输 |'):
                row = cells(line)
                for index, value in fields.items():
                    row[int(index)] = value
                lines[i] = '| ' + ' | '.join(x.replace('\\', '\\\\').replace('|', '\\|') for x in row) + ' |'
                return '\n'.join(lines)
        self.fail('fixture row missing')

    def test_every_metric_requires_stimulus_independently_of_coverage(self):
        for kind in ['cg', 'cp', 'p', 't']:
            target = '[t] 待反填' if kind == 't' else f'[{kind}] 待设计:目标'
            with self.subTest(kind=kind):
                fields = {'11': target}
                doc = parse_document(self.changed_row(**fields))
                self.assertIn('配置：', doc['rows'][0][9])
                self.assertNotEqual(doc['rows'][0][8], '-')
                fields['9'] = '-'
                with self.assertRaisesRegex(ContractError, '第 10 列'):
                    parse_document(self.changed_row(**fields))

    def test_coverage_required_for_cg_cp_p_optional_for_t(self):
        for kind in ['cg', 'cp', 'p']:
            with self.subTest(kind=kind), self.assertRaisesRegex(ContractError, '第 9 列'):
                parse_document(self.changed_row(**{'8': '-', '11': f'[{kind}] 待设计:目标'}))
        doc = parse_document(self.changed_row(**{'8': '-', '11': '[t] 待反填'}))
        self.assertEqual(doc['rows'][0][8], '-')

    def test_unresolved_stimulus_retains_planning_point(self):
        stimulus = '配置：MODE=Normal；需要 check：模式编码缺失（Q1）<br>发起：业务请求；需要 check：接口名称（Q2）<br>预期：保留设计要求的完整输出；精确检查需要 check'
        doc = parse_document(self.changed_row(**{'9': stimulus}))
        self.assertEqual(len(doc['rows']), 3)
        self.assertEqual(doc['rows'][0][9], stimulus)

    def test_planning_targets_block_handoff(self):
        with self.assertRaisesRegex(ContractError, '交接前'):
            parse_document(self.text, 'handoff')

    def test_concrete_targets_allow_structural_handoff(self):
        text = self.text.replace('[cp] 待设计:长度边界', '[cp] env.cov.length_cg.length_cp')
        text = text.replace('[p] 待设计:反压稳定性', '[p] demo_if.stable_p')
        text = text.replace('[t] 待反填', '[t] demo_reset_vseq')
        self.assertEqual(len(parse_document(text, 'handoff')['rows']), 3)
        self.assertEqual(parse_document(text, 'handoff')['rows'][2][7], '待反填')

    def test_empty_template_and_legacy_layout_fail(self):
        for text in [(ROOT / 'assets/tp-template.md').read_text(encoding='utf-8'),
                     '# 旧格式\n## 功能\n**测试点：demo_test**\n| 字段 | 内容 |\n|---|---|']:
            with self.subTest(text=text[:20]), self.assertRaises(ContractError):
                parse_document(text)

    def test_fenced_fake_sections_are_not_parsed(self):
        fake = '\n```markdown\n## 测试点汇总表\n| fake |\n```\n'
        self.assertEqual(len(parse_document(self.text + fake)['rows']), 3)

    def test_nonunique_or_incomplete_header_rejected(self):
        with self.assertRaisesRegex(ContractError, '表头'):
            parse_document(self.text.replace('功能覆盖率描述(Optional)', '覆盖描述'))

    def test_renderer_preserves_hierarchy_and_escapes_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = Path(temporary) / '中文 空格.md', Path(temporary) / 'result.html'
            source.write_text(self.text + '\n<script>alert("x")</script>\n', encoding='utf-8')
            completed = subprocess.run([sys.executable, str(ROOT / 'scripts/gen_tp_html.py'), str(source), str(target)], capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            html = target.read_text(encoding='utf-8')
            self.assertEqual(html.count('class="tpname"'), 3)
            for value in ['端到端传输 / 合法长度', 'DEMO-01/02/03', '&lt;script&gt;', '待设计:长度边界', '$stable(data)', '需要 check：', '响应/推进：', '长度取1、8、16字节']:
                self.assertIn(value, html)
            self.assertNotIn('<script>alert', html)
            self.assertIn('id="anc_cat_0"', html)
            self.assertIn('data-t="anc_cat_0"', html)

    def test_failure_does_not_overwrite_existing_html_or_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = Path(temporary) / 'input.md', Path(temporary) / 'output.html'
            source.write_text('# 无表格\n', encoding='utf-8')
            target.write_text('KEEP', encoding='utf-8')
            completed = subprocess.run([sys.executable, str(ROOT / 'scripts/gen_tp_html.py'), str(source), str(target)], capture_output=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(target.read_text(encoding='utf-8'), 'KEEP')
            source.write_text(self.text, encoding='utf-8')
            completed = subprocess.run([sys.executable, str(ROOT / 'scripts/gen_tp_html.py'), str(source), str(source)], capture_output=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(source.read_text(encoding='utf-8'), self.text)

    def test_renderer_import_has_no_cli_side_effects(self):
        spec = importlib.util.spec_from_file_location('renderer', ROOT / 'scripts/gen_tp_html.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.parse))


if __name__ == '__main__':
    unittest.main()
