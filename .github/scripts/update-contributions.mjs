#!/usr/bin/env node
// Regenerates the "Open Source Contributions" section of README.md from the
// merged pull requests authored by GH_USER in each tracked repository.
//
// Run: GITHUB_TOKEN=... node .github/scripts/update-contributions.mjs
// The section is delimited by the CONTRIBUTIONS:START / CONTRIBUTIONS:END
// markers so the rest of the README stays untouched.

import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const USER = process.env.GH_USER || "prx-my";
const TOKEN = process.env.GITHUB_TOKEN || process.env.GH_TOKEN || "";

const README = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "README.md",
);

const START = "<!-- CONTRIBUTIONS:START -->";
const END = "<!-- CONTRIBUTIONS:END -->";

// Repos surfaced in the section, in display order.
const REPOS = [
  {
    owner: "sugarlabs",
    repo: "musicblocks-v4",
    heading: "Sugar Labs",
    badgeLabel: "Sugar_Labs",
    badgeColor: "FF7A00",
    subtitle:
      "Blocks-based music programming environment · TypeScript · React · Zustand",
  },
  {
    owner: "OWASP",
    repo: "cve-lite-cli",
    heading: "OWASP",
    badgeLabel: "OWASP",
    badgeColor: "00549E",
    subtitle:
      "Dependency CVE scanner &amp; override-hygiene CLI · TypeScript · Node.js",
  },
];

// Hand-written summaries that override the auto-derived ones. New PRs are
// derived from their title, so this map only needs entries where a nicer
// description or area is wanted. A value is either the change text, or an
// object with `change` and/or `area`. Keyed by "<owner>/<repo>#<number>".
const OVERRIDES = {
  "sugarlabs/musicblocks-v4#942":
    "Share the drag trailing-click suppression guard across three call sites",
  "sugarlabs/musicblocks-v4#919": "Clear and toggle brick selection on press",
  "sugarlabs/musicblocks-v4#871":
    "Separate drag and click selection so drags stop leaving bricks selected",
  "sugarlabs/musicblocks-v4#850":
    "Duplicate a brick and its subtree as an independent tower",
  "sugarlabs/musicblocks-v4#646": {
    change: "Correct tail step width bleed for `strokeWidth > 2`",
    area: "`fix` · `geometry`",
  },
  "OWASP/cve-lite-cli#1231":
    "Disclose compact-mode finding and command-group truncation",
  "OWASP/cve-lite-cli#1230": "Extract CLI flag literals into named constants",
  "OWASP/cve-lite-cli#1229": "De-duplicate flag-conflict error messages",
  "OWASP/cve-lite-cli#1228":
    "Add braces to remaining single-line `if` statements",
  "OWASP/cve-lite-cli#1202": {
    change: "Surface the 5000-file scan cap so `--only-used` can't drop findings",
    area: "`fix` · `security`",
  },
  "OWASP/cve-lite-cli#1200": {
    change: "Document the OA010 override-hygiene rule",
    area: "`docs` · `rules`",
  },
  "OWASP/cve-lite-cli#1183": {
    change: "Apply the `0.x` caret rule in `satisfiesRange`",
    area: "`fix` · `semver`",
  },
  "OWASP/cve-lite-cli#1181":
    "Correct OA008 pluralization and order copies by version",
  "OWASP/cve-lite-cli#1273":
    "Ignore `.claude/` so the rule travels with the repo",
  "OWASP/cve-lite-cli#1271":
    "Emit HTML override fix commands relative to the scanned project",
};

