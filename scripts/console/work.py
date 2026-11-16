"""Render the Selected work rack from the editable projects.md file."""

import html
import random
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INK = "#12249e"
DARK = "#0d1a6b"
PAPER = "#f9e9cb"
CARD = "#f9e6cc"  # the profile's shared paper, matched to the hero print
CABINET = "#0b1240"
LIME = "#d2ed45"
LED_COLORS = ("#ff6658", "#74df70", "#76a6ff", "#ffdc55")
PATCH_COLORS = ("#9ab7ff", "#eabd70", "#aabafa", "#d7e477")
ACTIVITY_PERIODS = (1.15, 1.85, 1.30, 2.25, 1.55)
HEARTBEAT_PERIODS = (4.8, 3.9, 5.4, 4.3, 5.1)
ACTIONS = {"owasp": "Read PR #1202", "jansamadhan": "Watch demo"}
HEADING = re.compile(r"## (.+?)\s*<!-- ([a-z0-9-]+) -->")


@dataclass
class Project:
    slug: str
    name: str
    summary: str = ""
    bullets: list[str] = field(default_factory=list)


def load_projects(path):
    projects = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        heading = HEADING.fullmatch(line)
        if heading:
            name, slug = heading.groups()
            projects.append(Project(slug, name))
        elif not line or line.startswith(("# ", "<!--")):
            continue
        elif projects and line.startswith("- ") and projects[-1].summary:
            projects[-1].bullets.append(line[2:].strip())
        elif projects and not projects[-1].summary and not line.startswith(("#", "-")):
            projects[-1].summary = line
        else:
            raise ValueError(f"{path}:{line_number}: expected a project heading, one-line summary, or '- ' bullet")

    if not projects or any(not project.summary for project in projects):
        raise ValueError(f"{path}: every project needs a one-line summary")
    if len({project.slug for project in projects}) != len(projects):
        raise ValueError(f"{path}: project IDs must be unique")
    return projects


def grain():
    rng = random.Random(191)
    return "".join(
        f'<circle cx="{rng.randrange(93)}" cy="{rng.randrange(61)}" r="{rng.choice((.45,.65,.85))}"/>'
        for _ in range(125)
    )


def bullet_led(slug, bullet):
    # A stable color lets repeated workflow runs produce identical files.
    return random.Random(f"{slug}\0{bullet}").choice(LED_COLORS)


def bullet_rows(project, mobile):
    x = 93
    y = 97 if mobile else 99
    rows = []
    for bullet in project.bullets:
        color = bullet_led(project.slug, bullet)
        rows.append(
            f'<circle cx="78" cy="{y-6}" r="4.2" fill="{color}" stroke="{DARK}" stroke-width="1"/>'
            f'<circle cx="77" cy="{y-7}" r="1.05" fill="white" opacity=".6"/>'
        )
        for line in textwrap.wrap(bullet, width=29 if mobile else 53):
            rows.append(f'<text x="{x}" y="{y}" font-size="{16 if mobile else 17}">{html.escape(line)}</text>')
            y += 20
    return "\n      ".join(rows), y - (97 if mobile else 99)


