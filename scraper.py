#!/usr/bin/env python3
"""
Maine 2026 Poll Tracker
Senate · Governor · CD-1 · CD-2 — primaries and general election matchups.
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Maine Poll Tracker/1.0; +https://github.com/)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 15

# ---------------------------------------------------------------------------
# Poll data
# Each section has:
#   type: "primary" | "h2h"  (h2h = head-to-head general election matchup)
#   key_candidates: used for the big avg display (and h2h spread calculation)
#   polls: list of individual polls
# ---------------------------------------------------------------------------

SECTIONS = [
    # ── US SENATE ────────────────────────────────────────────────────────────
    {
        "id": "senate-dem-primary",
        "race": "senate",
        "type": "primary",
        "heading": "Democratic Primary",
        "note": "Primary election: June 9, 2026",
        "key_candidates": ["Graham Platner (D)", "Janet Mills (D)"],
        "polls": [
            {"date": "2026-04-07", "pollster": "Maine Beacon / Aggregate",
             "sample": None, "moe": None,
             "candidates": {"Graham Platner (D)": 61, "Janet Mills (D)": 28, "Undecided": 11}},
            {"date": "2026-03-21", "pollster": "Emerson College",
             "sample": None, "moe": None,
             "candidates": {"Graham Platner (D)": 55, "Janet Mills (D)": 28, "Undecided": 13}},
            {"date": "2026-02-16", "pollster": "UNH Survey Center",
             "sample": 462, "moe": None,
             "candidates": {"Graham Platner (D)": 64, "Janet Mills (D)": 26, "Undecided": 10}},
        ],
    },
    {
        "id": "senate-gen-platner",
        "race": "senate",
        "type": "h2h",
        "heading": "General Election: Collins vs. Platner",
        "note": "RealClearPolling average: Platner +7.6 pts",
        "key_candidates": ["Susan Collins (R)", "Graham Platner (D)"],
        "polls": [
            {"date": "2026-04-09", "pollster": "Decision Desk HQ",
             "sample": 157, "moe": None,
             "candidates": {"Susan Collins (R)": 44, "Graham Platner (D)": 44, "Other/Undecided": 12}},
            {"date": "2026-04-09", "pollster": "Race to the WH",
             "sample": 500, "moe": None,
             "candidates": {"Susan Collins (R)": 41, "Graham Platner (D)": 48, "Other/Undecided": 11}},
            {"date": "2026-03-21", "pollster": "Emerson College",
             "sample": None, "moe": None,
             "candidates": {"Susan Collins (R)": 41, "Graham Platner (D)": 48, "Other/Undecided": 11}},
            {"date": "2026-02-16", "pollster": "UNH Survey Center",
             "sample": 462, "moe": None,
             "candidates": {"Susan Collins (R)": 38, "Graham Platner (D)": 49, "Other/Undecided": 13}},
        ],
        "wiki_url": "https://en.wikipedia.org/wiki/2026_United_States_Senate_election_in_Maine",
        "wiki_require": ["Susan Collins"],
        "wiki_exclude": ["Janet Mills"],  # skip 3-way polls that include Mills
    },
    {
        "id": "senate-gen-mills",
        "race": "senate",
        "type": "h2h",
        "heading": "General Election: Collins vs. Mills",
        "note": "Alternate matchup if Mills wins the Democratic primary",
        "key_candidates": ["Susan Collins (R)", "Janet Mills (D)"],
        "polls": [
            {"date": "2026-04-09", "pollster": "270toWin Aggregate",
             "sample": 138, "moe": None,
             "candidates": {"Susan Collins (R)": 45, "Janet Mills (D)": 45, "Other/Undecided": 10}},
            {"date": "2026-03-21", "pollster": "Emerson College",
             "sample": None, "moe": None,
             "candidates": {"Susan Collins (R)": 43, "Janet Mills (D)": 46, "Other/Undecided": 11}},
            {"date": "2026-02-16", "pollster": "UNH Survey Center",
             "sample": 462, "moe": None,
             "candidates": {"Susan Collins (R)": 40, "Janet Mills (D)": 41, "Other/Undecided": 19}},
        ],
    },
    # ── GOVERNOR ─────────────────────────────────────────────────────────────
    {
        "id": "gov-dem-primary",
        "race": "governor",
        "type": "primary",
        "heading": "Democratic Primary",
        "note": "Primary election: June 9, 2026. No general-election matchup polls available yet.",
        "key_candidates": ["Nirav Shah (D)", "Angus King III (D)", "Hannah Pingree (D)",
                           "Shenna Bellows (D)", "Troy Jackson (D)"],
        "polls": [
            {"date": "2026-03-05", "pollster": "Pan Atlantic Research",
             "sample": None, "moe": None,
             "candidates": {"Nirav Shah (D)": 24, "Angus King III (D)": 24,
                            "Hannah Pingree (D)": 18, "Shenna Bellows (D)": 16,
                            "Troy Jackson (D)": 10, "Undecided": 8}},
            {"date": "2025-12-11", "pollster": "Pan Atlantic Research",
             "sample": None, "moe": None,
             "candidates": {"Nirav Shah (D)": 24, "Angus King III (D)": 19,
                            "Hannah Pingree (D)": 18, "Shenna Bellows (D)": 16,
                            "Troy Jackson (D)": 8, "Undecided": 15}},
        ],
    },
    {
        "id": "gov-rep-primary",
        "race": "governor",
        "type": "primary",
        "heading": "Republican Primary",
        "note": "Primary election: June 9, 2026. 44% of Republican voters say they're not yet familiar with all candidates.",
        "key_candidates": ["Bobby Charles (R)", "Garrett Mason (R)", "Jim Libby (R)"],
        "polls": [
            {"date": "2026-03-05", "pollster": "Pan Atlantic Research",
             "sample": None, "moe": None,
             "candidates": {"Bobby Charles (R)": 26, "Garrett Mason (R)": 11,
                            "Jim Libby (R)": 8, "Undecided/Other": 55}},
        ],
    },
    # ── CD-2 ─────────────────────────────────────────────────────────────────
    {
        "id": "cd2-dem-primary",
        "race": "cd2",
        "type": "primary",
        "heading": "CD-2 Democratic Primary",
        "note": "Open seat: Jared Golden (D) withdrew Nov. 2025. Primary: June 9, 2026.",
        "key_candidates": ["Joe Baldacci (D)", "Matt Dunlap (D)", "Jordan Wood (D)"],
        "polls": [
            {"date": "2026-03-05", "pollster": "Pan Atlantic Research",
             "sample": None, "moe": None,
             "candidates": {"Joe Baldacci (D)": 36, "Matt Dunlap (D)": 14,
                            "Jordan Wood (D)": 12, "Undecided": 38}},
        ],
    },
    {
        "id": "cd2-gen-baldacci",
        "race": "cd2",
        "type": "h2h",
        "heading": "General Election: LePage vs. Baldacci",
        "note": "Trump won CD-2 by 9 pts in 2024. Within margin of error.",
        "key_candidates": ["Paul LePage (R)", "Joe Baldacci (D)"],
        "polls": [
            {"date": "2026-02-16", "pollster": "UNH Survey Center",
             "sample": 462, "moe": 5.1,
             "candidates": {"Paul LePage (R)": 48, "Joe Baldacci (D)": 47, "Other/Undecided": 5}},
            {"date": "2026-02-01", "pollster": "Punchbowl News / Internal",
             "sample": None, "moe": 5.1,
             "candidates": {"Paul LePage (R)": 44, "Joe Baldacci (D)": 43, "Other/Undecided": 13}},
        ],
    },
    {
        "id": "cd2-gen-dunlap",
        "race": "cd2",
        "type": "h2h",
        "heading": "General Election: LePage vs. Dunlap",
        "note": "Alternate matchup if Dunlap wins the Democratic primary.",
        "key_candidates": ["Paul LePage (R)", "Matt Dunlap (D)"],
        "polls": [
            {"date": "2026-02-16", "pollster": "UNH Survey Center",
             "sample": 462, "moe": 5.1,
             "candidates": {"Paul LePage (R)": 47, "Matt Dunlap (D)": 46, "Other/Undecided": 7}},
        ],
    },
    # ── CD-1 ─────────────────────────────────────────────────────────────────
    {
        "id": "cd1-gen",
        "race": "cd1",
        "type": "incumbent",
        "heading": "CD-1 General Election",
        "note": "Incumbent Chellie Pingree (D) won 58.1% in 2024. No public polling available yet.",
        "key_candidates": [],
        "polls": [],
    },
]

RACE_META = {
    "senate": {"label": "US Senate", "anchor": "senate"},
    "governor": {"label": "Governor", "anchor": "governor"},
    "cd2": {"label": "CD-2", "anchor": "cd2"},
    "cd1": {"label": "CD-1", "anchor": "cd1"},
}

# ---------------------------------------------------------------------------
# Wikipedia scraping (used to supplement senate-gen-platner)
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        print(f"  [warn] {url}: {exc}", file=sys.stderr)
        return None


def clean_pct(text: str) -> Optional[float]:
    try:
        v = float(text.strip().rstrip("%").strip())
        return v if 1 <= v <= 99 else None
    except ValueError:
        return None


def scrape_wiki_h2h(url: str, require: list[str], exclude: list[str]) -> list[dict]:
    soup = fetch_page(url)
    if not soup:
        return []
    polls = []
    for table in soup.find_all("table", class_=re.compile(r"wikitable")):
        col_headers: list[str] = []
        for row in table.find_all("tr")[:3]:
            ths = row.find_all("th")
            if len(ths) >= 3:
                col_headers = [th.get_text(separator=" ", strip=True) for th in ths]
                break
        if not col_headers:
            continue
        header_text = " ".join(col_headers).lower()
        if not any(k in header_text for k in ["poll", "date", "pollster"]):
            continue

        def find_col(patterns):
            for pat in patterns:
                for i, h in enumerate(col_headers):
                    if pat.lower() in h.lower():
                        return i
            return -1

        date_col = find_col(["date", "conducted", "field"])
        pollster_col = find_col(["poll", "source", "firm", "organization"])
        sample_col = find_col(["sample", "n =", "size"])

        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue
            texts = [c.get_text(separator=" ", strip=True) for c in cells]

            raw_date = texts[date_col] if 0 <= date_col < len(texts) else ""
            date_str = ""
            m = re.search(r"(\w+ \d{1,2},?\s*\d{4})", raw_date)
            if m:
                try:
                    date_str = datetime.strptime(m.group(1).replace(",", ""), "%B %d %Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass
            if not date_str:
                continue

            pollster = texts[pollster_col].strip() if 0 <= pollster_col < len(texts) else "Unknown"
            sample_raw = texts[sample_col] if 0 <= sample_col < len(texts) else ""
            sample_num = None
            sm = re.search(r"(\d[\d,]+)", sample_raw)
            if sm:
                sample_num = int(sm.group(1).replace(",", ""))

            cand_pcts: dict[str, float] = {}
            for i, (h, t) in enumerate(zip(col_headers, texts)):
                if i == sample_col or re.search(r"(margin|error|moe)", h, re.I):
                    continue
                pct = clean_pct(t)
                if pct is not None and h:
                    cand_pcts[h] = pct

            if len(cand_pcts) < 2:
                continue
            keys_lower = " ".join(cand_pcts.keys()).lower()
            if not all(r.lower() in keys_lower for r in require):
                continue
            if any(e.lower() in keys_lower for e in exclude):
                continue

            polls.append({"date": date_str, "pollster": pollster,
                          "sample": sample_num, "moe": None, "candidates": cand_pcts})
    return polls


# ---------------------------------------------------------------------------
# Averages — only over key_candidates
# ---------------------------------------------------------------------------

def compute_h2h_avgs(section: dict, days: int = 60) -> dict[str, float]:
    polls = section["polls"]
    key = section["key_candidates"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    weighted: list[tuple[float, dict]] = []
    for p in polls:
        try:
            d = datetime.strptime(p["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if d >= cutoff:
            age = (datetime.now(timezone.utc) - d).days
            weighted.append((max(days - age, 1), p["candidates"]))
    if not weighted:
        weighted = [(1, p["candidates"]) for p in polls[:3]]
    total_w = sum(w for w, _ in weighted)
    avgs = {}
    for cand in key:
        avgs[cand] = round(sum(w * c.get(cand, 0) for w, c in weighted) / total_w, 1)
    return avgs


def compute_primary_avgs(section: dict, days: int = 90) -> dict[str, float]:
    polls = section["polls"]
    key = set(section["key_candidates"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    weighted: list[tuple[float, dict]] = []
    for p in polls:
        try:
            d = datetime.strptime(p["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        age = (datetime.now(timezone.utc) - d).days
        if d >= cutoff:
            weighted.append((max(days - age, 1), p["candidates"]))
    if not weighted:
        weighted = [(1, p["candidates"]) for p in polls[:3]]
    total_w = sum(w for w, _ in weighted)
    all_cands = set()
    for _, c in weighted:
        all_cands.update(c.keys())
    avgs = {}
    for cand in all_cands:
        if cand in key or not key:
            avgs[cand] = round(sum(w * c.get(cand, 0) for w, c in weighted) / total_w, 1)
    return dict(sorted(avgs.items(), key=lambda x: x[1], reverse=True))


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def pclass(name: str) -> str:
    n = name.lower()
    if "(r)" in n:
        return "rep"
    if "(d)" in n:
        return "dem"
    return "und"


def pcolor(name: str) -> str:
    c = pclass(name)
    return {"rep": "#ef4444", "dem": "#3b82f6", "und": "#9ca3af"}[c]


def plabel(name: str) -> str:
    n = name.lower()
    if "(r)" in n:
        return "Republican"
    if "(d)" in n:
        return "Democrat"
    return ""


def short_name(name: str) -> str:
    return re.sub(r"\s*\([^)]+\)\s*$", "", name).strip()


CHART_QUEUE: list[str] = []  # collects makeChart(...) calls; rendered once at page bottom


def build_h2h_html(section: dict) -> str:
    avgs = compute_h2h_avgs(section)
    polls = section["polls"]
    key = section["key_candidates"]
    if len(key) < 2:
        return ""
    cand_a, cand_b = key[0], key[1]
    avg_a = avgs.get(cand_a, 0)
    avg_b = avgs.get(cand_b, 0)
    spread = round(abs(avg_a - avg_b), 1)
    leader = cand_a if avg_a >= avg_b else cand_b
    leader_short = short_name(leader)
    spread_txt = f"{leader_short} leads by {spread} pts" if spread > 0 else "Tied"

    # head-to-head display
    a_cls = pclass(cand_a)
    b_cls = pclass(cand_b)
    hth = f"""
    <div class="hth-wrap">
      <div class="hth-cand {a_cls} {'leader' if avg_a >= avg_b else ''}">
        <div class="hth-name">{short_name(cand_a)}</div>
        <div class="hth-party">{plabel(cand_a)}</div>
        <div class="hth-pct">{avg_a}%</div>
      </div>
      <div class="hth-vs">vs</div>
      <div class="hth-cand {b_cls} {'leader' if avg_b > avg_a else ''}">
        <div class="hth-name">{short_name(cand_b)}</div>
        <div class="hth-party">{plabel(cand_b)}</div>
        <div class="hth-pct">{avg_b}%</div>
      </div>
    </div>
    <p class="spread-line">{spread_txt} &mdash; polling average</p>"""

    # trend chart
    chart_id = section["id"]
    chart_polls = list(reversed(polls))
    labels = json.dumps([p["date"] for p in chart_polls])
    datasets = []
    for cand in key:
        color = pcolor(cand)
        vals = json.dumps([p["candidates"].get(cand) for p in chart_polls])
        datasets.append(
            f'{{"label":{json.dumps(short_name(cand))},"data":{vals},'
            f'"borderColor":"{color}","backgroundColor":"{color}22",'
            f'"pointBackgroundColor":"{color}","tension":0.35,"fill":false,"spanGaps":true}}'
        )
    CHART_QUEUE.append(f'makeChart("c_{chart_id}",[{",".join(datasets)}],{labels});')
    chart = f'<div class="chart-wrap"><canvas id="c_{chart_id}"></canvas></div>'

    # poll table
    all_cands: list[str] = []
    seen: set[str] = set()
    for p in polls:
        for c in p["candidates"]:
            if c not in seen:
                seen.add(c)
                all_cands.append(c)
    thead = "".join(f"<th>{h}</th>" for h in ["Date", "Pollster", "Sample", "MoE"] + all_cands)
    tbody = ""
    for p in polls:
        row = (f"<td>{p['date']}</td><td>{p['pollster']}</td>"
               f"<td>{p['sample'] or 'N/A'}</td>"
               f"<td>{'±'+str(p['moe'])+'%' if p.get('moe') else 'N/A'}</td>")
        for c in all_cands:
            v = p["candidates"].get(c)
            row += f"<td>{v}%</td>" if v is not None else "<td>—</td>"
        tbody += f"<tr>{row}</tr>"
    table = f'<div class="tbl-wrap"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>'

    note_html = f'<p class="section-note">{section["note"]}</p>' if section.get("note") else ""
    return f"""
