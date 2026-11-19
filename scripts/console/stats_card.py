"""Draws the profile's GitHub stats card: five numbers and the rank ring.

Sits in the same cream/indigo card language as `metrics.py`, so it can be
dropped into the README as a normal panel. Renders a desktop and a mobile
slice; `rasterize.py` bakes both to WebP on the next profile run.

    python scripts/console/stats_card.py

Numbers come from data/stats.json (the same file the rest of the console
reads). Lines added is measured here, once, and cached in data/lines.json.
The rank is the letter github-readme-stats hands out; if that service is
unreachable the local reimplementation of its formula is used instead.
"""

import datetime as dt
import html
import json
import os
import random
import re
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE / "data"
OUT = ROOT / "profile-assets"

USER = "prx-my"
TOKEN = os.environ.get("GH_TOKEN", "")

# Committed run artefacts, not authored code: railmind is ~6M lines of JSON
# traces and would swamp the total.
EXCLUDE_REPOS = {"railmind"}

MIRROR = (
    "https://github-readme-stats-one-bice.vercel.app/api"
    f"?username={USER}&show_icons=true&include_all_commits=true"
)

# The mirror predates the current tier list and still grades on the old one.
LEGACY_ARC = {"S+": 1, "S": 12.5, "A++": 25, "A+": 37.5, "A": 50,
              "A-": 62.5, "B+": 75, "B": 87.5, "B-": 100, "C+": 90, "C": 100}

PAPER = "#f9e6cc"
INK = "#12249e"


# ─────────────────────────────── data ─────────────────────────────────
def api(path, retries=5):
    req = urllib.request.Request(
        f"https://api.github.com/{path}",
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": USER,
                 **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})},
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read().strip()
                if response.status == 202 or not body:
                    raise ValueError("stats not ready")
                return json.loads(body)
        except urllib.error.HTTPError as error:
            if error.code in (202, 403, 429) and attempt < retries:
                import time
                time.sleep(2 * (attempt + 1))
                continue
            raise
        except ValueError:
            if attempt < retries:
                import time
                time.sleep(2 * (attempt + 1))
                continue
            raise


def lines_added():
    """Additions across owned, non-fork repos, cached for a week."""
    cache = DATA / "lines.json"
    if cache.is_file():
        saved = json.loads(cache.read_text(encoding="utf-8"))
        age = dt.date.today() - dt.date.fromisoformat(saved["measured"])
        if age.days < 7:
            return saved["added"]

    total, page = 0, 1
    while True:
        batch = api(f"users/{USER}/repos?per_page=100&type=owner&page={page}")
        for repo in batch:
            if repo["fork"] or repo["name"] in EXCLUDE_REPOS:
                continue
            try:
                for contributor in api(f"repos/{USER}/{repo['name']}/stats/contributors") or []:
                    if (contributor.get("author") or {}).get("login") == USER:
                        total += sum(week["a"] for week in contributor["weeks"])
            except Exception as error:  # empty repos and uncomputed stats
                print(f"  skipped {repo['name']}: {error}")
        if len(batch) < 100:
            break
        page += 1

    cache.write_text(
        json.dumps({"added": total, "measured": dt.date.today().isoformat()}, indent=2) + "\n",
        encoding="utf-8",
    )
    return total


def rank_from_mirror():
    try:
        request = urllib.request.Request(MIRROR, headers={"User-Agent": USER})
        with urllib.request.urlopen(request, timeout=20) as response:
            svg = response.read().decode("utf-8", "replace")
        block = svg[svg.find('class="rank-text"'):][:600]
        found = re.search(r"<text[^>]*>\s*([A-S][+-]{0,2})\s*<", block)
        return found.group(1) if found else ""
    except Exception:
        return ""


def rank_local(commits, prs, issues, stars, followers):
    """github-readme-stats v2, reimplemented, for when the mirror is down."""
    exp_cdf = lambda x: 1 - 2 ** -x
    log_cdf = lambda x: x / (1 + x)
    medians = dict(commits=1000, prs=50, issues=25, reviews=2, stars=50, followers=10)
    weights = dict(commits=2, prs=3, issues=1, reviews=1, stars=4, followers=1)
    score = (
        weights["commits"] * exp_cdf(commits / medians["commits"])
        + weights["prs"] * exp_cdf(prs / medians["prs"])
        + weights["issues"] * exp_cdf(issues / medians["issues"])
        + weights["stars"] * log_cdf(stars / medians["stars"])
        + weights["followers"] * log_cdf(followers / medians["followers"])
    ) / sum(weights.values())
    percentile = (1 - score) * 100
    thresholds = [1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100]
    levels = ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"]
    return next(level for limit, level in zip(thresholds, levels) if percentile <= limit), percentile


def human(number):
    # Exact up to five digits: 1,428 reads stronger than 1.4k. Only the
    # six-figure lines-added total gets shortened.
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    return f"{number / 1000:.1f}k" if number >= 10_000 else f"{number:,}"


# ─────────────────────────────── drawing ──────────────────────────────
def paper_edge(width, height):
    """The hero's torn lower paper edge, split to the card's width."""
    from base64 import b64encode
    from io import BytesIO

    from PIL import Image

    strips = sorted((HERE / "art").glob("hero-edge-*.png"))
    with Image.open(strips[0]) as first:
        strip_width, strip_height = first.size
    paper = Image.new("RGB", (strip_width * len(strips), strip_height))
    for index, path in enumerate(strips):
        with Image.open(path) as strip:
            paper.paste(strip, (index * strip_width, 0))
    with BytesIO() as buffer:
        paper.resize((width, height), Image.Resampling.LANCZOS).save(buffer, format="PNG")
        return b64encode(buffer.getvalue()).decode("ascii")


