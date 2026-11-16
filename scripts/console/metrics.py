"""Render the SVG cards from the profile workflow's existing GitHub snapshot."""

import html
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "profile-assets" / "metrics"


def render_card(value, label, detail, *, compact=()):
    value, detail = html.escape(value), html.escape(detail)
    title = f"{value}, {html.escape(label)}. {detail}."
    width, height = (132, 101) if compact else (400, 202)
    rng = random.Random(191)
    grain = "".join(
        f'<circle cx="{rng.randint(4, width - 4)}" cy="{rng.randint(4, height - 4)}" '
        f'r="{rng.choice((0.35, 0.5, 0.75))}"/>'
        for _ in range(160 if compact else 950)
    )
    if compact:
        lines = "\n    ".join(
            f'<text x="11" y="{70 + index * 16}" font-size="15" font-weight="700">{html.escape(line)}</text>'
            for index, line in enumerate(compact)
        )
        font_size = min(40, 170 / len(value))
        content = f'''<text x="11" y="40" font-size="{font_size:g}" font-weight="900">{value}</text>
    <path d="M11 49H121" fill="none" stroke="#12249e"/>
    {lines}'''
    else:
        content = f'''<text x="22" y="92" font-size="83" font-weight="900">{value}</text>
    <path d="M22 111H378" fill="none" stroke="#12249e" stroke-width="1.5"/>
    <text x="22" y="146" font-size="29" font-weight="700">{html.escape(label)}</text>
    <text x="22" y="177" font-size="23">{detail}</text>'''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
    viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">
  <title id="title">{title}</title>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" fill="#f9e9cb" stroke="#12249e" stroke-width="2"/>
  <g fill="#12249e" opacity=".14">{grain}</g>
  <g fill="#12249e" font-family="Arial, Helvetica, sans-serif">
    {content}
  </g>
</svg>
'''


def main():
    stats = json.loads((HERE / "data" / "stats.json").read_text())
    cards = {
        "streak": (
            f'{stats["streak_current"]:,}', "Contribution streak", "Consecutive days on GitHub",
            ("Contribution", "streak"),
        ),
        "featured-fix": (
            "5,000", "File scan limit", "OWASP CVE Lite CLI fix", ("File scan", "limit"),
        ),
        "merged": (
            f'{stats["prs_merged"]:,}', "Pull requests merged", "Across GitHub repositories",
            ("Pull requests", "merged"),
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, (value, label, detail, compact) in cards.items():
        (OUT / f"{slug}.svg").write_text(render_card(value, label, detail), encoding="utf-8")
        (OUT / f"{slug}-mobile.svg").write_text(
            render_card(value, label, detail, compact=compact), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
