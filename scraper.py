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
             "sample": None, "moe": "Avg",
             "candidates": {"Graham Platner (D)": 61, "Janet Mills (D)": 28, "Undecided": 11}},
            {"date": "2026-03-21", "pollster": "Emerson College",
             "sample": 530, "moe": 4.2,
             "candidates": {"Graham Platner (D)": 55, "Janet Mills (D)": 28, "Undecided": 13}},
            {"date": "2026-02-16", "pollster": "UNH Survey Center",
             "sample": 462, "moe": 4.6,
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
             "sample": None, "moe": "Avg",
             "candidates": {"Susan Collins (R)": 44, "Graham Platner (D)": 44, "Other/Undecided": 12}},
            {"date": "2026-04-09", "pollster": "Race to the WH",
             "sample": None, "moe": "Avg",
             "candidates": {"Susan Collins (R)": 41, "Graham Platner (D)": 48, "Other/Undecided": 11}},
            {"date": "2026-03-21", "pollster": "Emerson College",
             "sample": 1075, "moe": 2.9,
             "candidates": {"Susan Collins (R)": 41, "Graham Platner (D)": 48, "Other/Undecided": 11}},
            {"date": "2026-02-16", "pollster": "UNH Survey Center",
             "sample": 462, "moe": 4.6,
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
             "sample": None, "moe": "Avg",
             "candidates": {"Susan Collins (R)": 45, "Janet Mills (D)": 45, "Other/Undecided": 10}},
            {"date": "2026-03-21", "pollster": "Emerson College",
             "sample": 1075, "moe": 2.9,
             "candidates": {"Susan Collins (R)": 43, "Janet Mills (D)": 46, "Other/Undecided": 11}},
            {"date": "2026-02-16", "pollster": "UNH Survey Center",
             "sample": 462, "moe": 4.6,
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
             "sample": 810, "moe": 3.7,
             "candidates": {"Nirav Shah (D)": 24, "Angus King III (D)": 24,
                            "Hannah Pingree (D)": 18, "Shenna Bellows (D)": 16,
                            "Troy Jackson (D)": 10, "Undecided": 8}},
            {"date": "2025-12-11", "pollster": "Pan Atlantic Research",
             "sample": 810, "moe": 3.7,
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
             "sample": 810, "moe": 3.7,
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
             "sample": 810, "moe": 3.7,
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

            raw_pollster = texts[pollster_col] if 0 <= pollster_col < len(texts) else "Unknown"
            pollster = re.sub(r"\s*\[\s*\d+\s*\]", "", raw_pollster).strip()
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

            # Estimate MoE from sample size if not otherwise known (95% CI, p=0.5)
            est_moe = round(196 / (sample_num ** 0.5), 1) if sample_num else None
            polls.append({"date": date_str, "pollster": pollster,
                          "sample": sample_num, "moe": est_moe, "candidates": cand_pcts})
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


def fmt_moe(moe) -> str:
    if isinstance(moe, (int, float)):
        return f"±{moe}%"
    if isinstance(moe, str):
        return moe  # e.g. "Avg"
    return "—"


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
    meta_heads = "".join(f'<th class="th-meta">{h}</th>' for h in ["Date", "Pollster", "Sample", "MoE"])
    cand_heads = "".join(f'<th class="th-cand th-{pclass(c)}">{short_name(c)}</th>' for c in all_cands)
    thead = meta_heads + cand_heads
    tbody = ""
    for p in polls:
        row = (f"<td>{p['date']}</td><td>{p['pollster']}</td>"
               f"<td>{p['sample'] or '—'}</td>"
               f"<td>{fmt_moe(p.get('moe'))}</td>")
        for c in all_cands:
            v = p["candidates"].get(c)
            css = pclass(c)
            row += f'<td class="pct-cell {css}">{v}%</td>' if v is not None else "<td>—</td>"
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
    thead = "".join(f"<th>{h}</th>" for h in ["Date", "Pollster", "Sample", "MoE"] + all_cands)
    tbody = ""
    for p in polls:
        row = (f"<td>{p['date']}</td><td>{p['pollster']}</td>"
               f"<td>{p['sample'] or '—'}</td><td>{fmt_moe(p.get('moe'))}</td>")
        for c in all_cands:
            v = p["candidates"].get(c)
            css = pclass(c)
            row += f'<td class="pct-cell {css}">{v}%</td>' if v is not None else "<td>—</td>"
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
        body_html += f'<section class="race-block" id="{meta["anchor"]}"><div class="race-block-header"><h2>{meta["label"]}</h2><span class="race-date">Primary: Jun 9 &bull; General: Nov 3, 2026</span></div>{inner}</section>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Maine 2026 Poll Tracker | Bangor Daily News</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f2f1ed;color:#111;line-height:1.55}}

    /* ── BDN Top bar ── */
    .bdn-topbar{{background:#2d6535;padding:0.45rem 1.25rem;display:flex;align-items:center;gap:0.75rem}}
    .bdn-bug{{display:inline-flex;align-items:center;justify-content:center;background:#fff;color:#2d6535;font-weight:900;font-size:0.85rem;letter-spacing:0.02em;width:34px;height:34px;flex-shrink:0}}
    .bdn-topbar-text{{color:#fff;font-size:0.82rem;font-weight:600;letter-spacing:0.04em;text-transform:uppercase}}
    .bdn-topbar a{{color:rgba(255,255,255,0.75);font-size:0.78rem;margin-left:auto;text-decoration:none}}
    .bdn-topbar a:hover{{color:#fff}}

    /* ── Masthead ── */
    .masthead{{background:#fff;border-bottom:3px solid #2d6535;padding:1.1rem 1.25rem 0.9rem}}
    .masthead h1{{font-size:clamp(1.6rem,4vw,2.4rem);font-weight:900;letter-spacing:-0.5px;color:#111;line-height:1.1;text-transform:uppercase}}
    .masthead .kicker{{font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#2d6535;margin-bottom:0.35rem}}
    .masthead .meta{{font-size:0.78rem;color:#666;margin-top:0.4rem}}

    /* ── Race nav ── */
    .race-nav{{background:#2d6535;display:flex;overflow-x:auto;gap:0}}
    .nav-item{{padding:0.6rem 1.2rem;font-size:0.82rem;font-weight:700;color:rgba(255,255,255,0.75);text-decoration:none;text-transform:uppercase;letter-spacing:0.05em;white-space:nowrap;border-bottom:3px solid transparent;transition:all 0.15s}}
    .nav-item:hover{{color:#fff;background:rgba(255,255,255,0.1);border-bottom-color:#fff}}

    /* ── Layout ── */
    main{{max-width:900px;margin:1.5rem auto;padding:0 1rem 3rem}}

    /* ── Race block ── */
    .race-block{{margin-bottom:2rem;border:1px solid #d8d7d2}}
    .race-block-header{{background:#2d6535;padding:0.7rem 1.1rem;display:flex;align-items:baseline;gap:0.6rem}}
    .race-block-header h2{{font-size:1rem;font-weight:800;color:#fff;text-transform:uppercase;letter-spacing:0.08em}}
    .race-block-header .race-date{{font-size:0.72rem;color:rgba(255,255,255,0.7);margin-left:auto}}

    /* ── Subsection ── */
    .subsection{{background:#fff;padding:1.25rem 1.1rem;border-top:1px solid #e5e3df}}
    .subsection:first-of-type{{border-top:none}}
    .subsection-header{{display:flex;align-items:center;gap:0.55rem;margin-bottom:0.4rem}}
    .subsection-header h3{{font-size:0.95rem;font-weight:700;color:#111}}
    .subsection-badge{{font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;padding:0.18rem 0.5rem;border:1px solid currentColor}}
    .general{{color:#2d6535;border-color:#2d6535;background:#edf5ee}}
    .dem-badge{{color:#1a56db;border-color:#1a56db;background:#eff3ff}}
    .rep-badge{{color:#c81e1e;border-color:#c81e1e;background:#fdf2f2}}
    .section-note{{font-size:0.77rem;color:#666;margin-bottom:0.9rem;line-height:1.4}}

    /* ── Head-to-head ── */
    .hth-wrap{{display:flex;align-items:stretch;margin-bottom:0.6rem;border:1px solid #d8d7d2;overflow:hidden}}
    .hth-cand{{flex:1;padding:1rem 0.9rem;text-align:center}}
    .hth-cand.dem{{background:#f0f4ff}}
    .hth-cand.rep{{background:#fff4f4}}
    .hth-cand.leader.dem{{background:#dde8ff}}
    .hth-cand.leader.rep{{background:#fddede}}
    .hth-vs{{display:flex;align-items:center;padding:0 0.6rem;font-weight:800;font-size:0.75rem;color:#999;background:#f8f7f4;border-left:1px solid #d8d7d2;border-right:1px solid #d8d7d2}}
    .hth-name{{font-size:0.95rem;font-weight:800;color:#111;text-transform:uppercase;letter-spacing:0.02em}}
    .hth-party{{font-size:0.72rem;color:#555;margin:0.15rem 0 0.5rem;font-weight:600;text-transform:uppercase;letter-spacing:0.05em}}
    .hth-pct{{font-size:2.4rem;font-weight:900;line-height:1}}
    .hth-cand.dem .hth-pct{{color:#1a56db}}
    .hth-cand.rep .hth-pct{{color:#c81e1e}}
    .spread-line{{font-size:0.78rem;color:#555;margin-bottom:1rem;text-align:center;font-style:italic}}

    /* ── Primary bars ── */
    .bars-wrap{{margin-bottom:1rem}}
    .bar-row{{display:flex;align-items:center;gap:0.7rem;margin-bottom:0.55rem}}
    .bar-name{{width:140px;font-size:0.82rem;font-weight:600;color:#222;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .bar-track{{flex:1;background:#e8e7e3;height:20px;overflow:hidden}}
    .bar-fill{{height:100%;transition:width 0.4s}}
    .bar-fill.dem{{background:#1a56db}}
    .bar-fill.rep{{background:#c81e1e}}
    .bar-fill.und{{background:#888}}
    .bar-pct{{width:42px;font-size:0.85rem;font-weight:700;color:#111;text-align:right;flex-shrink:0}}

    /* ── Chart ── */
    .chart-wrap{{position:relative;height:195px;margin:0.9rem 0}}

    /* ── Table ── */
    .tbl-wrap{{overflow-x:auto;margin-top:1rem;border:1px solid #d8d7d2}}
    table{{width:100%;border-collapse:collapse;font-size:0.8rem}}
    thead tr{{background:#2d6535;color:#fff}}
    thead th{{padding:0.5rem 0.75rem;text-align:left;font-weight:700;white-space:nowrap;letter-spacing:0.03em;border-right:1px solid rgba(255,255,255,0.15)}}
    thead th:last-child{{border-right:none}}
    thead .th-cand{{text-align:center}}
    thead .th-dem{{background:#1a3d99}}
    thead .th-rep{{background:#991b1b}}
    thead .th-und{{background:#4b5563}}
    tbody tr{{border-bottom:1px solid #e5e3df}}
    tbody tr:last-child{{border-bottom:none}}
    tbody tr:hover{{background:#faf9f6}}
    tbody td{{padding:0.48rem 0.75rem;white-space:nowrap;border-right:1px solid #eeece8}}
    tbody td:last-child{{border-right:none}}
    .pct-cell{{text-align:center;font-weight:700}}
    .pct-cell.dem{{color:#1a3d99;background:#eff3ff}}
    .pct-cell.rep{{color:#991b1b;background:#fef2f2}}
    .pct-cell.und{{color:#555;background:#f8f7f4}}

    .no-polling{{color:#999;font-size:0.85rem;font-style:italic;padding:0.4rem 0}}

    /* ── Footer ── */
    footer{{border-top:3px solid #2d6535;background:#fff;padding:1.25rem;text-align:center;font-size:0.76rem;color:#666;margin-top:0}}
    footer a{{color:#2d6535;text-decoration:none;font-weight:600}}
    footer a:hover{{text-decoration:underline}}
    .footer-bdn{{font-weight:800;color:#111;font-size:0.82rem;margin-bottom:0.3rem;text-transform:uppercase;letter-spacing:0.05em}}

    @media(max-width:580px){{
      .masthead h1{{font-size:1.5rem}}
      .hth-pct{{font-size:1.8rem}}
      .hth-name{{font-size:0.85rem}}
      .bar-name{{width:105px;font-size:0.76rem}}
    }}
  </style>
</head>
<body>

<div class="bdn-topbar">
  <div class="bdn-bug">BDN</div>
  <span class="bdn-topbar-text">Bangor Daily News</span>
  <a href="https://www.bangordailynews.com/" target="_blank">bangordailynews.com &rarr;</a>
</div>

<div class="masthead">
  <div class="kicker">Maine Politics &bull; Data</div>
  <h1>Maine 2026 Poll Tracker</h1>
  <p class="meta">Senate &bull; Governor &bull; CD-1 &bull; CD-2 &mdash; primaries &amp; general election matchups &bull; Updated {last_updated}</p>
</div>

<nav class="race-nav">{nav_items}</nav>

<main>
{body_html}
</main>

<footer>
  <p class="footer-bdn">Bangor Daily News</p>
  <p>Sources: Emerson College &bull; UNH Survey Center &bull; Pan Atlantic Research &bull; Punchbowl News &bull; RealClearPolling &bull; Wikipedia</p>
  <p style="margin-top:0.4rem"><a href="https://github.com/sloftus-lab/maine-poll-tracker" target="_blank">View source on GitHub</a></p>
</footer>

<div id="pw-overlay" style="display:none;position:fixed;inset:0;background:#f2f1ed;z-index:9999;display:flex;align-items:center;justify-content:center;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
  <div style="background:#fff;border:1px solid #d8d7d2;border-top:4px solid #2d6535;padding:2.5rem 2rem;width:100%;max-width:360px;text-align:center">
    <div style="display:inline-flex;align-items:center;justify-content:center;background:#2d6535;color:#fff;font-weight:900;font-size:0.85rem;width:36px;height:36px;margin-bottom:1rem">BDN</div>
    <h2 style="font-size:1rem;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;color:#111;margin-bottom:0.3rem">Maine 2026 Poll Tracker</h2>
    <p style="font-size:0.78rem;color:#666;margin-bottom:1.25rem">This page is password protected.</p>
    <input id="pw-input" type="password" placeholder="Password" autofocus
      style="width:100%;padding:0.6rem 0.75rem;border:1px solid #d8d7d2;font-size:0.9rem;margin-bottom:0.75rem;outline:none;font-family:inherit"
      onkeydown="if(event.key==='Enter')checkPw()">
    <button onclick="checkPw()"
      style="width:100%;padding:0.6rem;background:#2d6535;color:#fff;border:none;font-size:0.85rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;cursor:pointer">
      Enter
    </button>
    <p id="pw-error" style="color:#c81e1e;font-size:0.78rem;margin-top:0.6rem;min-height:1em"></p>
  </div>
</div>

<script>
(function() {{
  const HASH = 'ad099e69988bc34a8453984aef9a6feebb92987352ecd3713529e6f2d087219a';
  const KEY  = 'bdn_poll_auth';
  if (sessionStorage.getItem(KEY) === HASH) {{
    document.getElementById('pw-overlay').style.display = 'none';
  }}
  window.checkPw = async function() {{
    const val = document.getElementById('pw-input').value;
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(val));
    const hex = Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2,'0')).join('');
    if (hex === HASH) {{
      sessionStorage.setItem(KEY, HASH);
      document.getElementById('pw-overlay').style.display = 'none';
    }} else {{
      document.getElementById('pw-error').textContent = 'Incorrect password.';
      document.getElementById('pw-input').value = '';
      document.getElementById('pw-input').focus();
    }}
  }};
}})();

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
