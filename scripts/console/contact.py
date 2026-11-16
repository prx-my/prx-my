"""Rebuild the contact RAM strip: five modules, stretched to a chosen height.

The RAM art is drawn at 142 units tall and stretched vertically; the labels and arrows are
counter-scaled so only the stick grows. The source is each module's SVG as of the
commit below, so this can be re-run with a different stretch without compounding it.
"""

import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "profile-assets" / "contact"
SOURCE = "1504da6"  # last commit with the original four-module art
OLD_STRETCH = 1.29
BOTTOM_PAD = 46  # paper under the pins
TEXT = '<g fill="#12249e" font-family="Arial, Helvetica, sans-serif" transform="scale(1 .7751938)">'
ARROW = re.compile(r'(<path d="M270 79l16-16m-12 0h12v12"[^>]*/>)', re.S)
# Order across the stick, and the RGB light-bar offset each module needs to stay continuous.
MODULES = ("portfolio", "resume", "x", "linkedin", "email")


def source(name):
    return subprocess.run(["git", "show", f"{SOURCE}:profile-assets/contact/{name}.svg"],
                          cwd=ROOT, check=True, capture_output=True, text=True).stdout


def resume_from_x(svg):
    svg = svg.replace("<title>X · @_prxmy</title>", "<title>Resume · prxmy.in/resume</title>")
    svg = svg.replace('<path d="M0 103H336V130H324L319 139H0Z"/>', '<path d="M0 103H336V139H0Z"/>')  # key notch stays between X and LinkedIn
    svg = svg.replace('font-weight="700">X</text>', 'font-weight="700">Resume</text>')
    return svg.replace(">@_prxmy</text>", ">prxmy.in/resume</text>")


def render(name, stretch):
    svg = source("x" if name == "resume" else name)
    if name == "resume":
        svg = resume_from_x(svg)
    index = MODULES.index(name)
    if 0 < index < len(MODULES) - 1:
        svg = re.sub(r'<g transform="translate\(-\d+ 0\)">', f'<g transform="translate({-336 * index} 0)">', svg)
    shift = 81 * (stretch - OLD_STRETCH)  # keep labels centred on the taller face
    lift = shift / stretch
    width = int(re.search(r'<svg[^>]* width="(\d+)"', svg)[1])
    height = round(139 * stretch + BOTTOM_PAD)
    svg = re.sub(r'(<svg[^>]* )height="\d+" viewBox="0 0 (\d+) \d+"', rf'\1height="{height}" viewBox="0 0 \2 {height}"', svg, count=1)
    svg = re.sub(r'<rect width="(\d+)" height="\d+" fill="#f9e6cc"/>', rf'<rect width="\1" height="{height}" fill="#f9e6cc"/>', svg, count=1)
    rng = random.Random(f"contact-{name}")
    dots = "".join(f'<circle cx="{rng.randrange(60)}" cy="{rng.randrange(60)}" r="{rng.choice((.35, .5, .75))}"/>' for _ in range(14))
    grain = (f'<pattern id="paper-grain" width="60" height="60" patternUnits="userSpaceOnUse">'
             f'<g fill="#12249e" opacity=".14">{dots}</g></pattern><rect width="{width}" height="{height}" fill="url(#paper-grain)"/>')
    svg = re.sub(r'<g fill="#12249e" opacity="\.14">.*?</g>', grain, svg, count=1, flags=re.S)
    # Phones show each module under ~90px wide: keep the light bar still there, and tile the grain
    # as a pattern so desktop frames don't redraw hundreds of separate dots.
    svg = svg.replace("@media (prefers-reduced-motion: no-preference) {", "@media (prefers-reduced-motion: no-preference) and (min-width: 120px) {")
    svg = svg.replace(f"scale(1 {OLD_STRETCH})", f"scale(1 {stretch:g})")
    assert svg.count(TEXT) == 1, name
    svg = svg.replace(TEXT, TEXT.replace('transform="scale(1 .7751938)"', f'transform="translate(0 {lift:.4f}) scale(1 {1 / stretch:.6f})"'))
    svg, arrows = ARROW.subn(rf'<g transform="translate(0 {lift:.4f}) scale(1 {OLD_STRETCH / stretch:.6f})">\1</g>', svg)
    assert arrows == 1, name
    return svg


def main():
    stretch = float(sys.argv[1]) if len(sys.argv) > 1 else 1.9
    for name in MODULES:
        (OUT / f"{name}.svg").write_text(render(name, stretch), encoding="utf-8")


if __name__ == "__main__":
    main()
