"""Render a terminal-inspired GitHub contribution calendar."""

import json
import random
from bisect import bisect_right
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "profile-assets"
WEEKS = 52
PAPER = "#f9e9cb"
COBALT = "#12249e"
LIME = "#d2ed45"
LEVELS = ("#e9dcc2", "#b8bce5", "#828fe0", "#4e61c3", "#152ba3")
THRESHOLDS = (1, 3, 9, 25)
FAN_COLORS = (COBALT, COBALT, "#101d78", PAPER, LIME)
FAN_ANGLES = (0, 12, 33, 54, 75)
FAN_SECONDS = (0, 8, 6, 4, 2)


def calendar_weeks(calendar):
    daily = {date.fromisoformat(day): count for day, count in calendar}
    latest = max(daily)
    last_sunday = latest - timedelta(days=(latest.weekday() + 1) % 7)
    start = last_sunday - timedelta(weeks=WEEKS - 1)
    return [
        [(day, daily.get(day, 0) if day <= latest else None)
         for day in (start + timedelta(weeks=week, days=row) for row in range(7))]
        for week in range(WEEKS)
    ]


def fan_tile(x, y, level, *, animate=False):
    color, angle = FAN_COLORS[level], FAN_ANGLES[level]
    opacity = ".22" if level == 0 else "1"
    rotor_class = f' class="fan-rotor fan-level-{level}"' if animate and level > 0 else ""
    return f"""<rect x="{x:g}" y="{y}" width="16" height="16" rx="2" fill="{LEVELS[level]}"/>
    <g transform="translate({x + 8:g} {y + 8}) rotate({angle})">
      <use href="#fan"{rotor_class} fill="{color}" opacity="{opacity}"/>
    </g>"""


def cell(day, count, x, y):
    if count is None:
        return f'<rect x="{x:g}" y="{y}" width="16" height="16" rx="2" fill="none" stroke="{COBALT}" stroke-opacity=".22"/>'

    level = bisect_right(THRESHOLDS, count)
    return f"""<g><title>{day:%b %d, %Y}: {count:,} contributions</title>
    {fan_tile(x, y, level, animate=True)}</g>"""


def panel(weeks, width, top):
    left, stride = 69, (width - 94) / len(weeks)
    marks = []
    for row, day_name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        marks.append(f'<text x="57" y="{top + row * 21 + 13}" text-anchor="end">{day_name}</text>')
    for index, week in enumerate(weeks):
        x = left + index * stride
        sunday = week[0][0]
        if (index == 0 or (index > 1 and sunday.month != weeks[index - 1][0][0].month)) and x < width - 42:
            marks.append(f'<text x="{x:g}" y="{top - 11}">{sunday:%b}</text>')
        marks.extend(cell(day, count, x, top + row * 21) for row, (day, count) in enumerate(week))
    return "\n".join(marks)


def render(weeks, mobile=False):
    width = 620 if mobile else 1200
    sections = [weeks[:26], weeks[26:]] if mobile else [weeks]
    height = 185 + len(sections) * 183
    first = weeks[0][0][0]
    last = max(day for week in weeks for day, count in week if count is not None)
    total = sum(count or 0 for week in weeks for _, count in week)
    rng = random.Random(191)
    grain = "".join(
        f'<circle cx="{rng.randrange(96)}" cy="{rng.randrange(80)}" r="{rng.choice((.4, .6, .75))}"/>'
        for _ in range(160)
    )
    plots = "\n".join(panel(section, width, 136 + index * 183) for index, section in enumerate(sections))
    labels = ("0", "1–2", "3–8", "9–24", "25+")
    positions = (218, 278, 354, 430, 526)
    legend = "".join(
        fan_tile(x, height - 41, index, animate=True)
        + f'<text x="{x + 22}" y="{height - 28}">{label}</text>'
        for index, (x, label) in enumerate(zip(positions, labels))
    )
    blades = "".join(
        f'<path d="M.6-1.15C.1-2.9 .7-6.1 2.5-6.2 4.8-6.3 4.5-3.6 3.2-2.1L1.4-.65Z" transform="rotate({angle})"/>'
        for angle in (0, 90, 180, 270)
    )
    speeds = "".join(
        f'.fan-level-{level}{{animation-duration:{seconds}s}}'
        for level, seconds in enumerate(FAN_SECONDS) if level > 0
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
    viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">
  <title id="title">GitHub contribution log</title>
  <desc id="description">{total:,} GitHub contributions from {first:%b %d, %Y} through {last:%b %d, %Y}.
    Each fan represents a day. Color and blade angle show the contribution range: 0, 1–2, 3–8, 9–24, or 25+.</desc>
  <style>
    @media (prefers-reduced-motion: no-preference) {{
      @keyframes spin-contribution-fan {{ to {{ transform: rotate(360deg); }} }}
      .fan-rotor {{
        transform-origin: 0 0;
        animation-name: spin-contribution-fan;
        animation-timing-function: linear;
        animation-iteration-count: infinite;
      }}
      {speeds}
    }}
  </style>
  <defs>
    <g id="fan">{blades}<circle r="1.15"/></g>
    <pattern id="grain" width="96" height="80" patternUnits="userSpaceOnUse">
      <g fill="{COBALT}" opacity=".13">{grain}</g>
    </pattern>
  </defs>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" fill="{PAPER}" stroke="{COBALT}" stroke-width="2"/>
  <rect x="2" y="2" width="{width - 4}" height="{height - 4}" fill="url(#grain)"/>
  <rect x="1" y="1" width="{width - 2}" height="60" fill="{COBALT}"/>
  <g fill="{COBALT}" font-family="Arial, Helvetica, sans-serif" font-size="18">
    <text x="27" y="39" fill="{LIME}" font-family="monospace" font-size="28" font-weight="700">&gt;_</text>
    <text x="83" y="39" fill="{PAPER}" font-size="27" font-weight="700">Contribution log</text>
    <text x="27" y="94" font-size="21">{total:,} GitHub contributions · {first:%b %Y} to {last:%b %Y}</text>
    {plots}
    <path d="M27 {height - 62}H{width - 27}" stroke="{COBALT}" stroke-opacity=".35"/>
    <text x="27" y="{height - 28}">Contributions per day</text>
    {legend}
  </g>
</svg>
"""


def main():
    calendar = json.loads((HERE / "data" / "calendar.json").read_text())
    weeks = calendar_weeks(calendar)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "activity.svg").write_text(render(weeks), encoding="utf-8")
    (OUT / "activity-mobile.svg").write_text(render(weeks, mobile=True), encoding="utf-8")


if __name__ == "__main__":
    main()
