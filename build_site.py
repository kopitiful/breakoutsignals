"""Generate docs/index.html with tabs for all 4 markets + watchlist."""

import csv
import json
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


def _load_rows(market: str) -> tuple[list[dict], str]:
    csv_path = _latest_csv(market)
    if not csv_path:
        return [], ""
    date = csv_path.stem.split("_", 2)[-1]  # signals_europa_2026-06-10 → 2026-06-10
    with open(csv_path) as f:
        rows = sorted(csv.DictReader(f),
                      key=lambda r: float(r.get("score") or 0), reverse=True)
    return rows, date


def _find_chart(ticker: str, pattern_type: str) -> str | None:
    stem = f"{ticker}_{pattern_type}"
    matches = sorted(CHARTS_DST.glob(f"{stem}*.png"))
    return f"charts/{matches[-1].name}" if matches else None


def _score_class(score: str) -> str:
    try:
        s = float(score)
        if s >= 70:  return "hi"
        if s >= 50:  return "mid"
    except (ValueError, TypeError):
        pass
    return ""


def _fmt(val: str, decimals: int = 2) -> str:
    try:
        return f"{float(val):.{decimals}f}"
    except (ValueError, TypeError):
        return val or "—"


def _row_html(r: dict) -> str:
    chart      = _find_chart(r["ticker"], r["pattern_type"])
    chart_cell = f'<a href="{chart}" target="_blank">&#x1F4C8;</a>' if chart else "—"
    confirmed  = "&#x2713;" if r.get("confirmed") in ("True", "full", "time", "volume") else ""
    sc         = _score_class(r.get("score", ""))
    row_data   = json.dumps({k: r.get(k, "") for k in [
        "ticker", "pattern_type", "breakout_type", "confirmed", "score", "status",
        "last_close", "entry_zone_low", "price_target", "measured_move_pct",
    ]}, ensure_ascii=False)
    return (
        f'<tr data-row=\'{row_data}\'>'
        f'<td><button class="add-btn" title="Zur Watchlist hinzufügen">+</button></td>'
        f'<td><b>{r["ticker"]}</b></td>'
        f'<td>{r["pattern_type"]}</td>'
        f'<td>{r["breakout_type"]}</td>'
        f'<td class=center>{confirmed}</td>'
        f'<td class="score {sc}">{_fmt(r.get("score",""), 0)}</td>'
        f'<td>{r.get("status","")}</td>'
        f'<td class=right>{_fmt(r.get("last_close",""))}</td>'
        f'<td class=right>{_fmt(r.get("entry_zone_low",""))}</td>'
        f'<td class=right>{_fmt(r.get("price_target",""))}</td>'
        f'<td class=right>{_fmt(r.get("measured_move_pct",""), 1)}%</td>'
        f'<td class=center>{chart_cell}</td>'
        f'</tr>\n'
    )


def _table(rows: list[dict]) -> str:
    if not rows:
        return '<p class="empty">Keine Signale.</p>'
    head = (
        '<table><thead><tr>'
        '<th></th><th>Ticker</th><th>Pattern</th><th>Breakout</th><th>Conf</th>'
        '<th>Score</th><th>Status</th><th>Kurs</th><th>Entry Low</th><th>Target</th>'
        '<th>Move%</th><th>Chart</th>'
        '</tr></thead><tbody>'
    )
    return head + "".join(_row_html(r) for r in rows) + "</tbody></table>"


def build():
    market_data = []
    all_tickers = set()
    for key, label in MARKETS:
        rows, date = _load_rows(key)
        market_data.append((key, label, rows, date))
        all_tickers.update(r["ticker"] for r in rows)

    for chart_file in CHARTS_SRC.glob("*.png"):
        if chart_file.name.split("_")[0] in all_tickers:
            shutil.copy2(chart_file, CHARTS_DST / chart_file.name)

    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    total = sum(len(rows) for _, _, rows, _ in market_data)
    latest_date = next((d for _, _, _, d in market_data if d), "")

    html = _render(market_data, now, total, latest_date)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    summary = " + ".join(f"{len(rows)} {label} ({date})" for _, label, rows, date in market_data if rows)
    print(f"Built docs/index.html — {summary}")


