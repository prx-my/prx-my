"""Embed the approved GPU artwork and animate its three rotors in place."""

from base64 import b64encode
from dataclasses import dataclass
from html import escape
from pathlib import Path

ART = Path(__file__).resolve().parent / "art"
HEIGHT = 724
CARD = "#f9e6cc"
# The artwork was printed on lighter stock (#fdf2db); multiplying moves it onto the profile's shared paper.
PAPER_TINT = "0.9842 0 0 0 0  0 0.9504 0 0 0  0 0 0.9315 0 0  0 0 0 1 0"
FRAME = 8  # the artwork's own border, painted out so the GPU row joins the paper above and below


@dataclass(frozen=True)
class Panel:
    slug: str
    width: int
    center: int
    rotor_radius: int
    printed_count: int
    printed_pr: int
    pr_left: int
    pr_width: int


PANELS = (
    Panel("owasp", 825, 559, 157, 27, 1636, 549, 92),
    Panel("sugar-labs", 565, 281, 157, 5, 942, 279, 72),
    Panel("ecoaudit", 782, 266, 157, 99, 563, 263, 77),
)

TOTAL_WIDTH = sum(panel.width for panel in PANELS)


def panel_width_percent(index):
    return 100 * PANELS[index].width / TOTAL_WIDTH


def updated_count(panel, count):
    if count == panel.printed_count:
        return ""
    value = f"{count:,}"
    size = min(64, 130 / len(value))
    return f"""<g clip-path="url(#hub-interior)">
    <circle cx="{panel.center}" cy="339" r="45" fill="#fff2d1"/>
    <text x="{panel.center}" y="339" dy=".35em" text-anchor="middle"
      fill="#11299e" font-size="{size:g}">{value}</text>
  </g>"""


def updated_pr(panel, latest):
    if latest == panel.printed_pr:
        return ""
    value = f"#{latest}" if latest is not None else "—"
    size = min(30, panel.pr_width / (.58 * len(value)))
    return f"""<g clip-path="url(#pr-number)"><use href="#art" x="-150"/></g>
  <text x="{panel.pr_left+2}" y="583" fill="#fff2d1" font-size="{size:g}">{value}</text>"""


def render_gpu(repo, index):
    name, count, latest = repo
    panel = PANELS[index]
    artwork = b64encode((ART / f"gpu-{panel.slug}.webp").read_bytes()).decode("ascii")
    direction = "reverse" if index == 1 else "normal"
    frame = f"M0 0H{panel.width}V{FRAME}H0ZM0 {HEIGHT - FRAME}H{panel.width}V{HEIGHT}H0Z"
    if index == 0:
        frame += f"M0 0H{FRAME}V{HEIGHT}H0Z"
    if index == len(PANELS) - 1:
        frame += f"M{panel.width - FRAME} 0H{panel.width}V{HEIGHT}H{panel.width - FRAME}Z"
    period = 12 if index == 1 else 8
    changes = "\n  ".join(filter(None, (updated_count(panel, count), updated_pr(panel, latest))))
    overlay = f'  <g font-family="Arial, Helvetica, sans-serif" font-weight="700">\n  {changes}\n  </g>\n' if changes else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{panel.width}" height="{HEIGHT}"
    viewBox="0 0 {panel.width} {HEIGHT}" role="img" aria-labelledby="title description">
  <title id="title">{escape(name)} GPU fan</title>
  <desc id="description">{count:,} merged pull requests.</desc>
  <style>
    .animated-fan {{ display: none; }}
    @media (prefers-reduced-motion: no-preference) {{
      .animated-fan {{ display: inline; }}
      .rotor {{ transform-origin: 0 0; animation: gpu-rotate {period}s linear infinite {direction}; }}
    }}
    @keyframes gpu-rotate {{ to {{ transform: rotate(360deg); }} }}
  </style>
  <defs>
    <filter id="paper-tint" x="0" y="0" width="1" height="1" color-interpolation-filters="sRGB">
      <feColorMatrix type="matrix" values="{PAPER_TINT}"/>
    </filter>
    <image id="art" width="{panel.width}" height="{HEIGHT}" filter="url(#paper-tint)" href="data:image/webp;base64,{artwork}"/>
    <clipPath id="rotor-opening"><circle cx="{panel.center}" cy="339" r="{panel.rotor_radius}"/></clipPath>
    <clipPath id="hub"><circle cx="{panel.center}" cy="339" r="54"/></clipPath>
    <clipPath id="hub-interior"><circle cx="{panel.center}" cy="339" r="45"/></clipPath>
    <clipPath id="pr-number"><rect x="{panel.pr_left}" y="554" width="{panel.pr_width}" height="33"/></clipPath>
  </defs>
  <use href="#art"/>
  <g class="animated-fan">
    <g clip-path="url(#rotor-opening)">
      <g transform="translate({panel.center} 339)">
        <g class="rotor"><use href="#art" transform="translate(-{panel.center} -339)"/></g>
      </g>
    </g>
    <g clip-path="url(#hub)"><use href="#art"/></g>
  </g>
  <path d="{frame}" fill="{CARD}"/>
{overlay}</svg>
"""
