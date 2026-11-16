"""Refresh the clickable GPU panels and their public merged-PR histories."""

import argparse
import html
import os
from pathlib import Path

from fetch import USER, graphql, load, save, warn
from gpu import panel_width_percent, render_gpu

ROOT = Path(__file__).resolve().parents[2]
DATASET = "upstream.json"
GPU_ROW = '<div id="open-source-contributions">\n'
ROW_END = "\n</div>"
REPOS = (
    ("OWASP/cve-lite-cli", "OWASP", "OWASP CVE Lite CLI",
     "I worked on scanner correctness, dependency version matching, and the commands developers use to fix findings."),
    ("sugarlabs/musicblocks-v4", "Sugar Labs", "Sugar Labs Music Blocks",
     "I worked on editing the visual workspace, including block duplication, selection, and drag behavior."),
    ("AWS-env/environmental-hacks", "EcoAudit", "EcoAudit",
     "I wrote detectors for avoidable compute waste and built the AWS API that runs repository scans."),
)
SLUGS = ("owasp", "sugar-labs", "ecoaudit")
QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    pullRequests(first: 100, after: $cursor, states: MERGED) {
      pageInfo { endCursor hasNextPage }
      nodes {
        number title url mergedAt
        repository { nameWithOwner isPrivate }
      }
    }
  }
}
"""


def fetch_history(token):
    repo_by_name = {repo.casefold(): repo for repo, *_ in REPOS}
    matches = {repo: {} for repo in repo_by_name.values()}
    cursor = None
    while True:
        data = graphql(token, QUERY, {"login": USER, "cursor": cursor})
        page = data["user"]["pullRequests"]
        for pr in page["nodes"]:
            repository = pr["repository"]
            name = repo_by_name.get(repository["nameWithOwner"].casefold())
            if name and not repository["isPrivate"] and pr["mergedAt"]:
                matches[name][pr["number"]] = {key: pr[key] for key in ("number", "title", "url", "mergedAt")}
        if not page["pageInfo"]["hasNextPage"]:
            break
        next_cursor = page["pageInfo"]["endCursor"]
        if not next_cursor or next_cursor == cursor:
            raise ValueError("GitHub did not advance the pull request cursor")
        cursor = next_cursor
    return {
        repo: sorted(prs.values(), key=lambda item: (item["mergedAt"], item["number"]), reverse=True)
        for repo, prs in matches.items()
    }


def render_history(repo, title, summary, entries):
    count = len(entries)
    unit = "PR" if count == 1 else "PRs"
    rows = [
        f'- <a href="{html.escape(pr["url"])}">#{pr["number"]} {html.escape(pr["title"])}</a> · {pr["mergedAt"][:10]}'
        for pr in entries
    ]
    if not rows:
        rows = ["No public merged pull requests yet."]
    return "\n".join([
        f"# {title}", "", summary, "",
        f"[Upstream repository](https://github.com/{repo}) · [Back to profile](../README.md#open-source-contributions)",
        "", f"## {count:,} merged {unit}", "", *rows, "",
    ])


def write_assets(history):
    readme = ROOT / "README.md"
    old = readme.read_text(encoding="utf-8")
    intro, start, panel = old.partition(GPU_ROW)
    previous, end, rest = panel.partition(ROW_END)
    if not start or not end or GPU_ROW in rest or not previous.strip().startswith('<a href="open-source/'):
        raise ValueError("README must contain one GPU row with links to the contribution histories")
    assets = ROOT / "profile-assets" / "open-source"
    histories = ROOT / "open-source"
    assets.mkdir(parents=True, exist_ok=True)
    histories.mkdir(parents=True, exist_ok=True)
    labels = [
        (short_name, len(history[repo]), history[repo][0]["number"] if history[repo] else None)
        for repo, short_name, *_ in REPOS
    ]
    links = []
    for index, (slug, (repo, _, title, summary)) in enumerate(zip(SLUGS, REPOS, strict=True)):
        (assets / f"{slug}.svg").write_text(render_gpu(labels[index], index), encoding="utf-8")
        (histories / f"{slug}.md").write_text(render_history(repo, title, summary, history[repo]), encoding="utf-8")
        count = len(history[repo])
        unit = "PR" if count == 1 else "PRs"
        latest = f' Latest merge: #{history[repo][0]["number"]}.' if count else ""
        alt = html.escape(f"{title}: {count:,} merged {unit}.{latest} Open the full contribution history.")
        links.append(
            f'<a href="open-source/{slug}.md"><img src="profile-assets/open-source/{slug}.svg" '
            f'width="{panel_width_percent(index):.8f}%" align="top" alt="{alt}"></a>'
        )
    updated = intro + GPU_ROW + "  " + "".join(links) + ROW_END + rest
    readme.write_text(updated, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="refresh the cached history before rendering")
    args = parser.parse_args()
    history = load(DATASET, None)
    if args.fetch:
        token = os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN")
        try:
            if not token:
                raise ValueError("GitHub token is missing")
            history = fetch_history(token)
            save(DATASET, history)
        except Exception as error:
            if history is None:
                raise
            warn(f"Upstream history refresh failed, keeping the last complete snapshot: {error}")
    if history is None:
        raise ValueError("No cached upstream history. Run with --fetch first.")
    write_assets(history)


if __name__ == "__main__":
    main()
