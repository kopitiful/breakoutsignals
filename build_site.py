"""Generate docs/index.html with tabs for all 4 markets."""

import csv
import shutil
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
SIGNALS_DIR = BASE / "signals" / "output"
CHARTS_SRC  = SIGNALS_DIR / "charts"
DOCS_DIR    = BASE / "docs"
CHARTS_DST  = DOCS_DIR / "charts"

DOCS_DIR.mkdir(exist_ok=True)
CHARTS_DST.mkdir(exist_ok=True)

MARKETS = [
    ("europa",  "Europa"),
    ("nasdaq",  "Nasdaq 100"),
    ("sp500",   "S&P 500"),
    ("russell", "Russell 2000"),
]


def _latest_csv(market: str):
    csvs = sorted(SIGNALS_DIR.glob(f"signals_{market}_*.csv"))
    return csvs[-1] if csvs else None


def _find_chart(ticker: str, pattern_type: str) -> str | None:
    stem = f"{ticker}_{pattern_type}"
    matches = sorted(CHARTS_DST.glob(f"{stem}*.png"))
    return f"charts/{matches[-1].name}" if matches else None


def _score_class(score: str) -> str:
    try:
        s = float(score)
        if s >= 70:
            return "hi"
        if s >= 50:
            return "mid"
    except (ValueError, TypeError):
        pass
    return ""


def _fmt(val: str, decimals: int = 2) -> str:
    try:
        return f"{float(val):.{decimals}f}"
    except (ValueError, TypeError):
        return val or "—"


def _build_tab(market: str) -> tuple[str, str, int]:
    csv_path = _latest_csv(market)
    if not csv_path:
        return "—", "<tr><td colspan='10' style='text-align:center;color:#6e7681;padding:2rem'>Keine Daten — erster Run ausstehend</td></tr>", 0

    run_date = "_".join(csv_path.stem.split("_")[2:])

    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    tickers_in_csv = {r["ticker"] for r in rows}
    for chart_file in CHARTS_SRC.glob("*.png"):
        ticker = chart_file.name.split("_")[0]
        if ticker in tickers_in_csv:
            shutil.copy2(chart_file, CHARTS_DST / chart_file.name)

    rows = sorted(rows, key=lambda r: float(r.get("score") or 0), reverse=True)

    tbody = ""
    for r in rows:
        chart = _find_chart(r["ticker"], r["pattern_type"])
        chart_cell = f'<a href="{chart}" target="_blank">&#x1F4C8;</a>' if chart else "—"
        confirmed  = "&#x2713;" if r.get("confirmed") == "True" else ""
        sc         = _score_class(r.get("score", ""))
        tbody += (
            f"<tr>"
            f"<td><b>{r['ticker']}</b></td>"
            f"<td>{r['pattern_type']}</td>"
            f"<td>{r['breakout_type']}</td>"
            f"<td class=center>{confirmed}</td>"
            f"<td class='score {sc}'>{_fmt(r.get('score',''), 0)}</td>"
            f"<td>{r.get('status','')}</td>"
            f"<td>{_fmt(r.get('entry_zone_low',''))}</td>"
            f"<td>{_fmt(r.get('price_target',''))}</td>"
            f"<td>{_fmt(r.get('measured_move_pct',''), 1)}%</td>"
            f"<td class=center>{chart_cell}</td>"
            f"</tr>\n"
        )
    return run_date, tbody, len(rows)


