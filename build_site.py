"""Generate docs/index.html from the latest signals CSV."""

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


def _latest_csv():
    csvs = sorted(SIGNALS_DIR.glob("signals_*.csv"))
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


def build():
    csv_path = _latest_csv()
    if not csv_path:
        print("No signals CSV found — nothing to build.")
        return

    run_date = csv_path.stem.replace("signals_", "")

    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    # Copy chart PNGs for tickers that appear in latest signals
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

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Aksel Signals {run_date}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'SF Mono',Consolas,monospace;background:#0d1117;color:#c9d1d9;padding:1.5rem;font-size:13px}}
    h1{{font-size:1rem;color:#58a6ff;margin-bottom:.25rem}}
    .meta{{color:#6e7681;font-size:11px;margin-bottom:1.5rem}}
    table{{border-collapse:collapse;width:100%}}
    th{{color:#8b949e;border-bottom:1px solid #30363d;padding:5px 10px;text-align:left;font-weight:normal;white-space:nowrap}}
    td{{padding:5px 10px;border-bottom:1px solid #161b22;white-space:nowrap}}
    tr:hover td{{background:#161b22}}
    .center{{text-align:center}}
    .score{{font-weight:bold}}
    .score.hi{{color:#3fb950}}
    .score.mid{{color:#d29922}}
    a{{color:#58a6ff;text-decoration:none}}
  </style>
</head>
<body>
  <h1>Aksel — Pattern Signals</h1>
  <p class="meta">Run date: {run_date} &nbsp;&middot;&nbsp; Generated: {now} &nbsp;&middot;&nbsp; {len(rows)} signals</p>
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
</body>
</html>"""

    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Built docs/index.html — {len(rows)} signals from {run_date}")


if __name__ == "__main__":
    build()