def _render(market_data, now, total, latest_date) -> str:
    first_key = market_data[0][0] if market_data else "europa"

    tab_html = "".join(
        f'<div class="tab{" active" if i == 0 else ""}" data-tab="{key}">'
        f'{label} <span class="tab-date">{date}</span></div>'
        for i, (key, label, _, date) in enumerate(market_data)
    ) + '<div class="tab" data-tab="wl">Watchlist</div>'

    panel_html = "".join(
        f'<div id="{key}" class="panel{" active" if i == 0 else ""}">{_table(rows)}</div>'
        for i, (key, _, rows, _) in enumerate(market_data)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Breakout Signals {latest_date}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'SF Mono',Consolas,monospace;background:#0d1117;color:#c9d1d9;padding:1.5rem;font-size:13px}}
    h1{{font-size:1rem;color:#58a6ff;margin-bottom:.25rem}}
    .meta{{color:#6e7681;font-size:11px;margin-bottom:1rem}}
    .tabs{{display:flex;gap:0;margin-bottom:1rem;border-bottom:1px solid #30363d}}
    .tab{{padding:6px 18px;cursor:pointer;color:#6e7681;border-bottom:2px solid transparent;margin-bottom:-1px}}
    .tab:hover{{color:#c9d1d9}}
    .tab.active{{color:#58a6ff;border-bottom-color:#58a6ff}}
    .tab-date{{font-size:10px;color:#6e7681;margin-left:4px}}
    .panel{{display:none}}.panel.active{{display:block}}
    table{{border-collapse:collapse;width:100%}}
    th{{color:#8b949e;border-bottom:1px solid #30363d;padding:5px 10px;text-align:left;font-weight:normal;white-space:nowrap}}
    td{{padding:5px 10px;border-bottom:1px solid #161b22;white-space:nowrap}}
    tr:hover td{{background:#161b22}}
    .right{{text-align:right}}.center{{text-align:center}}
    .score{{font-weight:bold}}
    .score.hi{{color:#3fb950}}.score.mid{{color:#d29922}}
    a{{color:#58a6ff;text-decoration:none}}
    .add-btn{{background:none;border:1px solid #30363d;color:#6e7681;border-radius:3px;
              width:18px;height:18px;cursor:pointer;font-size:12px;line-height:1;padding:0}}
    .add-btn:hover{{border-color:#58a6ff;color:#58a6ff}}
    #wl-empty{{color:#6e7681;margin-top:.5rem}}
    .wl-remove{{background:none;border:none;color:#6e7681;cursor:pointer;font-size:11px;padding:0 4px}}
    .wl-remove:hover{{color:#f85149}}
    .empty{{color:#6e7681;margin-top:.5rem}}
    .legend{{margin:1.5rem 0 0;color:#6e7681;font-size:11px;line-height:1.8}}
    .legend b{{color:#8b949e}}
  </style>
</head>
<body>
  <h1>Breakout Signals</h1>
  <p class="meta">Stand: {latest_date} &nbsp;&middot;&nbsp; {now} &nbsp;&middot;&nbsp; {total} Signale</p>

  <div class="tabs">{tab_html}</div>
  {panel_html}
  <div id="wl" class="panel">
    <div id="wl-empty" style="display:none">Noch keine Einträge — klicke + bei einem Signal.</div>
    <div id="wl-table"></div>
  </div>

  <div class="legend">
    <b>Pattern</b> &nbsp; rectangle — Seitwärtsrange &nbsp;|&nbsp; triangle_sym — symm. Dreieck &nbsp;|&nbsp; triangle_asc — aufst. Dreieck &nbsp;|&nbsp; ihs — inv. Head &amp; Shoulders<br>
    <b>Breakout</b> &nbsp; type1 — bestätigter Ausbruch &nbsp;|&nbsp; type2 — Ausbruch + Retest &nbsp;|&nbsp; pending — kein Ausbruch<br>
    <b>Conf</b> &nbsp; ✓ = bestätigt (Volumen oder 2 Closes außerhalb) &nbsp;|&nbsp; <b>Kurs</b> — letzter Wochenschluss zum Zeitpunkt des Scans<br>
    <b>Score</b> &nbsp; 0–100 &nbsp; <span style="color:#3fb950">&#x25A0;</span> ≥70 &nbsp; <span style="color:#d29922">&#x25A0;</span> ≥50 &nbsp;|&nbsp; <b>Entry Low</b> — untere Einstiegszone &nbsp;|&nbsp; <b>Target</b> — Kursziel (Measured Move)
  </div>

  <script>
    document.querySelectorAll('.tab').forEach(t => {{
      t.addEventListener('click', () => {{
        document.querySelectorAll('.tab,.panel').forEach(el => el.classList.remove('active'));
        t.classList.add('active');
        document.getElementById(t.dataset.tab).classList.add('active');
        if (t.dataset.tab === 'wl') renderWatchlist();
      }});
    }});

    function getWL() {{ return JSON.parse(localStorage.getItem('wl') || '[]'); }}
    function setWL(wl) {{ localStorage.setItem('wl', JSON.stringify(wl)); }}

    function addToWL(row) {{
      const wl = getWL();
      const key = row.ticker + '|' + row.pattern_type;
      if (!wl.find(r => r.ticker + '|' + r.pattern_type === key)) {{
        wl.push(row); setWL(wl);
      }}
    }}

    function removeFromWL(key) {{
      setWL(getWL().filter(r => r.ticker + '|' + r.pattern_type !== key));
      renderWatchlist();
    }}

    function renderWatchlist() {{
      const wl = getWL();
      const tbl = document.getElementById('wl-table');
      const empty = document.getElementById('wl-empty');
      if (!wl.length) {{ tbl.innerHTML = ''; empty.style.display = 'block'; return; }}
      empty.style.display = 'none';
      const rows = wl.map(r => {{
        const key = r.ticker + '|' + r.pattern_type;
        const sc = parseFloat(r.score||0) >= 70 ? 'hi' : parseFloat(r.score||0) >= 50 ? 'mid' : '';
        const fmt = (v, d=2) => v ? parseFloat(v).toFixed(d) : '—';
        return `<tr>
          <td><button class="wl-remove" onclick="removeFromWL('${{key}}')" title="Entfernen">&#x2715;</button></td>
          <td><b>${{r.ticker}}</b></td><td>${{r.pattern_type}}</td><td>${{r.breakout_type}}</td>
          <td class="score ${{sc}}">${{fmt(r.score, 0)}}</td><td>${{r.status}}</td>
          <td class=right>${{fmt(r.last_close)}}</td>
          <td class=right>${{fmt(r.entry_zone_low)}}</td>
          <td class=right>${{fmt(r.price_target)}}</td>
          <td class=right>${{fmt(r.measured_move_pct, 1)}}%</td>
        </tr>`;
      }}).join('');
      tbl.innerHTML = `<table><thead><tr>
        <th></th><th>Ticker</th><th>Pattern</th><th>Breakout</th>
        <th>Score</th><th>Status</th><th>Kurs</th><th>Entry Low</th><th>Target</th><th>Move%</th>
      </tr></thead><tbody>${{rows}}</tbody></table>`;
    }}

    document.querySelectorAll('.add-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const row = JSON.parse(btn.closest('tr').dataset.row);
        addToWL(row);
        btn.textContent = '✓'; btn.style.color = '#3fb950';
        setTimeout(() => {{ btn.textContent = '+'; btn.style.color = ''; }}, 1200);
      }});
    }});
  </script>
</body>
</html>"""


if __name__ == "__main__":
    build()
