#!/usr/bin/env node
// Regenerates streak.svg from the GitHub contribution calendar. Rendering the
// card locally keeps the profile fast: no third-party cold start on page load.
//
// Run: GITHUB_TOKEN=... node .github/scripts/update-streak.mjs

import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const USER = process.env.GH_USER || "prx-my";
const TOKEN = process.env.GITHUB_TOKEN || process.env.GH_TOKEN || "";

const OUT = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "streak.svg",
);

const QUERY = `query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}`;

async function contributions() {
  const res = await fetch("https://api.github.com/graphql", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      "Content-Type": "application/json",
      "User-Agent": "prx-my-streak",
    },
    body: JSON.stringify({ query: QUERY, variables: { login: USER } }),
  });
  if (!res.ok) throw new Error(`GraphQL ${res.status} ${res.statusText}`);
  const data = await res.json();
  if (data.errors?.length) throw new Error(data.errors[0].message);
  return data.data.user.contributionsCollection.contributionCalendar;
}

function runs(days) {
  const out = [];
  let current = null;
  for (const day of days) {
    if (day.contributionCount > 0) {
      if (!current) current = { start: day.date, end: day.date, length: 0 };
      current.end = day.date;
      current.length += 1;
    } else if (current) {
      out.push(current);
      current = null;
    }
  }
  if (current) out.push(current);
  return out;
}

function currentStreak(days) {
  let end = days.length - 1;
  if (end >= 0 && days[end].contributionCount === 0) end -= 1;
  let length = 0;
  for (let i = end; i >= 0 && days[i].contributionCount > 0; i -= 1) length += 1;
  if (length === 0) return { length: 0, start: "", end: "" };
  return { length, start: days[end - length + 1].date, end: days[end].date };
}

function fmt(iso) {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

function esc(text) {
  return String(text).replace(/[&<>"]/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
  })[c]);
}

function render(total, current, longest) {
  const cols = [
    {
      x: 160,
      label: "Current Streak",
      value: current.length,
      sub: current.length ? `${fmt(current.start)} – ${fmt(current.end)}` : "No active streak",
      color: "#38bdf8",
    },
    {
      x: 330,
      label: "Longest Streak",
      value: longest.length,
      sub: longest.length ? `${fmt(longest.start)} – ${fmt(longest.end)}` : "",
      color: "#2563eb",
    },
    {
      x: 500,
      label: "Total Contributions",
      value: total,
      sub: "",
      color: "#e2e8f0",
    },
  ];

  const cells = cols
    .map(
      (c) => `
    <text x="${c.x}" y="86" text-anchor="middle" fill="${c.color}" font-size="34" font-weight="700">${esc(c.value)}</text>
    <text x="${c.x}" y="116" text-anchor="middle" fill="#c9d1d9" font-size="13" font-weight="600">${esc(c.label)}</text>
    <text x="${c.x}" y="140" text-anchor="middle" fill="#8b949e" font-size="11">${esc(c.sub)}</text>`,
    )
    .join("");

  return `<svg xmlns="http://www.w3.org/2000/svg" width="660" height="180" viewBox="0 0 660 180" role="img" aria-label="GitHub streak: ${current.length} current, ${longest.length} longest, ${total} total contributions">
  <rect x="0.5" y="0.5" width="659" height="179" rx="12" fill="#0d1117" stroke="#30363d"/>
  <text x="30" y="44" fill="#e2e8f0" font-family="ui-sans-serif, -apple-system, Segoe UI, Helvetica, Arial, sans-serif" font-size="17" font-weight="700">GitHub Streak</text>
  <text x="630" y="44" text-anchor="end" fill="#8b949e" font-family="ui-sans-serif, -apple-system, Segoe UI, Helvetica, Arial, sans-serif" font-size="12">@${esc(USER)}</text>
  <g font-family="ui-sans-serif, -apple-system, Segoe UI, Helvetica, Arial, sans-serif">${cells}
    <circle cx="76" cy="100" r="30" fill="none" stroke="#2563eb" stroke-width="3" opacity="0.8"/>
    <path d="M76 82c8 8 12 14 12 20a12 12 0 0 1-24 0c0-6 4-12 12-20z" fill="#2563eb"/>
  </g>
</svg>
`;
}

async function main() {
  if (!TOKEN) throw new Error("GITHUB_TOKEN is required");
  const calendar = await contributions();
  const days = calendar.weeks.flatMap((w) => w.contributionDays);
  days.sort((a, b) => (a.date < b.date ? -1 : 1));

  const streak = currentStreak(days);
  const longest = runs(days).sort((a, b) => b.length - a.length)[0] ?? {
    length: 0,
    start: "",
    end: "",
  };

  await writeFile(OUT, render(calendar.totalContributions, streak, longest), "utf8");
  console.log(
    `streak.svg: ${streak.length} current, ${longest.length} longest, ${calendar.totalContributions} total`,
  );
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
