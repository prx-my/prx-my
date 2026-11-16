"""Render the section titles that sit on the profile's shared paper."""

import html
import random
from base64 import b64encode
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATUS = "Open to opportunities"
STATUS_DETAIL = "Backend & full-stack · Software engineering internships · Onsite/Remote"
STATUS_DETAIL_MOBILE = "Backend & full-stack · SWE internships · Onsite/Remote"
PAPER = "#f9e6cc"  # matches the hero print's paper so the slices join without a seam
INK = "#12249e"
LIME = "#d2ed45"
# Space under each title (desktop, mobile), less the paper each section's artwork already carries,
# so every title sits the same distance from what it introduces.
TITLES = {
    "work": ("Selected work", 26, 16),
    "open-source": ("Open source", 4, 6),
    "stack": ("Tech stack", 0, 4),
    "activity": ("Contribution log", 13, 5),
    "contact": ("Contact", 13, 10),
}
# Desktop draws at 831 units (GitHub's README width), mobile at 358, so units are pixels.
LAYOUT = {
    False: dict(width=831, gutter=20, top=34, badge=34, gap=14, size=25),
    True: dict(width=358, gutter=12, top=24, badge=26, gap=10, size=19),
}


def grain(width, height):
    rng = random.Random(191)
    return "".join(
        f'<circle cx="{rng.randrange(width)}" cy="{rng.randrange(height)}" r="{rng.choice((.4, .6, .75))}"/>'
        for _ in range(width * height // 260)
    )


def render(title, bottom, mobile):
    s = LAYOUT[mobile]
    width, height = s["width"], s["top"] + s["badge"] + bottom
    x, y, badge = s["gutter"], s["top"], s["badge"]
    middle = y + badge / 2
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
  <rect width="{width}" height="{height}" fill="{PAPER}"/>
  <g fill="{INK}" opacity=".14">{grain(width, height)}</g>
  <rect x="{x}" y="{y}" width="{badge}" height="{badge}" rx="{badge * .14:g}" fill="{INK}"/>
  <text x="{x + badge / 2:g}" y="{middle:g}" dy=".36em" text-anchor="middle" fill="{LIME}" font-family="monospace" font-size="{badge * .56:g}" font-weight="700">&gt;_</text>
  <text x="{x + badge + s["gap"]}" y="{middle:g}" dy=".36em" fill="{INK}" font-family="Arial, Helvetica, sans-serif" font-size="{s["size"]}" font-weight="700">{html.escape(title)}</text>
</svg>
'''


def render_status(mobile):
    """The availability line above the hero; the hero's own top paper fades in under it so they join."""
    s = LAYOUT[mobile]
    width, x = s["width"], s["gutter"]
    height = 66 if mobile else 64
    edge_height = 48 * width / 1440  # the strip at the hero's display scale
    edge = b64encode((HERE / "art" / "hero-top-edge.png").read_bytes()).decode("ascii")
    title, detail = html.escape(STATUS), html.escape(STATUS_DETAIL)
    if mobile:
        text = (
            f'<text x="{x}" y="26" dy=".36em" font-size="16" font-weight="700">{title}</text>'
            f'<text x="{x}" y="50" dy=".36em" font-size="13">{html.escape(STATUS_DETAIL_MOBILE)}</text>'
        )
    else:
        text = (
            f'<text x="{x}" y="32" dy=".36em" font-size="19" font-weight="700">{title}</text>'
            f'<text x="{width - x}" y="32" dy=".36em" text-anchor="end" font-size="15">{detail}</text>'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}. {detail}.">
  <defs>
    <linearGradient id="fade" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff"/></linearGradient>
    <mask id="edge"><rect y="{height - edge_height:g}" width="{width}" height="{edge_height:g}" fill="url(#fade)"/></mask>
  </defs>
  <rect width="{width}" height="{height}" fill="{PAPER}"/>
  <image y="{height - edge_height:g}" width="{width}" height="{edge_height:g}" preserveAspectRatio="none" mask="url(#edge)" href="data:image/png;base64,{edge}"/>
  <g fill="{INK}" opacity=".14">{grain(width, height)}</g>
  <g fill="{INK}" font-family="Arial, Helvetica, sans-serif">{text}</g>
</svg>
'''


def main():
    out = ROOT / "profile-assets" / "titles"
    out.mkdir(parents=True, exist_ok=True)
    (out / "status.svg").write_text(render_status(False), encoding="utf-8")
    (out / "status-mobile.svg").write_text(render_status(True), encoding="utf-8")
    for slug, (title, *bottoms) in TITLES.items():
        for mobile, bottom in zip((False, True), bottoms):
            suffix = "-mobile" if mobile else ""
            (out / f"{slug}{suffix}.svg").write_text(render(title, bottom, mobile), encoding="utf-8")


if __name__ == "__main__":
    main()
