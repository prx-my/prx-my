"""Render the SVG cards from the profile workflow's existing GitHub snapshot."""

import html
from base64 import b64encode
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "profile-assets" / "metrics"
# The hero print's bottom paper, split per card, continues and fades out so the hero joins the cards seamlessly.
EDGE_HEIGHT = 48 / 480  # strip height per unit of card width


def render_card(value, label, detail, index, *, compact=()):
    value, detail = html.escape(value), html.escape(detail)
    title = f"{value}, {html.escape(label)}. {detail}."
    width, height = (132, 101) if compact else (400, 202)
    rng = random.Random(191)
    grain = "".join(
        f'<circle cx="{rng.randint(0, width)}" cy="{rng.randint(0, height)}" '
        f'r="{rng.choice((0.35, 0.5, 0.75))}"/>'
        for _ in range(160 if compact else 950)
    )
    # Columns share the paper, so each card offsets its text to keep equal gutters across the row.
    x = (13.3 - 4.4 * index) if compact else (29 - 4 * index)
    edge = b64encode((HERE / "art" / f"hero-edge-{index}.png").read_bytes()).decode("ascii")
    edge_height = width * EDGE_HEIGHT
    if compact:
        lines = "\n    ".join(
            f'<text x="{x:g}" y="{70 + row * 16}" font-size="15" font-weight="700">{html.escape(line)}</text>'
            for row, line in enumerate(compact)
        )
        font_size = min(40, 170 / len(value))
        content = f'''<text x="{x:g}" y="40" font-size="{font_size:g}" font-weight="900">{value}</text>
    <path d="M{x:g} 49h114" fill="none" stroke="#12249e"/>
    {lines}'''
    else:
        content = f'''<text x="{x}" y="92" font-size="83" font-weight="900">{value}</text>
    <path d="M{x} 111h350" fill="none" stroke="#12249e" stroke-width="1.5"/>
    <text x="{x}" y="146" font-size="29" font-weight="700">{html.escape(label)}</text>
    <text x="{x}" y="177" font-size="23">{detail}</text>'''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
    viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">
  <title id="title">{title}</title>
  <defs>
    <linearGradient id="fade" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <mask id="edge"><rect width="{width}" height="{edge_height:g}" fill="url(#fade)"/></mask>
  </defs>
  <rect width="{width}" height="{height}" fill="#f9e6cc"/>
  <image width="{width}" height="{edge_height:g}" preserveAspectRatio="none" mask="url(#edge)" href="data:image/png;base64,{edge}"/>
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
    for index, (slug, (value, label, detail, compact)) in enumerate(cards.items()):
        (OUT / f"{slug}.svg").write_text(render_card(value, label, detail, index), encoding="utf-8")
        (OUT / f"{slug}-mobile.svg").write_text(
            render_card(value, label, detail, index, compact=compact), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
