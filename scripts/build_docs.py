#!/usr/bin/env python3
"""把 docs/ 下的 Markdown 文件转成可直接用浏览器开的 HTML。

用意:部署手册的读者常常是在校内主机或机房、没有网络的情况下读文档。
.md 在 GitHub 网页上看是排版好的,但把文件夹复制到本机后只是纯文本;
生成的 .html 则可以双击打开、离线阅读,并带有侧边目录和深浅色切换。

**生成的 .html 一律不要手动编辑**——改 .md 之后重新运行本脚本即可。

用法:
    pip install markdown
    python scripts/build_docs.py            # 生成 / 更新全部 HTML
    python scripts/build_docs.py --check    # 只检查是否与 .md 同步(CI 用,不写档)

新增一份文件时,把它加进下方 GROUPS 即可。
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
import unicodedata
from pathlib import Path

try:
    import markdown
except ModuleNotFoundError:
    sys.exit("需要 markdown 软件包,请先执行:pip install markdown")

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
GITHUB_BLOB = "https://github.com/sine-io/Course_Scheduling_System/blob/main/docs/"

# 侧边栏的文档列表。(相对 docs/ 的 .md 路径,侧边栏显示的短标题)
GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "部署与运维手册",
        [
            ("deploy/README.md", "总览:从哪开始"),
            ("deploy/install.md", "安装指南"),
            ("deploy/upgrade.md", "升级指南"),
            ("deploy/backup.md", "备份与恢复"),
            ("deploy/https.md", "域名与 HTTPS"),
            ("deploy/faq.md", "常见问题 FAQ"),
        ],
    ),
    (
        "项目技术文档",
        [
            ("architecture.md", "架构设计"),
            ("roadmap.md", "路线图"),
            ("tasks.md", "开发任务卡"),
        ],
    ),
]

# 这两份是给开发者的规格与开发日志,在侧边栏标示出来,免得一般用户误入
DEV_DOCS = {"architecture.md", "roadmap.md", "tasks.md"}

CSS = """
  :root{
    --bg:#f5f7f7; --surface:#ffffff; --surface-2:#eef2f2; --surface-3:#e3e9e8;
    --text:#172221; --text-soft:#465654; --text-faint:#6d7c7a;
    --border:#d9e1e0; --border-strong:#bac8c6;
    --accent:#0f766e; --accent-2:#0b5f59; --accent-soft:#e4f3f1; --accent-line:#9dcfc9;
    --good:#397a32; --warn:#9a6700; --warn-soft:#fff3cd; --danger:#b42318; --danger-soft:#fee9e7;
    --info:#2563a6; --info-soft:#e8f1fb;
    --font-sans:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    --font-serif:"Noto Serif CJK SC","Songti SC","Source Han Serif SC",Georgia,serif;
    --font-mono:"SF Mono","Cascadia Code","Consolas","Courier New",monospace;
    --maxw:800px;
  }
  @media (prefers-color-scheme:dark){
    :root:not([data-theme="light"]){
      --bg:#111716; --surface:#18201f; --surface-2:#222c2b; --surface-3:#2c3837;
      --text:#edf4f3; --text-soft:#b1c0be; --text-faint:#879795;
      --border:#344240; --border-strong:#465856;
      --accent:#53c7ba; --accent-2:#82ddd3; --accent-soft:#173532; --accent-line:#28615b;
      --good:#8bcf78; --warn:#e2b34d; --warn-soft:#352a10; --danger:#ff8c82; --danger-soft:#3a1f1d;
      --info:#8cbcf0; --info-soft:#1b2b3c;
    }
  }
  :root[data-theme="dark"]{
    --bg:#111716; --surface:#18201f; --surface-2:#222c2b; --surface-3:#2c3837;
    --text:#edf4f3; --text-soft:#b1c0be; --text-faint:#879795;
    --border:#344240; --border-strong:#465856;
    --accent:#53c7ba; --accent-2:#82ddd3; --accent-soft:#173532; --accent-line:#28615b;
    --good:#8bcf78; --warn:#e2b34d; --warn-soft:#352a10; --danger:#ff8c82; --danger-soft:#3a1f1d;
    --info:#8cbcf0; --info-soft:#1b2b3c;
  }

  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-sans);
    line-height:1.78;font-size:16px;-webkit-font-smoothing:antialiased;letter-spacing:0}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  :focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}

  .shell{display:grid;grid-template-columns:292px minmax(0,1fr);max-width:1240px;margin:0 auto}

  /* ── sidebar ── */
  .side{position:sticky;top:0;align-self:start;height:100vh;overflow-y:auto;padding:26px 18px 40px;
    border-right:1px solid var(--border)}
  .brand{display:block;margin-bottom:4px}
  .brand .mark{font-family:var(--font-serif);font-weight:700;font-size:1.1rem;color:var(--accent);
    display:block}
  .brand .sub{font-size:.7rem;color:var(--text-faint);letter-spacing:0}
  .side .grp{margin-top:20px;font-size:.7rem;letter-spacing:0;color:var(--text-faint);
    text-transform:uppercase;font-family:var(--font-mono);padding:0 8px 6px}
  .side nav{display:flex;flex-direction:column;gap:1px}
  .side nav a{display:block;padding:6px 10px;border-radius:7px;color:var(--text-soft);
    font-size:.88rem;transition:background .15s,color .15s}
  .side nav a:hover{background:var(--surface-2);text-decoration:none;color:var(--text)}
  .side nav a.here{background:var(--accent-soft);color:var(--accent-2);font-weight:600}
  .side nav a .dev{font-size:.66rem;color:var(--text-faint);font-family:var(--font-mono);
    margin-left:6px;letter-spacing:0}

  /* 本页目录 */
  .side .toc{margin-top:6px;display:flex;flex-direction:column;gap:0;
    border-left:1px solid var(--border);padding-left:2px}
  .side .toc a{font-size:.82rem;padding:4px 10px;color:var(--text-soft);border-radius:0 6px 6px 0}
  .side .toc a.lv3{padding-left:24px;font-size:.78rem;color:var(--text-faint)}
  .side .toc a:hover{background:var(--surface-2);color:var(--text);text-decoration:none}
  .side .toc a.on{color:var(--accent-2);font-weight:600;box-shadow:inset 2px 0 0 var(--accent)}

  .theme-btn{margin-top:22px;width:100%;padding:8px;border:1px solid var(--border);
    background:var(--surface);color:var(--text-soft);border-radius:8px;cursor:pointer;
    font-size:.8rem;font-family:var(--font-sans)}
  .theme-btn:hover{border-color:var(--accent);color:var(--accent)}

  /* ── main ── */
  main{padding:0 clamp(20px,5vw,60px) 110px;min-width:0}
  .wrap{max-width:var(--maxw);margin:0 auto}

  .head{padding:52px 0 22px;border-bottom:1px solid var(--border);margin-bottom:8px}
  .eyebrow{font-family:var(--font-mono);font-size:.72rem;letter-spacing:0;text-transform:uppercase;
    color:var(--accent);margin-bottom:14px}
  h1{font-family:var(--font-serif);font-weight:700;font-size:2.25rem;line-height:1.22;
    margin:0;text-wrap:balance;letter-spacing:0}
  .src{margin-top:16px;font-size:.78rem;color:var(--text-faint)}
  .src code{font-size:.9em}

  h2{font-family:var(--font-serif);font-size:1.55rem;font-weight:700;margin:52px 0 12px;line-height:1.3;
    padding-bottom:8px;border-bottom:1px solid var(--border);text-wrap:balance;scroll-margin-top:16px}
  h3{font-size:1.12rem;font-weight:700;margin:34px 0 10px;letter-spacing:0;
    padding-left:12px;border-left:3px solid var(--accent);scroll-margin-top:16px}
  h4{font-size:1rem;font-weight:700;margin:24px 0 8px;color:var(--text);scroll-margin-top:16px}
  p{margin:14px 0}
  strong{font-weight:700;color:var(--text)}
  ul,ol{margin:14px 0;padding-left:1.4em}
  li{margin:6px 0}
  li > ul,li > ol{margin:6px 0}
  hr{border:none;border-top:1px solid var(--border);margin:34px 0}

  code{font-family:var(--font-mono);font-size:.86em;background:var(--surface-2);
    padding:2px 6px;border-radius:5px;color:var(--accent-2);word-break:break-word}
  pre{background:var(--surface-2);border:1px solid var(--border);border-radius:6px;
    padding:14px 16px;overflow-x:auto;margin:18px 0;line-height:1.6}
  pre code{background:none;padding:0;color:var(--text);font-size:.85rem;white-space:pre}

  blockquote{margin:20px 0;padding:12px 18px;border:1px solid var(--border);border-left:4px solid var(--accent);
    border-radius:6px;background:var(--accent-soft);color:var(--text-soft);font-size:.95rem}
  blockquote p{margin:6px 0}
  blockquote strong{color:var(--accent-2)}

  .tw{overflow-x:auto;margin:20px 0;border:1px solid var(--border);border-radius:8px}
  table{border-collapse:collapse;width:100%;font-size:.9rem;min-width:440px}
  th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--border);vertical-align:top}
  thead th{background:var(--surface-2);font-weight:700;font-size:.8rem;letter-spacing:0;
    color:var(--text-soft);white-space:nowrap}
  tbody tr:last-child td{border-bottom:none}
  td code{white-space:nowrap}

  /* tasks.md 的任务卡复选框 */
  .tick{display:inline-block;width:1.15em;margin-right:.35em;font-family:var(--font-mono);font-weight:700}
  .tick.done{color:var(--good)}
  .tick.wip{color:var(--warn)}
  .tick.todo{color:var(--text-faint)}

  .foot{margin-top:70px;padding-top:24px;border-top:1px solid var(--border);color:var(--text-faint);
    font-size:.83rem}
  .foot a{color:var(--text-soft)}

  .navtoggle{display:none}
  @media (max-width:960px){
    .shell{grid-template-columns:1fr}
    .side{position:fixed;z-index:40;top:0;left:0;width:284px;transform:translateX(-100%);
      transition:transform .22s ease;background:var(--surface);height:100vh}
    .side.open{transform:none;box-shadow:0 0 40px rgba(0,0,0,.34)}
    .navtoggle{display:flex;position:fixed;z-index:50;top:14px;left:14px;gap:8px;align-items:center;
      background:var(--surface);border:1px solid var(--border-strong);border-radius:8px;padding:8px 13px;
      cursor:pointer;font-family:var(--font-sans);color:var(--text);font-size:.85rem;font-weight:600}
    .scrim{display:none;position:fixed;inset:0;z-index:39;background:rgba(0,0,0,.45)}
    .scrim.on{display:block}
    .head{padding-top:56px}
    h1{font-size:1.8rem}
  }
  @media (prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
  @media print{.side,.navtoggle,.scrim{display:none}.shell{grid-template-columns:1fr}
    main{padding:0}pre,blockquote,.tw{break-inside:avoid}}
  html{scroll-behavior:smooth}
"""

JS = """
  (function(){
    var root=document.documentElement, btn=document.getElementById('themeBtn');
    // 跨页记住深/浅色:读者在部署手册里是会一页一页翻的
    try{var s=localStorage.getItem('csDocsTheme'); if(s)root.setAttribute('data-theme',s);}catch(e){}
    function cur(){var d=root.getAttribute('data-theme');if(d)return d;
      return matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light';}
    btn.addEventListener('click',function(){
      var next=cur()==='dark'?'light':'dark';
      root.setAttribute('data-theme',next);
      try{localStorage.setItem('csDocsTheme',next);}catch(e){}
    });

    var side=document.getElementById('side'), scrim=document.getElementById('scrim'),
        tog=document.getElementById('navToggle');
    function close(){side.classList.remove('open');scrim.classList.remove('on');}
    tog.addEventListener('click',function(){side.classList.toggle('open');scrim.classList.toggle('on');});
    scrim.addEventListener('click',close);

    var links=Array.prototype.slice.call(document.querySelectorAll('.toc a'));
    links.forEach(function(a){a.addEventListener('click',function(){
      if(window.innerWidth<=960)close();});});
    var secs=links.map(function(a){return document.getElementById(
      decodeURIComponent(a.getAttribute('href').slice(1)));});
    function spy(){
      var best=-1;
      for(var i=0;i<secs.length;i++){
        if(secs[i]&&secs[i].getBoundingClientRect().top<=120)best=i;
      }
      links.forEach(function(a,i){a.classList.toggle('on',i===best);});
    }
    addEventListener('scroll',spy,{passive:true});spy();
  })();
"""


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# tasks.md 用 `### [x] M0-1 …` 在标题上标任务状态
TICKS = {" ": ("todo", "☐"), "~": ("wip", "◐"), "x": ("done", "☑")}
TICK_RE = re.compile(r"^\[([ ~x])\]\s*")


def slugify(value: str, separator: str) -> str:
    """生成保留中文的锚点,规则与 GitHub 一致,同一个 #锚点 在 .md 与 .html 都可用。

    python-markdown 内置的 slugify 会把非 ASCII 全部丢掉,中文标题会退化成
    #_1、#_2 这种序号——一旦中间插入新章节,所有已有链接就会失效。
    """
    value = TICK_RE.sub("", value.strip())
    value = unicodedata.normalize("NFKC", value).lower()
    value = re.sub(r"[^\w\s-]", "", value)  # \w 在 unicode 模式下含中日韩
    return re.sub(r"\s+", separator, value.strip())


def md_to_html(text: str) -> tuple[str, str, list]:
    """返回 (标题,正文 HTML,TOC tokens)。第一个 # 标题作为页首,不在正文重复显示。"""
    lines = text.splitlines()
    title = ""
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            lines = lines[i + 1:]
            break
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
        extension_configs={"toc": {"permalink": False, "slugify": slugify}},
    )
    body = md.convert("\n".join(lines).strip())
    return title, body, md.toc_tokens


def rewrite_links(html: str) -> str:
    """把指向 .md 的相对链接改为生成的 .html,外部链接保持不变。"""

    def sub(m: re.Match) -> str:
        href = m.group(1)
        if href.startswith(("http://", "https://", "mailto:", "#")):
            return m.group(0)
        return 'href="%s"' % re.sub(r"\.md(?=$|#)", ".html", href)

    return re.sub(r'href="([^"]*)"', sub, html)


def wrap_tables(html: str) -> str:
    """为表格增加横向滚动容器,避免窄屏把整页撑开。"""
    return html.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")


def render_ticks(html: str) -> str:
    """把 tasks.md 标题和列表中的 [ ] / [~] / [x] 转为有颜色的状态标记。"""

    def sub(m: re.Match) -> str:
        cls, glyph = TICKS[m.group(2)]
        return '%s<span class="tick %s">%s</span> ' % (m.group(1), cls, glyph)

    return re.sub(r"(<(?:li|h[2-4])\b[^>]*>)\[([ ~x])\]\s*", sub, html)


def build_toc(tokens: list, out: list | None = None) -> list:
    """展开 h2 / h3 作为侧边目录;h1 已作为页首,忽略更深层级。"""
    out = [] if out is None else out
    for t in tokens:
        if t["level"] in (2, 3):
            name = t["name"]
            mark = TICK_RE.match(name)
            out.append((t["level"], t["id"], TICK_RE.sub("", name), mark.group(1) if mark else None))
        if t["level"] < 3:
            build_toc(t["children"], out)
    return out


def link_to(target: str, current: str) -> str:
    """生成从 current 页面到 target 的链接(均为相对 docs/ 的路径)。"""
    return posixpath.relpath(target, posixpath.dirname(current)) or target


def nav_html(current: str) -> str:
    home = link_to("index.html", current)
    parts = [
        '<a class="brand" href="%s">'
        '<span class="mark">学校排课系统</span>'
        '<span class="sub">文档</span></a>' % home,
        '<div class="grp">用户文档</div><nav>',
        '<a href="%s">排课管理员操作手册</a>' % home,
        "</nav>",
    ]
    for group, items in GROUPS:
        parts.append('<div class="grp">%s</div><nav>' % esc(group))
        for rel, label in items:
            here = " here" if rel == current else ""
            dev = '<span class="dev">开发用</span>' if rel in DEV_DOCS else ""
            parts.append(
                '<a class="doc%s" href="%s">%s%s</a>'
                % (here, link_to(rel.replace(".md", ".html"), current), esc(label), dev)
            )
        parts.append("</nav>")
    return "\n".join(parts)


def toc_html(toc: list) -> str:
    if not toc:
        return ""
    rows = []
    for lv, tid, name, mark in toc:
        tick = ""
        if mark is not None:
            cls, glyph = TICKS[mark]
            tick = '<span class="tick %s">%s</span>' % (cls, glyph)
        rows.append(
            '<a class="%s" href="#%s">%s%s</a>'
            % ("lv3" if lv == 3 else "lv2", tid, tick, esc(name))
        )
    return '<div class="grp">本页目录</div><div class="toc">%s</div>' % "".join(rows)


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{desc}">
<title>{title} · 学校排课系统</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='88'>{icon}</text></svg>">
<!-- 本文件由 scripts/build_docs.py 从 docs/{src} 自动生成,请勿直接编辑。 -->
<style>{css}</style>
</head>
<body>
<button class="navtoggle" id="navToggle" aria-label="开启目录">☰ 目录</button>
<div class="scrim" id="scrim"></div>
<div class="shell">
  <aside class="side" id="side">
{nav}
{toc}
    <button class="theme-btn" id="themeBtn">◐ 切换深色 / 浅色</button>
  </aside>
  <main>
    <div class="wrap">
      <header class="head">
        <div class="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <div class="src">源文件 <code>docs/{src}</code> · <a href="{blob}">在 GitHub 上查看</a></div>
      </header>
{body}
      <div class="foot">
        本页由 <code>docs/{src}</code> 自动生成(<code>scripts/build_docs.py</code>)。
        要修改内容请编辑 Markdown 源文件,不要直接编辑这份 HTML。<br>
        学校排课系统 · MIT 授权 · <a href="https://github.com/sine-io/Course_Scheduling_System">GitHub</a>
      </div>
    </div>
  </main>
</div>
<script>{js}</script>
</body>
</html>
"""


def render(rel: str) -> str:
    src = DOCS / rel
    title, body, tokens = md_to_html(src.read_text(encoding="utf-8"))
    body = render_ticks(wrap_tables(rewrite_links(body)))
    body = "\n".join("      " + ln for ln in body.splitlines())
    dev = rel in DEV_DOCS
    html = PAGE.format(
        title=esc(title),
        desc=esc("%s — 学校排课系统%s文档" % (title, "开发" if dev else "部署与运维")),
        icon="D" if dev else "M",
        eyebrow="DEVELOPER DOCS" if dev else "DEPLOYMENT GUIDE",
        css=CSS,
        js=JS,
        nav=nav_html(rel),
        toc=toc_html(build_toc(tokens)),
        body=body,
        src=rel,
        blob=GITHUB_BLOB + rel,
    )
    # Markdown 可能把空段落渲染成只含缩进的行，提交前统一清理行尾空白。
    return "\n".join(line.rstrip() for line in html.splitlines()) + "\n"


def main() -> int:
    # Windows 控制台默认编码可能无法输出中文和 ✓
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="把 docs/ 的 Markdown 转成 HTML")
    ap.add_argument("--check", action="store_true", help="只检查是否同步,不写档(CI 用)")
    args = ap.parse_args()

    stale, written = [], []
    for _, items in GROUPS:
        for rel, _ in items:
            out = DOCS / rel.replace(".md", ".html")
            html = render(rel)
            if args.check:
                if not out.exists() or out.read_text(encoding="utf-8") != html:
                    stale.append(rel)
            else:
                if not out.exists() or out.read_text(encoding="utf-8") != html:
                    out.write_text(html, encoding="utf-8", newline="\n")
                    written.append(out.relative_to(REPO).as_posix())

    if args.check:
        if stale:
            print("以下文件的 HTML 未与 Markdown 同步:")
            for rel in stale:
                print("  - docs/%s" % rel)
            print("\n请执行 python scripts/build_docs.py 后一并提交。")
            return 1
        print("docs HTML 与 Markdown 同步 ✓")
        return 0

    print("更新 %d 份(共 %d 份)" % (len(written), sum(len(i) for _, i in GROUPS)))
    for w in written:
        print("  ✓ " + w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