<div class="subsection" id="{section['id']}">
  <div class="subsection-header">
    <span class="subsection-badge general">General Election</span>
    <h3>{section['heading']}</h3>
  </div>
  {note_html}
  {hth}
  {chart}
  {table}
</div>"""


def build_primary_html(section: dict) -> str:
    avgs = compute_primary_avgs(section)
    polls = section["polls"]
    key = section["key_candidates"]

    party_str = "Republican" if key and "(R)" in key[0] else "Democratic"
    badge_cls = "rep-badge" if party_str == "Republican" else "dem-badge"

    # Horizontal bar chart for each candidate
    bars_html = ""
    max_pct = max((v for k, v in avgs.items() if k in set(key)), default=1) or 1
    for cand in key:
        pct = avgs.get(cand, 0)
        css = pclass(cand)
        bar_w = round(pct / 75 * 100, 1)  # scale to 75% as "full"
        bars_html += f"""
      <div class="bar-row">
        <div class="bar-name">{short_name(cand)}</div>
        <div class="bar-track">
          <div class="bar-fill {css}" style="width:{min(bar_w,100)}%"></div>
        </div>
        <div class="bar-pct">{pct}%</div>
      </div>"""

    # trend chart (only if 2+ candidates have data across 2+ polls)
    chart_id = section["id"]
    chart_polls = list(reversed(polls))
    labels = json.dumps([p["date"] for p in chart_polls])
    datasets = []
    for cand in key:
        color = pcolor(cand)
        vals = json.dumps([p["candidates"].get(cand) for p in chart_polls])
        datasets.append(
            f'{{"label":{json.dumps(short_name(cand))},"data":{vals},'
            f'"borderColor":"{color}","backgroundColor":"{color}22",'
            f'"pointBackgroundColor":"{color}","tension":0.35,"fill":false,"spanGaps":true}}'
        )
    chart = ""
    if len(polls) >= 2:
        CHART_QUEUE.append(f'makeChart("c_{chart_id}",[{",".join(datasets)}],{labels});')
        chart = f'<div class="chart-wrap"><canvas id="c_{chart_id}"></canvas></div>'

    # poll table
    all_cands: list[str] = []
    seen: set[str] = set()
    for p in polls:
        for c in p["candidates"]:
            if c not in seen:
                seen.add(c)
                all_cands.append(c)
    thead = "".join(f"<th>{h}</th>" for h in ["Date", "Pollster", "Sample"] + all_cands)
    tbody = ""
    for p in polls:
        row = f"<td>{p['date']}</td><td>{p['pollster']}</td><td>{p['sample'] or 'N/A'}</td>"
        for c in all_cands:
            v = p["candidates"].get(c)
            row += f"<td>{v}%</td>" if v is not None else "<td>—</td>"
        tbody += f"<tr>{row}</tr>"
    table = f'<div class="tbl-wrap"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>'

    note_html = f'<p class="section-note">{section["note"]}</p>' if section.get("note") else ""
    return f"""