async function api(path) {
  const res = await fetch(`https://api.github.com${path}`, {
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    },
  });
  if (!res.ok) {
    throw new Error(`GET ${path} -> ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// All merged PRs authored by USER in one repo, newest merge first.
async function mergedPullRequests({ owner, repo }) {
  const q = `repo:${owner}/${repo} is:pr is:merged author:${USER}`;
  const params = new URLSearchParams({
    q,
    per_page: "100",
    sort: "created",
    order: "desc",
  });
  const data = await api(`/search/issues?${params}`);
  return data.items
    .map((item) => ({
      number: item.number,
      title: item.title,
      mergedAt: item.pull_request?.merged_at ?? "",
      url: item.html_url,
    }))
    .filter((pr) => pr.mergedAt)
    .sort((a, b) => (a.mergedAt < b.mergedAt ? 1 : -1));
}

// "fix(masonry): do the thing (#42)" -> { type, scope, subject }
function parseTitle(raw) {
  const title = raw
    .replace(/^#\d+\s*\|\s*/, "")
    .replace(/\s*\(#\d+\)\s*$/, "")
    .trim();
  const m = title.match(/^([a-z]+)(?:\(([^)]+)\))?!?:\s*(.+)$/i);
  if (!m) return { type: null, scope: null, subject: title };
  return {
    type: m[1].toLowerCase(),
    scope: m[2] ? m[2].trim() : null,
    subject: m[3].trim(),
  };
}

function areaFor(parsed) {
  const parts = [];
  if (parsed.type) parts.push(`\`${parsed.type}\``);
  if (parsed.scope) parts.push(`\`${parsed.scope}\``);
  return parts.length ? parts.join(" · ") : "—";
}

function cell(text) {
  return text.replace(/\|/g, "\\|");
}

function badge(repo, count) {
  const query = `https://github.com/${repo.owner}/${repo.repo}/pulls?q=is%3Apr+author%3A${USER}+is%3Amerged`;
  const label = `${repo.badgeLabel}-${count}_merged_PR${count === 1 ? "" : "s"}-${repo.badgeColor}`;
  return `  <a href="${query}"><img src="https://img.shields.io/badge/${label}?style=for-the-badge" alt="${repo.heading} merged PRs"/></a>`;
}

function repoSection(repo, prs) {
  const lines = [
    `### ${repo.heading} · [${repo.repo}](https://github.com/${repo.owner}/${repo.repo})`,
    `<sub>${repo.subtitle}</sub>`,
    "",
    "| PR | Change | Area |",
    "|:--:|---|---|",
  ];
  for (const pr of prs) {
    const parsed = parseTitle(pr.title);
    const override = OVERRIDES[`${repo.owner}/${repo.repo}#${pr.number}`];
    const change =
      (typeof override === "string" ? override : override?.change) ??
      parsed.subject;
    const area =
      (typeof override === "object" && override?.area) || areaFor(parsed);
    lines.push(
      `| [#${pr.number}](${pr.url}) | ${cell(change)} | ${area} |`,
    );
  }
  return lines.join("\n");
}

function render(sections) {
  const parts = [START, '<p align="center">'];
  parts.push(sections.map((s) => badge(s.repo, s.prs.length)).join("\n  &nbsp;\n"));
  parts.push("</p>");
  for (const s of sections) {
    parts.push("", "<br/>", "", repoSection(s.repo, s.prs));
  }
  parts.push(END);
  return parts.join("\n");
}

async function main() {
  const sections = [];
  for (const repo of REPOS) {
    const prs = await mergedPullRequests(repo);
    if (prs.length) sections.push({ repo, prs });
  }
  const generated = render(sections);

  const readme = await readFile(README, "utf8");
  const startIdx = readme.indexOf(START);
  const endIdx = readme.indexOf(END);
  if (startIdx === -1 || endIdx === -1 || endIdx < startIdx) {
    throw new Error(`README.md is missing ${START} / ${END} markers`);
  }
  const updated =
    readme.slice(0, startIdx) +
    generated +
    readme.slice(endIdx + END.length);

  if (updated === readme) {
    console.log("Contributions already up to date.");
    return;
  }
  await writeFile(README, updated, "utf8");
  const total = sections.reduce((n, s) => n + s.prs.length, 0);
  console.log(`Updated README.md (${total} merged PRs across ${sections.length} repos).`);
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