def grain(width, height, count, seed):
    rng = random.Random(seed)
    return "".join(
        f'<circle cx="{rng.randint(0, width)}" cy="{rng.randint(0, height)}" '
        f'r="{rng.choice((0.35, 0.5, 0.75))}"/>'
        for _ in range(count)
    )


def ring(cx, cy, radius, stroke, letter, percentile):
    circumference = 2 * 3.141592653589793 * radius
    filled = circumference * (1 - min(percentile, 100) / 100)
    return f'''
  <g transform="rotate(-90 {cx} {cy})">
    <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{INK}" stroke-width="{stroke}" opacity=".16"/>
    <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{INK}" stroke-width="{stroke}"
            stroke-linecap="round" stroke-dasharray="{filled:.1f} {circumference:.1f}"/>
  </g>
  <text x="{cx}" y="{cy + radius * 0.18:g}" text-anchor="middle" font-size="{radius * 0.62:g}"
        font-weight="900">{html.escape(letter)}</text>'''


def card(rows, letter, percentile, *, width, height, title_size, row_size,
         row_gap, first_row, label_x, value_x, ring_cx, ring_cy, ring_r,
         caption_y, caption_size, edge_height, seed, dots):
    edge = paper_edge(width, edge_height)
    table = "".join(
        f'<text x="{label_x}" y="{first_row + index * row_gap}" font-size="{row_size}">{html.escape(label)}</text>'
        f'<text x="{value_x}" y="{first_row + index * row_gap}" font-size="{row_size}" '
        f'font-weight="700" text-anchor="end">{html.escape(value)}</text>'
        for index, (label, value) in enumerate(rows)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
    viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">
  <title id="title">GitHub stats</title>
  <defs>
    <linearGradient id="fade" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <mask id="edge"><rect width="{width}" height="{edge_height:g}" fill="url(#fade)"/></mask>
  </defs>
  <rect width="{width}" height="{height}" fill="{PAPER}"/>
  <image width="{width}" height="{edge_height:g}" preserveAspectRatio="none" mask="url(#edge)" href="data:image/png;base64,{edge}"/>
  <g fill="{INK}" opacity=".14">{grain(width, height, dots, seed)}</g>
  <g fill="{INK}" font-family="Arial, Helvetica, sans-serif">
    <text x="{label_x}" y="{first_row - row_gap * 1.6:g}" font-size="{title_size}" font-weight="700">GitHub stats</text>
    <path d="M{label_x} {first_row - row_gap * 1.35:g}H{value_x}" fill="none" stroke="{INK}" stroke-width="2"/>
    {table}
    {ring(ring_cx, ring_cy, ring_r, max(10, ring_r * 0.19), letter, percentile)}
    <text x="{ring_cx}" y="{caption_y}" font-size="{caption_size}" text-anchor="middle">rank · top {max(1, round(percentile))}%</text>
  </g>
</svg>
'''


def alt_text(rows, letter, percentile):
    (_, commits), (_, year), (_, lines), (_, repos), (_, followers) = rows
    return (
        f"Stats: {commits} commits all time, {year} this year, {lines} lines added, "
        f"{repos} public repos, {followers} followers. Rank {letter} on the legacy "
        f"github-readme-stats scale (top {max(1, round(percentile))}%)."
    )


def main():
    stats = json.loads((DATA / "stats.json").read_text(encoding="utf-8"))
    year = stats["year"]
    rows = [
        ("Total commits", human(stats["commits_all"])),
        (f"Commits in {year}", human(stats["commits_year"])),
        ("Lines added", human(lines_added())),
        ("Public repos", f'{stats["public_repos"]:,}'),
        ("Followers", f'{stats["followers"]:,}'),
    ]

    letter = rank_from_mirror()
    if letter in LEGACY_ARC:
        percentile = LEGACY_ARC[letter]
        source = "mirror"
    else:
        letter, percentile = rank_local(
            stats["commits_all"], stats["prs"], 0, stats["stars"], stats["followers"]
        )
        source = "local"

    (OUT / "stats-card.svg").write_text(
        card(rows, letter, percentile, width=1200, height=500, title_size=42,
             row_size=24, row_gap=38, first_row=280, label_x=54, value_x=704,
             ring_cx=950, ring_cy=330, ring_r=96, caption_y=474, caption_size=20,
             edge_height=120, seed=72, dots=2400),
        encoding="utf-8",
    )
    (OUT / "stats-card-mobile.svg").write_text(
        card(rows, letter, percentile, width=358, height=590, title_size=26,
             row_size=15, row_gap=30, first_row=140, label_x=20, value_x=338,
             ring_cx=179, ring_cy=380, ring_r=74, caption_y=500, caption_size=14,
             edge_height=36, seed=72, dots=900),
        encoding="utf-8",
    )

    print(alt_text(rows, letter, percentile))
    print(f"rank source: {source} -> {letter} (arc {percentile})")
    for label, value in rows:
        print(f"  {label}: {value}")


if __name__ == "__main__":
    main()
