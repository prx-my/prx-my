"""Fetches profile data into data/stats.json, data/calendar.json and data/merged.json.

Environment:
  GITHUB_TOKEN   token for the GitHub API (the Actions token is fine).

Every source is fetched independently; a failure keeps the previous file so a
flaky API never blanks the profile.

Adapted from Giorgi Kobaidze's profile generator (MIT; see LICENSE and NOTICE).
"""

import datetime
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

USER = "prx-my"
HACKATHON_WINS = 3
REPOS = ["OWASP/cve-lite-cli", "sugarlabs/musicblocks-v4"]
DATA = pathlib.Path(__file__).resolve().parent / "data"
UA = "prx-my-profile-updater"


def http_json(url, *, headers=None, body=None, timeout=30):
    req = urllib.request.Request(
        url,
        data=None if body is None else json.dumps(body).encode(),
        headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})},
    )
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def graphql(token, query, variables=None):
    result = http_json(
        "https://api.github.com/graphql",
        headers={"Authorization": f"bearer {token}"},
        body={"query": query, "variables": variables or {}},
    )
    if result.get("errors"):
        raise RuntimeError(
            "GraphQL error: " + "; ".join(e.get("message", "?") for e in result["errors"])
        )
    return result["data"]


def load(name, default):
    try:
        return json.loads((DATA / name).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(name, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(
        json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    )


def warn(message):
    print(
        f"::warning::{message}" if os.environ.get("GITHUB_ACTIONS") else f"warning: {message}",
        file=sys.stderr,
    )


PROFILE_QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    allRepos: repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
    followers { totalCount }
    pullRequests { totalCount }
    merged: pullRequests(states: MERGED) { totalCount }
    contributionsCollection { contributionYears }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      nodes {
        name
        stargazerCount
        forkCount
        languages(first: 20) { edges { size node { name } } }
      }
    }
  }
}"""


def years_query(years):
    parts = []
    for year in years:
        parts.append(
            f"""
    y{year}: contributionsCollection(from: "{year}-01-01T00:00:00Z", to: "{year}-12-31T23:59:59Z") {{
      totalCommitContributions
      contributionCalendar {{ totalContributions weeks {{ contributionDays {{ date contributionCount }} }} }}
    }}"""
        )
    return 'query($login: String!) {\n  user(login: $login) {' + "".join(parts) + "\n  }\n}"


def streaks(days, today):
    dates = sorted(day for day in days if day <= today)
    longest = run = 0
    for day in dates:
        run = run + 1 if days[day] > 0 else 0
        longest = max(longest, run)
    current, day = 0, today
    if days.get(day, 0) == 0:
        day -= datetime.timedelta(days=1)
    while days.get(day, 0) > 0:
        current += 1
        day -= datetime.timedelta(days=1)
    return current, longest


def fetch_github(token, today):
    user = graphql(token, PROFILE_QUERY, {"login": USER})["user"]
    years = sorted(user["contributionsCollection"]["contributionYears"])
    year_data = (
        graphql(token, years_query(years), {"login": USER})["user"] if years else {}
    )

    days, commits_all, contributions_all = {}, 0, 0
    for year in years:
        block = year_data[f"y{year}"]
        commits_all += block["totalCommitContributions"]
        contributions_all += block["contributionCalendar"]["totalContributions"]
        for week in block["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                days[datetime.date.fromisoformat(day["date"])] = day["contributionCount"]

    current, longest = streaks(days, today)
    start = today - datetime.timedelta(weeks=52)
    start -= datetime.timedelta(days=(start.weekday() + 1) % 7)
    calendar = [
        [day.isoformat(), days.get(day, 0)]
        for day in (
            start + datetime.timedelta(days=i)
            for i in range((today - start).days + 1)
        )
    ]

    repos = user["repositories"]["nodes"]
    languages = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            languages[edge["node"]["name"]] = (
                languages.get(edge["node"]["name"], 0) + edge["size"]
            )
    this_year = year_data.get(f"y{today.year}", {})
    return {
        "created_at": user["createdAt"],
        "public_repos": user["allRepos"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "prs": user["pullRequests"]["totalCount"],
        "prs_merged": user["merged"]["totalCount"],
        "stars": sum(repo["stargazerCount"] for repo in repos),
        "forks": sum(repo["forkCount"] for repo in repos),
        "repo_count": len(repos),
        "repo_stars": {repo["name"]: repo["stargazerCount"] for repo in repos},
        "languages": dict(sorted(languages.items(), key=lambda item: -item[1])),
        "year": today.year,
        "commits_year": this_year.get("totalCommitContributions", 0),
        "commits_all": commits_all,
        "contributions_year": this_year.get("contributionCalendar", {}).get(
            "totalContributions", 0
        ),
        "contributions_all": contributions_all,
        "streak_current": current,
        "streak_longest": longest,
        "_calendar": calendar,
    }


def clean_title(title):
    title = re.sub(r"^[a-z]+(?:\([^)]+\))?!?:\s*", "", title, flags=re.I)
    return re.sub(r"\s*\(#\d+\)\s*$", "", title).strip()


def fetch_merged(token):
    items = []
    total = 0
    for repo in REPOS:
        query = urllib.parse.quote(f"repo:{repo} is:pr is:merged author:{USER}")
        payload = http_json(
            f"https://api.github.com/search/issues?q={query}&per_page=20&sort=updated&order=desc",
            headers={"Authorization": f"bearer {token}"},
        )
        owner, name = repo.split("/")
        total += payload.get("total_count", 0)
        for item in payload.get("items", []):
            items.append(
                {
                    "number": item["number"],
                    "title": clean_title(item["title"]),
                    "date": (item.get("pull_request") or {}).get("merged_at", "")[:10],
                    "repo": name,
                    "owner": owner,
                    "url": item["html_url"],
                }
            )
    items = [item for item in items if item["date"]]
    items.sort(key=lambda item: item["date"], reverse=True)
    return items[:6], total


def main():
    today = datetime.datetime.now(datetime.timezone.utc).date()
    stats = load("stats.json", {})
    merged = load("merged.json", [])
    upstream = stats.get("upstream_merged", 0)
    ok = False

    token = os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        warn("No PROFILE_TOKEN or GITHUB_TOKEN set, skipping GitHub")
        sys.exit(1)

    try:
        github = fetch_github(token, today)
        save("calendar.json", github.pop("_calendar"))
        stats.update(github)
        ok = True
        print("github: ok")
    except Exception as error:  # noqa: BLE001 - keep previous data
        warn(f"GitHub fetch failed, keeping previous stats: {error}")

    try:
        merged, upstream = fetch_merged(token)
        print(f"merged: {len(merged)} pull requests, {upstream} upstream")
    except Exception as error:  # noqa: BLE001
        warn(f"Merged PR fetch failed, keeping previous list: {error}")

    if not ok:
        print("error: GitHub fetch failed", file=sys.stderr)
        sys.exit(1)

    stats["hackathon_wins"] = HACKATHON_WINS
    stats["upstream_merged"] = upstream
    stats["updated"] = today.isoformat()
    save("stats.json", stats)
    save("merged.json", merged)


if __name__ == "__main__":
    main()