def build():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    tab_buttons = ""
    tab_panes   = ""

    for i, (key, label) in enumerate(MARKETS):
        run_date, tbody, count = _build_tab(key)
        active = "active" if i == 0 else ""
        tab_buttons += (
            f'<button class="tab-btn {active}" '
            f'onclick="showTab(\'{key}\')" id="btn-{key}">'
            f'{label}<span class="badge">{count}</span></button>\n'
        )
        tab_panes += f"""
<div class="tab-pane {active}" id="tab-{key}">
  <p class="meta">Stand: {run_date} &nbsp;&middot;&nbsp; {count} Signale</p>
  <table>
    <thead>
      <tr>
        <th>Ticker</th><th>Pattern</th><th>Breakout</th><th>Confirmed</th>
        <th>Score</th><th>Status</th><th>Entry Low</th><th>Target</th><th>Move%</th><th>Chart</th>
      </tr>
    </thead>
    <tbody>
{tbody}    </tbody>
  </table>
</div>
"""

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Breakout Signals</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'SF Mono',Consolas,monospace;background:#0d1117;color:#c9d1d9;padding:1.5rem;font-size:13px}}
    h1{{font-size:1rem;color:#58a6ff;margin-bottom:.5rem}}
    .generated{{color:#6e7681;font-size:11px;margin-bottom:1rem}}
    .tabs{{display:flex;gap:.5rem;margin-bottom:1.25rem;flex-wrap:wrap}}
    .tab-btn{{background:#161b22;border:1px solid #30363d;color:#8b949e;padding:.4rem 1rem;
              border-radius:6px;cursor:pointer;font-size:12px;font-family:inherit;display:flex;
              align-items:center;gap:.4rem}}
    .tab-btn:hover{{border-color:#58a6ff;color:#c9d1d9}}
    .tab-btn.active{{background:#1f6feb;border-color:#1f6feb;color:#fff}}
    .badge{{background:#30363d;border-radius:10px;padding:1px 7px;font-size:10px}}
    .tab-btn.active .badge{{background:rgba(255,255,255,.25)}}
    .tab-pane{{display:none}}.tab-pane.active{{display:block}}
    .meta{{color:#6e7681;font-size:11px;margin-bottom:.75rem}}
    table{{border-collapse:collapse;width:100%}}
    th{{color:#8b949e;border-bottom:1px solid #30363d;padding:5px 10px;text-align:left;
        font-weight:normal;white-space:nowrap}}
    td{{padding:5px 10px;border-bottom:1px solid #161b22;white-space:nowrap}}
    tr:hover td{{background:#161b22}}
    .center{{text-align:center}}
    .score{{font-weight:bold}}
    .score.hi{{color:#3fb950}}
    .score.mid{{color:#d29922}}
    a{{color:#58a6ff;text-decoration:none}}
    .legend{{margin:1.5rem 0 1rem;color:#6e7681;font-size:11px;line-height:1.8}}
    .legend b{{color:#8b949e}}
  </style>
</head>
<body>
  <h1>Breakout Signals</h1>
  <p class="generated">Generiert: {now}</p>
  <div class="tabs">
{tab_buttons}  </div>
{tab_panes}
  <div class="legend">
    <div><b>Pattern</b> &nbsp; rectangle — Seitwärtsrange &nbsp;|&nbsp; triangle_sym — symm. Dreieck &nbsp;|&nbsp; triangle_asc — aufst. Dreieck &nbsp;|&nbsp; ihs — inv. SKS</div>
    <div><b>Breakout</b> &nbsp; type1 — bestätigt &nbsp;|&nbsp; type2 — Ausbruch + Retest &nbsp;|&nbsp; pending — kein Ausbruch yet</div>
    <div><b>Score</b> &nbsp; <span style="color:#3fb950">■</span> ≥70 hoch &nbsp; <span style="color:#d29922">■</span> ≥50 mittel &nbsp;|&nbsp; <b>Entry Low</b> — Einstiegszone unten &nbsp;|&nbsp; <b>Move%</b> — erwartete Bewegung</div>
  </div>
  <script>
    function showTab(key) {{
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('tab-' + key).classList.add('active');
      document.getElementById('btn-' + key).classList.add('active');
    }}
  </script>
</body>
</html>"""

    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Built docs/index.html — {now} — {len(MARKETS)} tabs")


if __name__ == "__main__":
    build()
