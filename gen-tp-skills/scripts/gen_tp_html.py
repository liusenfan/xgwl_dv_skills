#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_tp_html.py — 将 <module>_<xt>_tp.md 场景测试点文档转换为单表分级 HTML（gen-tp-skills；视觉框架派生自 ubench-tp-gen）
用法: python3 gen_tp_html.py <module>_<xt>_tp.md [输出html，默认同名 .html]
呈现: 所有测试点在一个表格中，一级(测试需求)/二级(子需求)/三级(测试点)三列分级；
      一级/二级合并单元格标题居左上角、点击可收起/展开（折叠后按可见行重算 rowspan）；
      table-layout:fixed 适配整屏；搜索高亮定位；待反填/预留/度量彩色徽标。
"""
import re, sys, html as H

import argparse
from pathlib import Path
from tp_contract import parse_document, ContractError

FIELD_ORDER = ["测试点描述", "需求 ID", "关联用例", "功能覆盖率描述",
               "直接用例激励描述", "环境检查说明", "度量测试点覆盖", "标签"]
COL_TITLE   = ["一级（测试需求）", "二级（子需求）", "#", "三级（测试点）",
               "测试点描述", "需求 ID", "关联用例", "功能覆盖率描述",
               "直接用例激励描述", "环境检查说明", "度量", "标签"]
COL_WIDTH   = ["6.5%", "7%", "2.2%", "9.5%", "18%", "4.8%",
               "5.5%", "13.5%", "6%", "11.5%", "9%", "6%"]

def inline(s):
    s = H.escape(s.strip()).replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = s.replace("待反填", '<span class="badge pend">待反填</span>')
    s = re.sub(r"(【预留[^】]*】)", r'<span class="badge rsv">\1</span>', s)
    s = re.sub(r"\[(t|cp|cg|p)\]", r'<span class="badge m-\1">[\1]</span>', s)
    return s

def parse(md_text):
    document = parse_document(md_text)
    cats, categories = [], {}
    for row in document["rows"]:
        cat_name = row[0]
        if cat_name not in categories:
            categories[cat_name] = {"title": cat_name, "blocks": [], "subs": [], "tps": []}
            cats.append(categories[cat_name])
        cat = categories[cat_name]
        sub_name = " / ".join(value for value in row[1:4] if value != "-")
        sub = next((entry for entry in cat["subs"] if entry["title"] == sub_name), None)
        if sub is None:
            sub = {"title": sub_name, "blocks": [], "tps": []}
            cat["subs"].append(sub)
        sub["tps"].append({"name": row[4], "fields": dict(zip(FIELD_ORDER, row[5:]))})
    if document["appendix"].strip():
        cats.append({"title": "来源、缺口与能力交接", "subs": [], "tps": [],
                     "blocks": [("raw", [document["appendix"]])]})
    return document["meta"], cats

def render_table(tbl):
    rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tbl]
    rows = [r for r in rows if not (r and set("".join(r)) <= set("-: "))]
    if not rows: return ""
    out = ['<table class="plain">',
           "<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>"]
    for r in rows[1:]:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)

def render_blocks(blocks):
    out = []
    for kind, body in blocks:
        if kind == "raw": out.append('<pre style="white-space:pre-wrap;overflow-wrap:anywhere">' + H.escape(body[0]) + '</pre>')
        elif kind == "table": out.append(render_table(body))
        elif kind == "quote":
            out.append("<blockquote>" + "<br>".join(inline(x) for x in body if x.strip()) + "</blockquote>")
        elif kind == "list":
            items = "".join(f"<li>{inline(re.sub(chr(92)+'s*-'+chr(92)+'s?', '', x, count=1))}</li>" for x in body)
            out.append(f"<ul>{items}</ul>")
        else:
            out.append(f"<p>{inline(body[0])}</p>")
    return "\n".join(out)

def flatten(cats):
    """展平为 (cat_idx, 一级, sub_idx, 二级, tp) 序列。"""
    rows = []
    for ci, cat in enumerate(cats):
        for tp in cat["tps"]:
            rows.append((ci, cat["title"], -1, "-", tp))
        for si, sub in enumerate(cat["subs"]):
            for tp in sub["tps"]:
                rows.append((ci, cat["title"], si, sub["title"], tp))
    return rows

def render_big_table(rows):
    n = len(rows)
    cat_span, sub_span = [0]*n, [0]*n
    i = 0
    while i < n:
        j = i
        while j < n and rows[j][0] == rows[i][0]: j += 1
        cat_span[i] = j - i; i = j
    i = 0
    while i < n:
        j = i
        while j < n and rows[j][0] == rows[i][0] and rows[j][2] == rows[i][2]: j += 1
        sub_span[i] = j - i; i = j
    out = ['<table class="tp">',
           "<colgroup>" + "".join(f'<col style="width:{w}">' for w in COL_WIDTH) + "</colgroup>",
           '<thead><tr>' + "".join(f"<th>{c}</th>" for c in COL_TITLE) + "</tr></thead><tbody>"]
    for idx, (ci, cat, si, sub, tp) in enumerate(rows):
        ck, sk = f"c{ci}", f"c{ci}_s{si}"
        attrs = [f'class="tprow{" catfirst" if cat_span[idx] else ""}"',
                 f'data-cat="{ck}"', f'data-sub="{sk}"']
        if cat_span[idx]: attrs.append("data-catfirst")
        if sub_span[idx]: attrs.append("data-subfirst")
        cells = []
        if cat_span[idx]:
            aid = f"cat_{ci}"
            cells.append(f'<td class="lv1" rowspan="{cat_span[idx]}" id="anc_{aid}" data-g="{ck}" '
                         f'title="点击收起/展开"><span class="tg">▼</span>{inline(cat)}'
                         f'<span class="gcnt">{cat_span[idx]}</span></td>')
        if sub_span[idx]:
            cells.append(f'<td class="lv2" rowspan="{sub_span[idx]}" data-g="{sk}" '
                         f'title="点击收起/展开"><span class="tg">▼</span>{inline(sub)}</td>')
        f = tp["fields"]
        cells.append(f'<td class="num"><div class="c">{idx+1}</div></td>')
        cells.append(f'<td class="l3"><div class="c"><b class="tpname">{H.escape(tp["name"])}</b></div></td>')
        cells += [f'<td><div class="c">{inline(f.get(k, "-"))}</div></td>' for k in FIELD_ORDER]
        out.append(f'<tr {" ".join(attrs)}>' + "".join(cells) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path)
    parser.add_argument("output", nargs="?", type=Path)
    args = parser.parse_args()
    MD = args.markdown
    OUT = args.output or MD.with_suffix(".html")
    if MD.resolve() == OUT.resolve() or (OUT.exists() and MD.samefile(OUT)):
        raise ContractError("HTML 输出不能覆盖输入文档")
    if OUT.suffix.lower() != ".html":
        raise ContractError("输出扩展名必须为 .html")
    md = MD.read_text(encoding="utf-8-sig")
    title = parse_document(md)["title"]
    meta, cats = parse(md)
    rows = flatten(cats)
    total = len(rows)
    # 顶部不再放测试点数统计表（左侧导航已带各类计数，页尾有合计）
    nav = []
    for ci, cat in enumerate(cats):
        cnt = len(cat["tps"]) + sum(len(s["tps"]) for s in cat["subs"])
        if cnt:
            aid = f"cat_{ci}"
            nav.append(f'<a data-t="anc_{aid}">{inline(cat["title"])}<span class="ncnt">{cnt}</span></a>')
    appendix = []
    for cat in cats:
        blocks = list(cat["blocks"]) + [b for s in cat["subs"] for b in s["blocks"]]
        has_tp = len(cat["tps"]) + sum(len(s["tps"]) for s in cat["subs"])
        if blocks and (not has_tp or any(k == "table" for k, _ in blocks)):
            appendix.append(f'<details class="apx"><summary>{inline(cat["title"])}（说明/清单）</summary>')
            appendix.append(render_blocks(cat["blocks"]))
            for s in cat["subs"]:
                if s["blocks"]:
                    appendix.append(f'<h4>{inline(s["title"])}</h4>')
                    appendix.append(render_blocks(s["blocks"]))
            appendix.append("</details>")
    css = """
