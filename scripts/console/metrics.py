"""Render the SVG cards from the profile workflow's existing GitHub snapshot."""

import html
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "profile-assets" / "metrics"


def render_card(value, label, detail):
    value, label, detail = map(html.escape, (value, label, detail))
    rng = random.Random(191)
    grain = "".join(
        f'<circle cx="{rng.randint(4, 396)}" cy="{rng.randint(4, 198)}" '
        f'r="{rng.choice((0.35, 0.5, 0.75))}"/>'
        for _ in range(950)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="202"
    viewBox="0 0 400 202" role="img" aria-labelledby="title">
  <title id="title">{value}, {label}. {detail}.</title>
  <rect x="2" y="2" width="396" height="198" fill="#f9e9cb" stroke="#12249e" stroke-width="2"/>
  <g fill="#12249e" opacity=".14">{grain}</g>
  <g fill="#12249e" font-family="Arial, Helvetica, sans-serif">
    <text x="22" y="92" font-size="83" font-weight="900">{value}</text>
    <path d="M22 111H378" fill="none" stroke="#12249e" stroke-width="1.5"/>
    <text x="22" y="146" font-size="29" font-weight="700">{label}</text>
    <text x="22" y="177" font-size="23">{detail}</text>
  </g>
</svg>
"""


def main():
    stats = json.loads((HERE / "data" / "stats.json").read_text())
    cards = {
        "streak": (f'{stats["streak_current"]:,}', "Contribution streak", "Consecutive days on GitHub"),
        "featured-fix": ("5,000", "File scan limit", "OWASP CVE Lite CLI fix"),
        "merged": (f'{stats["prs_merged"]:,}', "Pull requests merged", "Across GitHub repositories"),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, card in cards.items():
        (OUT / f"{slug}.svg").write_text(render_card(*card), encoding="utf-8")


if __name__ == "__main__":
    main()