def patch_cables(index, total, height, mobile):
    plug, trunk = (386, 427) if mobile else (592, 611)
    paths, ports, highlights = [], [], []
    for incoming, neighbor in ((True, index - 1), (False, index)):
        if not 0 <= neighbor < total - 1:
            continue
        for wire in range(2):
            color = PATCH_COLORS[(neighbor + wire) % len(PATCH_COLORS)]
            x = trunk + wire * 7
            y = (36 if incoming else 61) + wire * 9
            if incoming:
                route = f"M{x} 0V14Q{x} {y} {plug} {y}"
            else:
                route = f"M{plug} {y}Q{x} {y} {x} {y+22}V{height}"
            paths.append(
                f'<path d="{route}" stroke="{DARK}" stroke-width="5.4"/>'
                f'<path d="{route}" stroke="{color}" stroke-width="2.8"/>'
            )
            ports.append(
                f'<rect x="{plug-22}" y="{y-3.6:g}" width="17" height="7.2" rx="1.2" fill="#09154c" stroke="#8094df" stroke-width=".8"/>'
                f'<rect x="{plug-12}" y="{y-2.6:g}" width="12" height="5.2" rx=".8" fill="{color}"/>'
                f'<path d="M{plug-8} {y-2}v4m3-4v4" stroke="{DARK}" stroke-opacity=".55" stroke-width=".7"/>'
            )
            if wire == 0:
                delay = neighbor * 2.1 + (.82 if incoming else 0)
                highlights.append(
                    f'<path class="packet" style="--delay:{delay:.2f}s" d="{route}" pathLength="100" '
                    'stroke="#fff1b8" stroke-width="3.3" stroke-linecap="round" '
                    'stroke-dasharray="12 170" stroke-dashoffset="14" opacity="0"/>'
                )
                if incoming:
                    highlights.append(
                        f'<rect class="port-glow" style="--delay:{delay+.65:.2f}s" '
                        f'x="{plug-22}" y="{y-3.6:g}" width="17" height="7.2" rx="1.2" '
                        'fill="#f6be72" opacity="0"/>'
                    )
    return "\n    ".join(paths + ports + highlights)