body{font-family:'PingFang SC','Microsoft YaHei',sans-serif;margin:0;background:#f5f6f8;color:#222}
.wrap{max-width:none;margin:0;padding:12px 14px 50px}
h1{font-size:20px;border-bottom:3px solid #2b6cb0;padding-bottom:6px;margin:6px 0 10px}
.meta{background:#eef4fb;border-left:4px solid #2b6cb0;padding:6px 12px;border-radius:4px;font-size:12px;line-height:1.6}
table{border-collapse:collapse;width:100%;font-size:11.5px;margin:8px 0}
th,td{border:1px solid #cfd6df;padding:4px 5px;vertical-align:top;text-align:left;word-break:break-word;overflow-wrap:anywhere}
thead th{background:#1a365d;color:#fff;position:sticky;top:0;z-index:2;font-size:11.5px}
table.tp{table-layout:fixed}
table.tp td.lv1{background:#e8f0fa;font-weight:700;color:#1a365d;vertical-align:top;text-align:left;cursor:pointer;user-select:none}
table.tp td.lv2{background:#f3f7fc;font-weight:600;color:#2b6cb0;vertical-align:top;text-align:left;cursor:pointer;user-select:none}
table.tp td.num{color:#999}
.tg{display:inline-block;width:13px;color:#2b6cb0;font-size:10px;margin-right:2px}
.gcnt{display:inline-block;background:#2b6cb0;color:#fff;border-radius:8px;font-size:10px;padding:0 6px;margin-left:5px;font-weight:600}
table.tp tr.catfirst td{border-top:2px solid #2b6cb0}
table.tp tbody tr:hover td{background-color:#fff7e0}
.tpname{color:#153e75;font-family:Menlo,Consolas,monospace;font-size:10.5px;word-break:break-all}
tr.fold-c td .c,tr.fold-s td .c{display:none}
tr.fold-c td.l3::after,tr.fold-s td.l3::after{content:attr(data-note);color:#a0a6b0;font-size:10.5px}
table.plain{table-layout:auto}
table.plain thead th{background:#f0f3f7;color:#1a365d;position:static}
code{background:#f0f2f5;border:1px solid #e0e3e8;border-radius:3px;padding:0 3px;font-size:11px}
blockquote{background:#fffbe8;border-left:4px solid #ecc94b;margin:8px 0;padding:6px 10px;font-size:12px;border-radius:4px}
ul{margin:6px 0;padding-left:20px;font-size:12.5px;line-height:1.6}
.badge{display:inline-block;border-radius:3px;padding:0 4px;font-size:10px;font-weight:600}
.badge.pend{background:#fde8c8;color:#9c4b00;border:1px solid #f0b060}
.badge.rsv{background:#e8e8ec;color:#555;border:1px solid #c8c8d0}
.badge.m-t{background:#d9f0dc;color:#116329;border:1px solid #8fce9c}
.badge.m-cp{background:#dbe9fb;color:#0b4a8f;border:1px solid #90b8e8}
.badge.m-cg{background:#e8dbfb;color:#5521a5;border:1px solid #bb98ee}
.badge.m-p{background:#fbdbe9;color:#8f0b4a;border:1px solid #e890b8}
#q{width:340px;padding:5px 10px;border:1px solid #c5cdd8;border-radius:6px;font-size:12.5px;margin:8px 8px 8px 0}
#qinfo{font-size:12px;color:#666}
.btn{font-size:12px;padding:4px 10px;border:1px solid #9db6d4;border-radius:6px;background:#fff;color:#2b6cb0;cursor:pointer;margin-right:6px}
tr.hit td{background:#fff3bf!important}
tr.dim td{opacity:.35}
details.apx{background:#fff;border:1px solid #d8dee6;border-radius:8px;margin:10px 0;padding:0 12px 8px}
details.apx>summary{font-size:14px;font-weight:700;color:#1a365d;padding:8px 0;cursor:pointer}
h4{margin:8px 0 4px;color:#2b6cb0;font-size:13px}
h2{color:#1a365d;font-size:16px}
/* 左侧一级需求导航（可隐藏） */
nav.side{position:fixed;left:0;top:0;bottom:0;width:220px;overflow-y:auto;background:#1a365d;
         padding:12px 0;box-sizing:border-box;z-index:9;transition:transform .18s}
nav.side.hide{transform:translateX(-220px)}
nav.side .tt{color:#fff;font-weight:700;font-size:13px;padding:0 14px 8px;border-bottom:1px solid rgba(255,255,255,.15);margin-bottom:6px}
nav.side a{display:flex;justify-content:space-between;align-items:center;color:#c3d4ea;text-decoration:none;
           font-size:12.5px;padding:5px 14px;border-left:3px solid transparent;cursor:pointer}
nav.side a:hover{background:rgba(255,255,255,.08);color:#fff}
nav.side a.on{background:rgba(255,255,255,.12);color:#fff;border-left-color:#63b3ed}
nav.side .ncnt{background:rgba(255,255,255,.18);border-radius:8px;font-size:10.5px;padding:0 6px;margin-left:6px}
#navToggle{position:fixed;left:220px;top:8px;z-index:11;background:#1a365d;color:#fff;border:none;
           border-radius:0 6px 6px 0;font-size:12px;padding:5px 8px;cursor:pointer;transition:left .18s}
#navToggle.hide{left:0}
.wrap{margin-left:220px;transition:margin-left .18s}
.wrap.full{margin-left:0}
"""
    js = """
function rowsOf(sel){return Array.prototype.slice.call(document.querySelectorAll(sel));}
function setNote(row,txt){var l3=row.querySelector('td.l3');if(l3)l3.setAttribute('data-note',txt);}
/* 折叠后按可见行数重算 rowspan，避免隐藏行后合并单元格跨入后续类别（错位根因） */
function refreshSpans(){
  document.querySelectorAll('td.lv1[data-g]').forEach(function(c){
    var g=c.getAttribute('data-g');
    var vis=rowsOf('tr[data-cat="'+g+'"]').filter(function(r){return r.style.display!=='none';}).length;
    c.rowSpan=Math.max(vis,1);
  });
  document.querySelectorAll('td.lv2[data-g]').forEach(function(c){
    var g=c.getAttribute('data-g');
    var vis=rowsOf('tr[data-sub="'+g+'"]').filter(function(r){return r.style.display!=='none';}).length;
    c.rowSpan=Math.max(vis,1);
  });
}
function foldCat(cell){
  var g=cell.getAttribute('data-g'),fold=cell.classList.toggle('folded');
  rowsOf('tr[data-cat="'+g+'"]').forEach(function(r){
    if(r.hasAttribute('data-catfirst')){r.classList.toggle('fold-c',fold);setNote(r,fold?'（一级已收起，点击左侧标题展开）':'');}
    else r.style.display=fold?'none':'';
  });
  if(!fold){ /* 展开一级时重置其内二级折叠 */
    rowsOf('tr[data-cat="'+g+'"]').forEach(function(r){r.classList.remove('fold-s');setNote(r,'');});
    document.querySelectorAll('td.lv2.folded[data-g^="'+g+'_"]').forEach(function(s){
      s.classList.remove('folded');var t=s.querySelector('.tg');if(t)t.textContent='\\u25BC';});
  }
  var t=cell.querySelector('.tg');if(t)t.textContent=fold?'\u25B6':'\u25BC';
  refreshSpans();
}
function foldSub(cell){
  var g=cell.getAttribute('data-g'),fold=cell.classList.toggle('folded');
  rowsOf('tr[data-sub="'+g+'"]').forEach(function(r){
    if(r.hasAttribute('data-subfirst')){r.classList.toggle('fold-s',fold);setNote(r,fold?'（二级已收起，点击左侧子需求展开）':'');}
    else r.style.display=fold?'none':'';
  });
  var t=cell.querySelector('.tg');if(t)t.textContent=fold?'\u25B6':'\u25BC';
  refreshSpans();
}
document.querySelectorAll('td.lv1').forEach(function(c){c.addEventListener('click',function(){foldCat(c);});});
document.querySelectorAll('td.lv2').forEach(function(c){c.addEventListener('click',function(){foldSub(c);});});
document.getElementById('btnAll').addEventListener('click',function(){
  document.querySelectorAll('td.lv1.folded').forEach(function(c){foldCat(c);});
  document.querySelectorAll('td.lv2.folded').forEach(function(c){foldSub(c);});
});
document.getElementById('btnNone').addEventListener('click',function(){
  document.querySelectorAll('td.lv1:not(.folded)').forEach(function(c){foldCat(c);});
});
var q=document.getElementById('q'),info=document.getElementById('qinfo');
q.addEventListener('input',function(){
  var k=this.value.trim().toLowerCase(),n=0,first=null;
  rowsOf('tr.tprow').forEach(function(r){
    r.classList.remove('hit','dim');
    if(!k)return;
    if(r.textContent.toLowerCase().indexOf(k)>=0){r.classList.add('hit');if(!first)first=r;n++;}
    else r.classList.add('dim');
  });
  info.textContent=k?('命中 '+n+' 条'):'';
  if(first)first.scrollIntoView({block:'center'});
});
/* 左侧一级需求导航：点击滚动定位（不用 #hash，兼容 iframe srcdoc）+ 滚动高亮 + 显示/隐藏 */
var nav=document.getElementById('sideNav'),wrap=document.getElementById('wrap'),
    tg=document.getElementById('navToggle'),navAs=nav?nav.querySelectorAll('a'):[];
navAs.forEach(function(a){a.addEventListener('click',function(){
  var el=document.getElementById(a.dataset.t);
  if(el)el.scrollIntoView({block:'start'});});});
function navHi(){
  var cur=null;
  navAs.forEach(function(a){var el=document.getElementById(a.dataset.t);
    if(el&&el.getBoundingClientRect().top<=90)cur=a;});
  navAs.forEach(function(a){a.classList.toggle('on',a===cur);});
}
document.addEventListener('scroll',navHi);navHi();
tg.addEventListener('click',function(){
  var h=nav.classList.toggle('hide');
  tg.classList.toggle('hide',h);wrap.classList.toggle('full',h);
  tg.textContent=h?'\u25B6 目录':'\u25C0 隐藏';
});
"""
    html_doc = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>{H.escape(title)}</title><style>{css}</style></head>
<body>
<nav class="side" id="sideNav"><div class="tt">测试需求导航</div>{"".join(nav)}</nav>
<button id="navToggle">\u25C0 隐藏</button>
<div class="wrap" id="wrap">
<h1>{H.escape(title)}</h1>
<div class="meta">{"<br>".join(inline(x) for x in meta)}</div>
<div>
<input id="q" type="search" placeholder="搜索测试点（高亮定位）">
<button class="btn" id="btnAll">全部展开</button>
<button class="btn" id="btnNone">全部收起</button>
<span id="qinfo"></span>
</div>
{render_big_table(rows)}
<h2>附录（非测试点内容）</h2>
{"".join(appendix)}
<p style="color:#999;font-size:11px">由 gen_tp_html.py 从 {H.escape(str(MD))} 自动生成 · 测试点合计 {total}（单表分级：一级/二级/三级，点击一级/二级标题可收起展开）</p>
</div><script>{js}</script></body></html>"""
    OUT.write_text(html_doc, encoding="utf-8")
    print(f"OK: {OUT} (rows={total})")

if __name__ == "__main__":
    try:
        main()
    except (OSError, UnicodeError, ContractError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
