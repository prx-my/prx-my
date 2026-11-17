"""Render the profile metrics from GitHub data and the editable records."""

import html
from base64 import b64encode
import json
from io import BytesIO
import random
from pathlib import Path

from PIL import Image

from profile_records import count_entries
from stamp import README, ROOT

HERE = Path(__file__).resolve().parent
OUT = ROOT / "profile-assets" / "metrics"
START = "<!-- Profile metrics -->"
END = "<!-- End profile metrics -->"
RAW = "https://raw.githubusercontent.com/prx-my/prx-my/main/"
# The hero print's bottom paper, split per card, continues and fades out so the hero joins the cards seamlessly.
EDGE_HEIGHT = 48 / 480  # strip height per unit of card width


def render_card(value, label, detail, edge, *, compact=()):
    value, detail = html.escape(value), html.escape(detail)
    title = f"{value}, {html.escape(label)}. {detail}."
    width, height = (132, 134) if compact else (400, 202)
    rng = random.Random(191)
    grain = "".join(
        f'<circle cx="{rng.randint(0, width)}" cy="{rng.randint(0, height)}" '
        f'r="{rng.choice((0.35, 0.5, 0.75))}"/>'
        for _ in range(160 if compact else 950)
    )
    x = 8 if compact else 27
    edge_height = width * EDGE_HEIGHT
    if compact:
        lines = "\n    ".join(
            f'<text x="{x:g}" y="{82 + row * 17}" font-size="15" font-weight="700">{html.escape(line)}</text>'
            for row, line in enumerate(compact)
        )
        font_size = min(40, 170 / len(value))
        content = f'''<text x="{x:g}" y="48" font-size="{font_size:g}" font-weight="900">{value}</text>
    <path d="M{x:g} 60h116" fill="none" stroke="#12249e"/>
    {lines}
    <text x="{x}" y="121" font-size="12">{detail}</text>'''
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


def paper_edges(count):
    """Re-cut the existing continuous paper strip to match the new card widths."""
    strips = sorted((HERE / "art").glob("hero-edge-*.png"))
    with Image.open(strips[0]) as first:
        width, height = first.size
    paper = Image.new("RGB", (width * len(strips), height))
    for index, path in enumerate(strips):
        with Image.open(path) as strip:
            paper.paste(strip, (index * width, 0))
    for index in range(count):
        bounds = (paper.width * index // count, 0, paper.width * (index + 1) // count, height)
        with BytesIO() as buffer:
            paper.crop(bounds).save(buffer, format="PNG")
            yield b64encode(buffer.getvalue()).decode("ascii")


def write_readme(cards):
    text = README.read_text(encoding="utf-8")
    before, start, remainder = text.partition(START)
    _, end, after = remainder.partition(END)
    if not start or not end:
        raise ValueError("README is missing the profile metrics markers")

    images = []
    for slug, value, label, detail, _, url in cards:
        alt = html.escape(f"{label}: {value}. {detail}.", quote=True)
        path = f"profile-assets/metrics/{slug}"
        images.append(
            f'<a href="{html.escape(url, quote=True)}"><picture>'
            f'<source media="(max-width: 600px)" srcset="{RAW}{path}-mobile.webp">'
            f'<img src="{path}.webp" width="25%" align="top" alt="{alt}"></picture></a>'
        )
    body = '\n<div>\n  ' + "".join(images) + '\n</div>\n'
    README.write_text(before + start + body + end + after, encoding="utf-8")


def main():
    stats = json.loads((HERE / "data" / "stats.json").read_text(encoding="utf-8"))
    cards = [
        ("streak", f'{stats["streak_current"]:,}', "Contribution streak", "I code daily",
         ("Contribution", "streak"), "https://github.com/prx-my#contributions"),
        ("hackathons", f'{count_entries("hackthons.md", "win"):,}', "Hackathon wins", "I go on stage",
         ("Hackathon", "wins"), "hackthons.md"),
        ("client-projects", f'{count_entries("client.md", "shipped"):,}', "Client projects shipped",
         "People can trust me", ("Client projects", "shipped"), "client.md"),
        ("merged", f'{stats["prs_merged"]:,}', "Pull requests merged", "I give back in code",
         ("Pull requests", "merged"), "https://github.com/search?q=is%3Apr+is%3Amerged+author%3Aprx-my&type=pullrequests"),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    for (slug, value, label, detail, compact, _), edge in zip(cards, paper_edges(len(cards)), strict=True):
        (OUT / f"{slug}.svg").write_text(render_card(value, label, detail, edge), encoding="utf-8")
        (OUT / f"{slug}-mobile.svg").write_text(
            render_card(value, label, detail, edge, compact=compact), encoding="utf-8"
        )
    write_readme(cards)


if __name__ == "__main__":
    main()
