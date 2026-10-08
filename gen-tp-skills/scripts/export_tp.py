#!/usr/bin/env python3
"""Validate once, export only selected formats; default XLSX. No content rewriting."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from tp_contract import parse_document, ContractError, cells
from xlsx_check import verify

ROOT = Path(__file__).resolve().parents[1]


def formats(values=None):
    aliases = {'md': 'markdown', 'markdowm': 'markdown', 'xslx': 'xlsx'}
    result = []
    for value in values or ['xlsx']:
        for token in value.lower().split(','):
            token = aliases.get(token.strip(), token.strip())
            if token not in ('xlsx', 'html', 'markdown'):
                raise ValueError(f'不支持的输出格式: {token}')
            if token not in result:
                result.append(token)
    return result


def notes(document):
    """Preserve metadata and appendix text; turn table rows into labeled detail cells."""
    result = [['Document', 'title', document['title']]]
    result += [['Document', 'metadata', text] for text in document['meta']]
    counts = Counter(row[0] for row in document.get('rows', []))
    if counts:
        result += [['测试点统计', category, str(count)] for category, count in counts.items()]
        result.append(['测试点统计', '合计', str(sum(counts.values()))])
    section, headers, skip_section = '', None, False
    for line in document['appendix'].splitlines():
        if not line.strip():
            headers = None
            continue
        if re.match(r'^#{2,6} ', line):
            section = line.lstrip('#').strip()
            if line.startswith('## '):
                skip_section = bool(document.get('layout')) and section == '规格缺口'
            if skip_section:
                continue
            result.append([section, 'section', section])
            headers = None
        elif skip_section:
            continue
        elif line.startswith('|') and line.endswith('|'):
            row = cells(line)
            if all(re.fullmatch(r':?-{3,}:?', x) for x in row):
                continue
            if headers is None:
                headers = row
                # Retain the header even for an empty appendix table.
                result.append([section, 'table_columns', '\n'.join(row)])
            else:
                if len(row) != len(headers):
                    raise ValueError(f'附录表格列数不匹配: {line}')
                result.append([section, row[0], '\n'.join(f'{h}: {v}' for h, v in zip(headers[1:], row[1:]))])
        else:
            headers = None
            result.append([section, 'text', line])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Validated internal/working Markdown')
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--formats', nargs='+', help='xlsx html markdown; default xlsx')
    parser.add_argument('--name', help='Output stem, default input stem')
    parser.add_argument('--node', default=os.environ.get('TP_NODE', 'node'))
    parser.add_argument('--node-modules', default=os.environ.get('TP_NODE_MODULES'))
    parser.add_argument('--preview-dir', type=Path, help='Optional QA images, not final deliverables')
    parser.add_argument('--overwrite', action='store_true', help='Only use when replacing outputs is authorized')
    args = parser.parse_args()
    try:
        selected = formats(args.formats)
        text = args.source.read_text(encoding='utf-8-sig')
        document = parse_document(text)
        name = args.name or args.source.stem
        if not re.fullmatch(r'[^<>:"/\\|?*]+', name) or name in ('.', '..') or name.endswith(('.', ' ')):
            raise ValueError('输出名必须是有效的文件名，不包含路径')
        outputs = {fmt: args.out_dir / (name + ('.md' if fmt == 'markdown' else '.' + fmt)) for fmt in selected}
        for target in outputs.values():
            if target.exists() and target.resolve() != args.source.resolve() and not args.overwrite:
                raise ValueError(f'已存在输出，未覆盖: {target}')
        args.out_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='tp-export-') as temporary:
            stage = Path(temporary)
            working = stage / (name + '.md')
            working.write_text(text, encoding='utf-8')
            if 'xlsx' in selected:
                payload = dict(document, notes=notes(document))
                data = stage / 'plan.json'
                data.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
                cmd = [args.node, str(ROOT / 'scripts/gen_tp_xlsx.mjs'), str(data), str(stage / (name + '.xlsx'))]
                if args.node_modules:
                    cmd += ['--node-modules', args.node_modules]
                if args.preview_dir:
                    cmd += ['--preview-dir', str(args.preview_dir.resolve())]
                completed = subprocess.run(cmd)
                target = stage / (name + '.xlsx')
                receipt = target.with_suffix('.complete.json')
                native_teardown = os.name == 'nt' and (completed.returncode & 0xffffffff) == 0xC0000409
                if completed.returncode and not (native_teardown and receipt.exists()):
                    raise subprocess.CalledProcessError(completed.returncode, cmd)
                # An exit-code exception is accepted only after a completed write
                # receipt AND independent full field/appendix verification.
                verify(target, payload, json.loads((ROOT / 'assets/xlsx-style.json').read_text(encoding='utf-8')))
                if native_teardown:
                    print('NOTE: Windows renderer teardown exit 0xC0000409; completed XLSX independently verified.', file=sys.stderr)
            if 'html' in selected:
                subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT / 'scripts/gen_tp_html.py'), str(working)], check=True)
            # Only publish when all selected representations have been built successfully.
            for fmt, target in outputs.items():
                if target.resolve() == args.source.resolve():
                    continue
                shutil.copyfile(stage / target.name, target)
        print(json.dumps({'formats': selected, 'points': len(document['rows']), 'outputs': [str(p) for p in outputs.values()]}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, ContractError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    sys.exit(main())