<div class="subsection" id="{section['id']}">
  <div class="subsection-header">
    <span class="subsection-badge {badge_cls}">Primary</span>
    <h3>{section['heading']}</h3>
  </div>
  {note_html}
  <div class="bars-wrap">{bars_html}</div>
  {chart}
  {table}
</div>"""


def build_incumbent_html(section: dict) -> str:
    note_html = f'<p class="section-note">{section["note"]}</p>' if section.get("note") else ""
    return f"""
<div class="subsection" id="{section['id']}">
  <div class="subsection-header">
    <span class="subsection-badge general">General Election</span>
    <h3>{section['heading']}</h3>
  </div>
  {note_html}
  <p class="no-polling">No public polling available — race not currently competitive.</p>
</div>"""


def generate_html(sections: list[dict], last_updated: str) -> str:
    global CHART_QUEUE
    CHART_QUEUE = []

    # Group sections by race
    races = list(dict.fromkeys(s["race"] for s in sections))

    nav_items = ""
    for race in races:
        meta = RACE_META[race]
        nav_items += f'<a href="#{meta["anchor"]}" class="nav-item">{meta["label"]}</a>'

    body_html = ""
    for race in races:
        meta = RACE_META[race]
        race_sections = [s for s in sections if s["race"] == race]
        inner = ""
        for s in race_sections:
            if s["type"] == "h2h":
                inner += build_h2h_html(s)
            elif s["type"] == "primary":
                inner += build_primary_html(s)
            elif s["type"] == "incumbent":
                inner += build_incumbent_html(s)
        body_html += f'<section class="race-block" id="{meta["anchor"]}"><h2>{meta["label"]}</h2>{inner}</section>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Maine 2026 Poll Tracker</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f0f2f5;color:#1a1a2e;line-height:1.55}}

    /* Header */
    header{{background:linear-gradient(135deg,#0f2744 0%,#1d4ed8 100%);color:#fff;padding:2rem 1.5rem 0}}
    header h1{{font-size:1.9rem;font-weight:800;letter-spacing:-0.5px}}
    header .subtitle{{opacity:0.8;font-size:0.92rem;margin-top:0.3rem}}
    .updated{{font-size:0.78rem;opacity:0.6;margin-top:0.3rem}}

    /* Race nav tabs */
    .race-nav{{display:flex;gap:0;margin-top:1.2rem;overflow-x:auto}}
    .nav-item{{padding:0.65rem 1.25rem;font-size:0.9rem;font-weight:600;color:rgba(255,255,255,0.7);text-decoration:none;border-bottom:3px solid transparent;white-space:nowrap;transition:all 0.15s}}
    .nav-item:hover{{color:#fff;border-bottom-color:rgba(255,255,255,0.5)}}

    main{{max-width:900px;margin:0 auto;padding:1.5rem 1rem 3rem}}

    /* Race block */
    .race-block{{margin-bottom:2rem}}
    .race-block h2{{font-size:1.3rem;font-weight:800;color:#0f2744;padding:0.9rem 1.25rem;background:#fff;border-radius:10px 10px 0 0;border-bottom:2px solid #e2e8f0;margin-bottom:0}}

    /* Subsection */
    .subsection{{background:#fff;border-radius:0;padding:1.5rem 1.25rem;border-bottom:1px solid #e2e8f0}}
    .race-block .subsection:last-child{{border-radius:0 0 10px 10px;border-bottom:none}}
    .race-block .subsection:first-of-type{{border-top:none}}
    .subsection-header{{display:flex;align-items:center;gap:0.6rem;margin-bottom:0.5rem}}
    .subsection-header h3{{font-size:1rem;font-weight:700;color:#374151}}
    .subsection-badge{{font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;padding:0.2rem 0.55rem;border-radius:999px}}
    .general{{background:#dbeafe;color:#1d4ed8}}
    .dem-badge{{background:#dbeafe;color:#1d4ed8}}
    .rep-badge{{background:#fee2e2;color:#dc2626}}
    .section-note{{font-size:0.8rem;color:#6b7280;margin-bottom:1rem}}

    /* Head-to-head */
    .hth-wrap{{display:flex;align-items:stretch;gap:0;margin-bottom:0.75rem;border-radius:8px;overflow:hidden;border:1px solid #e5e7eb}}
    .hth-cand{{flex:1;padding:1.1rem 1rem;text-align:center;background:#f9fafb;transition:background 0.2s}}
    .hth-cand.dem{{background:#eff6ff}}
    .hth-cand.rep{{background:#fff5f5}}
    .hth-cand.leader.dem{{background:#dbeafe}}
    .hth-cand.leader.rep{{background:#fee2e2}}
    .hth-vs{{display:flex;align-items:center;padding:0 0.75rem;font-weight:700;font-size:0.8rem;color:#9ca3af;background:#f9fafb;border-left:1px solid #e5e7eb;border-right:1px solid #e5e7eb}}
    .hth-name{{font-size:1rem;font-weight:700;color:#111827}}
    .hth-party{{font-size:0.75rem;color:#6b7280;margin:0.1rem 0 0.4rem}}
    .hth-pct{{font-size:2.2rem;font-weight:800;line-height:1}}
    .hth-cand.dem .hth-pct{{color:#1d4ed8}}
    .hth-cand.rep .hth-pct{{color:#dc2626}}
    .spread-line{{font-size:0.82rem;color:#6b7280;margin-bottom:1rem;text-align:center}}

    /* Primary bars */
    .bars-wrap{{margin-bottom:1rem}}
    .bar-row{{display:flex;align-items:center;gap:0.75rem;margin-bottom:0.6rem}}
    .bar-name{{width:130px;font-size:0.85rem;font-weight:600;color:#374151;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .bar-track{{flex:1;background:#f3f4f6;border-radius:4px;height:22px;overflow:hidden}}
    .bar-fill{{height:100%;border-radius:4px;transition:width 0.4s}}
    .bar-fill.dem{{background:#3b82f6}}
    .bar-fill.rep{{background:#ef4444}}
    .bar-fill.und{{background:#9ca3af}}
    .bar-pct{{width:42px;font-size:0.88rem;font-weight:700;color:#374151;text-align:right;flex-shrink:0}}

    /* Chart */
    .chart-wrap{{position:relative;height:200px;margin:1rem 0}}

    /* Table */
    .tbl-wrap{{overflow-x:auto;margin-top:1rem}}
    table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
    thead tr{{background:#0f2744;color:#fff}}
    thead th{{padding:0.5rem 0.65rem;text-align:left;font-weight:600;white-space:nowrap}}
    tbody tr:nth-child(even){{background:#f8fafc}}
    tbody td{{padding:0.45rem 0.65rem;border-bottom:1px solid #e5e7eb;white-space:nowrap}}
    tbody tr:last-child td{{border-bottom:none}}

    .no-polling{{color:#9ca3af;font-size:0.87rem;font-style:italic;padding:0.5rem 0}}

    footer{{text-align:center;font-size:0.78rem;color:#9ca3af;padding-bottom:2rem}}
    footer a{{color:#6b7280;text-decoration:none}}
    footer a:hover{{color:#374151}}

    @media(max-width:580px){{
      header h1{{font-size:1.5rem}}
      .hth-pct{{font-size:1.7rem}}
      .hth-name{{font-size:0.9rem}}
      .bar-name{{width:100px;font-size:0.78rem}}
    }}
  </style>
</head>
<body>
<header>
  <h1>Maine 2026 Poll Tracker</h1>
  <p class="subtitle">Senate &bull; Governor &bull; CD-1 &bull; CD-2 &mdash; primaries &amp; general election</p>
  <p class="updated">Updated {last_updated}</p>
  <nav class="race-nav">{nav_items}</nav>
</header>

<main>
{body_html}
</main>

<footer>
  <p>Sources: Emerson College &bull; UNH Survey Center &bull; Pan Atlantic Research &bull; Punchbowl News &bull; RealClearPolling &bull; Wikipedia</p>
  <p style="margin-top:0.3rem"><a href="https://github.com/sloftus-lab/maine-poll-tracker" target="_blank">View source on GitHub</a></p>
</footer>

<script>
function makeChart(id, datasets, labels) {{
  const ctx = document.getElementById(id);
  if (!ctx || !datasets.length) return;
  new Chart(ctx, {{
    type: 'line',
    data: {{ labels, datasets }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ position: 'top', labels: {{ boxWidth: 12, font: {{ size: 11 }} }} }},
        tooltip: {{ callbacks: {{ label: c => c.dataset.label + ': ' + c.parsed.y + '%' }} }},
      }},
      scales: {{
        y: {{ min: 10, max: 75, ticks: {{ callback: v => v + '%', font: {{ size: 11 }} }}, grid: {{ color: '#f0f0f0' }} }},
        x: {{ ticks: {{ maxRotation: 30, maxTicksLimit: 6, font: {{ size: 11 }} }}, grid: {{ display: false }} }},
      }},
    }},
  }});
}}
{chr(10).join(CHART_QUEUE)}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Maine 2026 Poll Tracker — building...", file=sys.stderr)
    sections = list(SECTIONS)

    # Supplement Collins vs Platner with Wikipedia (exclude 3-way Mills polls)
    for s in sections:
        if s.get("wiki_url"):
            print(f"  Fetching Wikipedia for {s['id']}...", file=sys.stderr)
            wiki_polls = scrape_wiki_h2h(s["wiki_url"], s.get("wiki_require", []), s.get("wiki_exclude", []))
            existing_keys = {(p["date"], p["pollster"]) for p in s["polls"]}
            new = [p for p in wiki_polls if (p["date"], p["pollster"]) not in existing_keys]
            if new:
                print(f"  Added {len(new)} poll(s) from Wikipedia.", file=sys.stderr)
            s["polls"] = sorted(s["polls"] + new, key=lambda x: x["date"], reverse=True)

    last_updated = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    html = generate_html(sections, last_updated)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Done — index.html written.", file=sys.stderr)


if __name__ == "__main__":
    main()
