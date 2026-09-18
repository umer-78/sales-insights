"""A self-contained HTML report: charts embedded, no assets to lose."""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sales report — {period}</title>
<style>
 :root {{ color-scheme: light dark; --bg:#f6f7f9; --card:#fff; --text:#16181d; --muted:#5d6573; --line:#dde1e8; --accent:#2563eb; }}
 @media (prefers-color-scheme: dark) {{ :root {{ --bg:#0e1116; --card:#161a21; --text:#e8eaee; --muted:#9aa3b2; --line:#2a303b; --accent:#60a5fa; }} }}
 body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
 .wrap {{ max-width:900px; margin:0 auto; padding:32px 16px 64px; }}
 h1 {{ font-size:24px; margin:0 0 4px; }} h2 {{ font-size:17px; margin:28px 0 10px; }}
 .muted {{ color:var(--muted); }}
 .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:18px 0; }}
 .kpi {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px; }}
 .kpi .k {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }}
 .kpi .v {{ font-size:22px; font-weight:650; }}
 .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; margin-bottom:16px; }}
 img {{ width:100%; height:auto; border-radius:8px; }}
 table {{ width:100%; border-collapse:collapse; font-size:14px; }}
 th,td {{ text-align:right; padding:7px 8px; border-bottom:1px solid var(--line); }}
 th:first-child, td:first-child {{ text-align:left; }}
 th {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }}
 footer {{ margin-top:28px; color:var(--muted); font-size:13px; }}
 @media print {{ body {{ background:#fff; }} .card {{ break-inside:avoid; }} }}
</style></head>
<body><div class="wrap">
<h1>Sales report</h1>
<p class="muted">{period} · generated {generated}</p>
<div class="kpis">{kpis}</div>
{sections}
<footer>{footer}</footer>
</div></body></html>"""


def _img(path: str | Path) -> str:
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return f'<img alt="chart" src="data:image/png;base64,{data}">'


def _table(df, index_name: str = "") -> str:
    frame = df.reset_index()
    head = "".join(f"<th>{str(c).replace('_', ' ')}</th>" for c in frame.columns)
    rows = []
    for _, row in frame.iterrows():
        cells = "".join(
            f"<td>{v:,.0f}</td>" if isinstance(v, (int, float)) and abs(v) >= 1000
            else f"<td>{v}</td>" for v in row
        )
        rows.append(f"<tr>{cells}</tr>")
    del index_name
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def build_report(path: str | Path, *, period: str, kpis: dict, charts: dict, tables: dict,
                 footer: str = "") -> Path:
    kpi_html = "".join(
        f'<div class="kpi"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in kpis.items())
    sections = []
    for title, chart in charts.items():
        sections.append(f'<h2>{title}</h2><div class="card">{_img(chart)}</div>')
    for title, table in tables.items():
        sections.append(f'<h2>{title}</h2><div class="card">{_table(table)}</div>')
    html = TEMPLATE.format(
        period=period, generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        kpis=kpi_html, sections="".join(sections), footer=footer)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(html, encoding="utf-8")
    return Path(path)