def render(project, index, total, mobile):
    bullets, extra_height = bullet_rows(project, mobile)
    width = 460 if mobile else 820
    # The rack sits inside the shared paper with the same 12px/20px gutter as every other slice.
    margin = 17 if mobile else 21
    outer = width + 2 * margin
    foot = (17 if mobile else 19) if index == total - 1 else 0  # paper under the rack before the next section
    height = (132 if mobile else 110) + extra_height
    label_right = 358 if mobile else 562
    label_bottom = height - (42 if mobile else 15)
    label = f"M62 19H{label_right-10}L{label_right} 29V{label_bottom}H62Z"
    action_x, action_y = (402, height - 20) if mobile else (768, 60)
    action = ACTIONS.get(project.slug, "View source")
    summary_sizing = f' textLength="{label_right-86}" lengthAdjust="spacingAndGlyphs"' if len(project.summary) > 33 and mobile else ""
    rails = f"M1 0V{height}M{width-1} 0V{height}"
    if index == 0:
        rails += f"M1 1H{width-1}"
    if index == total - 1:
        rails += f"M1 {height-1}H{width-1}"
    screws = "".join(
        f'<circle cx="{x}" cy="{y}" r="5.5"/><path d="M{x-2.8:g} {y+2.8:g}l5.6-5.6" stroke="{DARK}" stroke-width="1.5"/>'
        for x in (15, width - 15) for y in (24, height - 24)
    )
    slots = "".join(f'<rect x="35" y="{y}" width="14" height="5" rx="2.5"/>' for y in range(31, 78, 10))
    activity_period = ACTIVITY_PERIODS[index % len(ACTIVITY_PERIODS)]
    heartbeat_period = HEARTBEAT_PERIODS[index % len(HEARTBEAT_PERIODS)]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{outer}" height="{height + foot}" viewBox="0 0 {outer} {height + foot}" role="img" aria-labelledby="title detail">
  <title id="title">{html.escape(project.name)}</title>
  <desc id="detail">{html.escape(". ".join([project.summary.rstrip("."), *[bullet.rstrip(".") for bullet in project.bullets], action]))}.</desc>
  <style>
    @media (prefers-reduced-motion: no-preference) {{
      .activity {{ animation: activity-blip {activity_period:g}s ease-in-out {-index * .27:.2f}s infinite; }}
      .heartbeat {{ animation: heartbeat {heartbeat_period:g}s ease-in-out {-index * .68:.2f}s infinite; }}
      .packet {{ animation: packet-travel 12s linear var(--delay) infinite; }}
      .port-glow {{ animation: port-arrival 12s ease-out var(--delay) infinite; }}
    }}
    @keyframes activity-blip {{ 0%, 21%, 100% {{ opacity: .42; }} 7% {{ opacity: 1; }} }}
    @keyframes heartbeat {{ 0%, 100% {{ opacity: .38; }} 45% {{ opacity: .9; }} }}
    @keyframes packet-travel {{
      0% {{ opacity: 0; stroke-dashoffset: 14; }}
      .3% {{ opacity: 1; }}
      7% {{ opacity: 1; stroke-dashoffset: -102; }}
      7.3%, 100% {{ opacity: 0; stroke-dashoffset: -102; }}
    }}
    @keyframes port-arrival {{
      0%, 5%, 100% {{ opacity: 0; }}
      1.2% {{ opacity: .88; }}
    }}
  </style>
  <defs>
    <pattern id="grain" width="93" height="61" patternUnits="userSpaceOnUse"><g fill="{INK}" opacity=".22">{grain()}</g></pattern>
    <clipPath id="chassis"><rect x="7" y="4" width="{width-14}" height="{height-8}" rx="5"/></clipPath>
  </defs>
  <rect width="{outer}" height="{height + foot}" fill="{CARD}"/>
  <rect width="{outer}" height="{height + foot}" fill="url(#grain)" opacity=".6"/>
  <rect x="{margin}" width="{width}" height="{height}" fill="{CABINET}"/>
  <g transform="translate({margin} 0)">
  <g clip-path="url(#chassis)">
    <rect width="{width}" height="{height}" fill="{DARK}"/>
    <rect x="24" y="7" width="{width-48}" height="{height-14}" rx="5" fill="{INK}"/>
    <rect width="{width}" height="{height}" fill="url(#grain)"/>
    <path d="M25 13H{width-25}M25 {height-13}H{width-25}" stroke="#7083d1" stroke-opacity=".65"/>
    <g fill="#f4dfb6">{screws}</g>
    <g fill="{DARK}" stroke="#7a8ad9" stroke-opacity=".4">{slots}</g>
    <g aria-hidden="true">
      <rect x="30" y="82" width="26" height="10" rx="4" fill="#0b1659" stroke="#7184d3" stroke-opacity=".46"/>
      <circle cx="35" cy="87" r="2.55" fill="{LIME}"/>
      <circle class="activity" cx="43" cy="87" r="2.55" fill="#f6be72" opacity=".72"/>
      <circle class="heartbeat" cx="51" cy="87" r="2.55" fill="#e67569" opacity=".68"/>
    </g>
    <path d="{label}" fill="{PAPER}"/>
    <path d="{label}" fill="url(#grain)"/>
    <g fill="{INK}" font-family="Arial, Helvetica, sans-serif">
      <text x="75" y="46" font-size="{27 if mobile else 30}" font-weight="700">{html.escape(project.name)}</text>
      <text x="75" y="72" font-size="{18 if mobile else 19}"{summary_sizing}>{html.escape(project.summary)}</text>
      {bullets}
    </g>
    <text x="{action_x-12}" y="{action_y}" text-anchor="end" font-family="Arial, Helvetica, sans-serif"
      font-size="{19 if mobile else 17}" font-weight="700" fill="{PAPER}">{action}</text>
    <path d="M{action_x} {action_y-1}l14-14m-10 0h10v10" fill="none" stroke="{LIME}" stroke-width="2.4"
      stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <path d="{rails}" fill="none" stroke="#7083d1" stroke-width="2"/>
  <g aria-hidden="true" fill="none" stroke-linejoin="round">
    {patch_cables(index, total, height, mobile)}
  </g>
  </g>
</svg>
'''


def main():
    projects = load_projects(ROOT / "projects.md")
    out = ROOT / "profile-assets" / "work"
    out.mkdir(parents=True, exist_ok=True)
    for index, project in enumerate(projects):
        for mobile in (False, True):
            suffix = "-mobile" if mobile else ""
            (out / f"{project.slug}{suffix}.svg").write_text(
                render(project, index, len(projects), mobile), encoding="utf-8"
            )


if __name__ == "__main__":
    main()
