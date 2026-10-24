"""Writes README.md as the console's image stack, with alt text carrying the data.

Every slice has a light-theme variant in assets/light/, swapped in with
<picture>. Adapted from Giorgi Kobaidze's readme.py (MIT; see LICENSE and NOTICE).
"""

import datetime
import html
import json
import pathlib

from render import LINKS, OWASP_MERGED, PROJECTS, QUOTE, SUGAR_MERGED

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE / "data"
README = ROOT / "README.md"
RAW = "https://github.com/prx-my/prx-my/raw/main/assets"


def esc(value):
    return html.escape(str(value), quote=True)


def pic(rel, width, alt, href=None):
    image = (
        f'<picture><source media="(prefers-color-scheme: light)" srcset="{RAW}/light/{rel}">'
        f'<img src="./assets/{rel}" width="{width}" align="top" alt="{esc(alt)}"></picture>'
    )
    return f'<a href="{esc(href)}">{image}</a>' if href else image


def stats_alt(data):
    since = datetime.date.fromisoformat(data["created_at"][:10])
    languages = sorted(data["languages"].items(), key=lambda item: -item[1])[:5]
    parts = [
        f'{data["contributions_year"]:,} contributions in {data["year"]}, {data["contributions_all"]:,} all time',
        f'{data["prs"]:,} pull requests ({data["prs_merged"]:,} merged)',
        f'{data.get("upstream_merged", 0)} merged upstream in OWASP and Sugar Labs',
        f'current streak {data["streak_current"]} days, longest {data["streak_longest"]} days',
        f'{data["followers"]:,} followers',
        f'{data.get("public_repos", data.get("repo_count", 0))} public repos',
        f'member since {since:%B %Y}',
        f'{data["hackathon_wins"]} hackathon wins',
    ]
    return (
        "Stats: " + "; ".join(parts) + ". Top languages: "
        + ", ".join(name for name, _ in languages) + "."
    )


def city_alt(calendar):
    total = sum(count for _, count in calendar)
    busiest = max(calendar, key=lambda item: item[1]) if calendar else None
    text = (
        "Contribution city: an isometric skyline with one building per day of the last year. "
        f"{total:,} contributions"
    )
    if busiest and busiest[1]:
        day = datetime.date.fromisoformat(busiest[0])
        text += f", busiest day {day:%B} {day.day} with {busiest[1]}"
    return text + "."


def stack_alt():
    from render import STACK

    return "Tech stack. " + " ".join(
        f"{category}: {', '.join(items)}." for category, items in STACK
    )


def milestones_alt(data):
    since = datetime.date.fromisoformat(data["created_at"][:10])
    first = (
        datetime.date.fromisoformat(data["first_merged"])
        if data.get("first_merged")
        else None
    )
    rows = [
        f"joined GitHub {since:%B %Y}",
        f"first upstream merge {first:%B %Y}" if first else "first upstream merge",
        "3 hackathon wins",
        f'{data.get("upstream_merged", 0)} merged upstream',
    ]
    return "Milestones. " + "; ".join(rows) + "."


def main():
    stats = json.loads((DATA / "stats.json").read_text())
    calendar = json.loads((DATA / "calendar.json").read_text())
    merged = json.loads((DATA / "merged.json").read_text())

    rows = []
    rows.append(
        pic(
            "header.svg",
            "100%",
            "Prakhar Gupta — backend and security tooling in TypeScript and Python. Open to software engineering internships, any term. 13 merged pull requests in OWASP cve-lite-cli.",
        )
    )
    rows.append(pic("links.svg", "100%", "Links"))
    buttons = []
    for key, label, handle, url in LINKS:
        buttons.append(pic(f"links/{key}.svg", "25%", f"{label}: {handle}", url))
    rows.append("".join(buttons))
    rows.append(pic("stats.svg", "100%", stats_alt(stats)))
    rows.append(pic("contribution-city.svg", "100%", city_alt(calendar)))
    rows.append(pic("projects.svg", "100%", "Projects"))
    cards = []
    for project in PROJECTS:
        alt = (
            f'{project["name"]} — {project["tag"]}. {project["desc"]} '
            f'Built with {project["stack"].replace(" · ", ", ")}. {project["stat"]}.'
        )
        cards.append(pic(f'card-{project["slug"]}.svg', "50%", alt, project["url"]))
    rows.append("".join(cards))
    rows.append(
        pic(
            "quote.svg",
            "100%",
            f'On {QUOTE["on"]}: "{QUOTE["text"]}" — {QUOTE["who"]}, {QUOTE["role"]}.',
            QUOTE["url"],
        )
    )
    rows.append(pic("merged.svg", "100%", "Merged upstream"))
    for index, pr in enumerate(merged[:5], 1):
        repo = "OWASP" if pr["owner"] == "OWASP" else "Sugar Labs"
        alt = f'{repo} #{pr["number"]}: {pr["title"]}. Merged {pr["date"]}.'
        rows.append(pic(f"merged/{index}.svg", "100%", alt, pr["url"]))
    rows.append(
        pic("merged/owasp.svg", "50%", "All OWASP merged pull requests", OWASP_MERGED)
        + pic("merged/sugar.svg", "50%", "All Sugar Labs merged pull requests", SUGAR_MERGED)
    )
    rows.append(pic("milestones.svg", "100%", milestones_alt(stats)))
    rows.append(pic("stack.svg", "100%", stack_alt()))
    rows.append(pic("footer.svg", "100%", "Connection closed."))

    readme = (
        "<!-- Generated by `python scripts/console/fetch.py && python scripts/console/render.py && python scripts/console/readme.py`. -->\n"
        '<p align="center">\n'
        + "\n".join(rows)
        + "\n</p>\n"
    )
    README.write_text(readme)
    print("README.md updated")


if __name__ == "__main__":
    main()
