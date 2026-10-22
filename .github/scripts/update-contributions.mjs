#!/usr/bin/env node
// Regenerates the "Open Source Contributions" section of README.md from the
// merged pull requests authored by GH_USER in each tracked repository, plus the
// proof block at the top of the README.
//
// Run: GITHUB_TOKEN=... node .github/scripts/update-contributions.mjs
// The sections are delimited by the CONTRIBUTIONS:START / CONTRIBUTIONS:END and
// PROOF:START / PROOF:END markers so the rest of the README stays untouched.

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
const PROOF_START = "<!-- PROOF:START -->";
const PROOF_END = "<!-- PROOF:END -->";

// How many highlighted PRs to surface above the fold.
const PROOF_LIMIT = 3;

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

// PRs worth leading with. Rank 1 is the most impactful. The generator puts
// highlighted PRs first and keeps the rest in merge order, so the section
// answers "what mattered" before "what landed recently".
const HIGHLIGHTS = {
  "OWASP/cve-lite-cli#1202": {
    rank: 1,
    proof:
      "A repo past 5,000 files could scan green with an empty report; a truncated scan is now distinguishable from a clean one, findings survive `--only-used`, and the cut is disclosed.",
    note:
      "A repo past the 5,000-file usage cap could scan green with an empty SARIF report. Findings now survive, --fail-on still gates, and the truncation is disclosed.",
  },
  "OWASP/cve-lite-cli#1231": {
    rank: 2,
    proof:
      "Compact mode showed 3 of 54 findings and called the plan complete; both finding and command-group truncation are now disclosed.",
    note:
      "Compact mode was showing 3 of 109 findings and calling the plan complete. Both withheld findings and command groups are now disclosed.",
  },
  "OWASP/cve-lite-cli#1183": {
    rank: 3,
    proof:
      "Fixed npm's `0.x` caret semantics in the semver oracle that decides which override versions a CVE report admits.",
    note:
      "Corrected npm's 0.x caret semantics in satisfiesRange, which decides which versions an override admits and feeds OA010.",
  },
  "OWASP/cve-lite-cli#1271": {
    rank: 4,
    note:
      "HTML fix commands were relative to the process cwd, so they did not run. They now resolve against the scanned project.",
  },
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

function describe(repo, pr) {
  const parsed = parseTitle(pr.title);
  const override = OVERRIDES[`${repo.owner}/${repo.repo}#${pr.number}`];
  return {
    change:
      (typeof override === "string" ? override : override?.change) ??
      parsed.subject,
    area: (typeof override === "object" && override?.area) || areaFor(parsed),
  };
}

function highlightFor(repo, pr) {
  return HIGHLIGHTS[`${repo.owner}/${repo.repo}#${pr.number}`];
}

function orderedPullRequests(repo, prs) {
  return [...prs].sort((a, b) => {
    const rankA = highlightFor(repo, a)?.rank ?? Number.POSITIVE_INFINITY;
    const rankB = highlightFor(repo, b)?.rank ?? Number.POSITIVE_INFINITY;
    if (rankA !== rankB) return rankA - rankB;
    return a.mergedAt < b.mergedAt ? 1 : -1;
  });
}

function repoSection(repo, prs) {
  const ordered = orderedPullRequests(repo, prs);
  const highlights = ordered.filter((pr) => highlightFor(repo, pr));

  const lines = [
    `### ${repo.heading} · [${repo.repo}](https://github.com/${repo.owner}/${repo.repo})`,
    `<sub>${repo.subtitle}</sub>`,
  ];

  if (highlights.length) {
    lines.push("", "**Impact highlights**", "");
    for (const pr of highlights) {
      const { change } = describe(repo, pr);
      lines.push(
        `- [#${pr.number}](${pr.url}) - **${cell(change)}**: ${highlightFor(repo, pr).note}`,
      );
    }
  }

  lines.push("", "| PR | Change | Area |", "|:--:|---|---|");
  for (const pr of ordered) {
    const { change, area } = describe(repo, pr);
    const marker = highlightFor(repo, pr) ? "★ " : "";
    lines.push(
      `| ${marker}[#${pr.number}](${pr.url}) | ${cell(change)} | ${area} |`,
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

// Top-of-profile proof block: the highlighted PRs in rank order, plus the
// merged-PR counts for every tracked repo, so the headline claims never drift
// from what is actually merged.
function renderProof(sections) {
  const highlighted = [];
  for (const { repo, prs } of sections) {
    for (const pr of prs) {
      const highlight = highlightFor(repo, pr);
      if (highlight) highlighted.push({ repo, pr, highlight });
    }
  }
  highlighted.sort((a, b) =>
    a.highlight.rank === b.highlight.rank
      ? a.pr.number - b.pr.number
      : a.highlight.rank - b.highlight.rank,
  );

  const counts = [...sections]
    .sort((a, b) => b.prs.length - a.prs.length)
    .map(
      ({ repo, prs }) =>
        `${prs.length} in [${repo.heading} ${repo.repo}](https://github.com/${repo.owner}/${repo.repo})`,
    )
    .join(", ");

  if (!highlighted.length) {
    return `Merged upstream so far: ${counts}.`;
  }

  const lines = [`Selected fixes (${counts}):`, ""];
  for (const { repo, pr, highlight } of highlighted.slice(0, PROOF_LIMIT)) {
    const { change } = describe(repo, pr);
    const summary = highlight.proof ?? `${change}: ${highlight.note}`;
    lines.push(`- [#${pr.number}](${pr.url}) ${cell(summary)}`);
  }
  return lines.join("\n");
}

function replaceBlock(text, start, end, body) {
  const startIdx = text.indexOf(start);
  const endIdx = text.indexOf(end);
  if (startIdx === -1 || endIdx === -1 || endIdx < startIdx) {
    throw new Error(`README.md is missing ${start} / ${end} markers`);
  }
  return `${text.slice(0, startIdx + start.length)}\n${body}\n${text.slice(endIdx)}`;
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
    replaceBlock(
      readme.slice(0, startIdx) + generated + readme.slice(endIdx + END.length),
      PROOF_START,
      PROOF_END,
      renderProof(sections),
    );

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
