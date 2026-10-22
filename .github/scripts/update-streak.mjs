#!/usr/bin/env node
// Regenerates streak.svg from GitHub's public contribution calendar. Rendering
// the card locally keeps the profile fast: no third-party cold start.
//
// Run: node .github/scripts/update-streak.mjs

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

const UA = "prx-my-streak";
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

async function accountCreated() {
  const res = await fetch(`https://api.github.com/users/${USER}`, {
    headers: {
      "User-Agent": UA,
      Accept: "application/vnd.github+json",
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    },
  });
  if (!res.ok) throw new Error(`GET /users/${USER} -> ${res.status}`);
  const data = await res.json();
  return data.created_at.slice(0, 10);
}

// GitHub renders one calendar per request. Counts live in the <tool-tip> for
// each day cell; days with no tooltip are zero.
function parseCalendar(html) {
  const counts = new Map();
  for (const m of html.matchAll(/for="([^"]+)"[^>]*>([^<]*)<\/tool-tip>/g)) {
    const text = m[2];
    const count = /No contributions/.test(text)
      ? 0
      : Number(text.match(/(\d+)/)?.[1] ?? 0);
    counts.set(m[1], count);
  }

  const days = [];
  for (const m of html.matchAll(
    /data-date="([0-9-]+)"\s+id="([^"]+)"[^>]*data-level="([0-9])"/g,
  )) {
    days.push({ date: m[1], count: counts.get(m[2]) ?? 0 });
  }
  return days;
}

async function calendarYear(year) {
  const url = `https://github.com/users/${USER}/contributions?from=${year}-01-01&to=${year}-12-31`;
  const res = await fetch(url, { headers: { "User-Agent": UA } });
  if (!res.ok) throw new Error(`GET ${year} contributions -> ${res.status}`);
  return parseCalendar(await res.text());
}

async function publicDays(since) {
  const today = isoToday();
  const firstYear = Number(since.slice(0, 4));
  const lastYear = Number(today.slice(0, 4));
  const years = [];
  for (let y = firstYear; y <= lastYear; y += 1) years.push(y);

  const pages = await Promise.all(years.map(calendarYear));
  const byDate = new Map();
  for (const day of pages.flat()) {
    if (day.date >= since && day.date <= today) byDate.set(day.date, day.count);
  }
  return [...byDate].sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([date, count]) => ({
    date,
    count,
  }));
}

function runs(days) {
  const out = [];
  let current = null;
  for (const day of days) {
    if (day.count > 0) {
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
  if (end >= 0 && days[end].count === 0) end -= 1;
  let length = 0;
  for (let i = end; i >= 0 && days[i].count > 0; i -= 1) length += 1;
  if (length === 0) return { length: 0, start: "", end: "" };
  return { length, start: days[end - length + 1].date, end: days[end].date };
}

function fmt(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`;
}

function esc(text) {
  return String(text).replace(/[&<>"]/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
  })[c]);
}

function updatedAt() {
  const now = new Date().toLocaleString("en-GB", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${now} IST`;
}

function render(total, current, longest, since) {
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
      sub: `since ${MONTHS[Number(since.slice(5, 7)) - 1]} ${since.slice(0, 4)}`,
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
    <text x="30" y="168" fill="#8b949e" font-size="10">Updated ${esc(updatedAt())}</text>
  </g>
</svg>
`;
}

async function main() {
  const since = await accountCreated();
  const days = await publicDays(since);
  if (!days.length) throw new Error("No contribution days returned");

  const total = days.reduce((sum, day) => sum + day.count, 0);
  const streak = currentStreak(days);
  const longest = runs(days).sort((a, b) => b.length - a.length)[0] ?? {
    length: 0,
    start: "",
    end: "",
  };

  await writeFile(OUT, render(total, streak, longest, since), "utf8");
  console.log(
    `streak.svg: ${streak.length} current, ${longest.length} longest, ${total} total since ${since}`,
  );
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
