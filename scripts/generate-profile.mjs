#!/usr/bin/env node
// Generates the profile's bespoke SVG assets from live GitHub data.
//
// Run: GITHUB_TOKEN=... node scripts/generate-profile.mjs
//
// Outputs (committed to the repo, rendered by README.md):
//   assets/hero.svg          desktop hero
//   assets/hero-phone.svg    narrow hero
//   assets/activity.svg      contribution signal trace
//   assets/activity-phone.svg

import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const USER = process.env.GH_USER || "prx-my";
const TOKEN = process.env.GITHUB_TOKEN || process.env.GH_TOKEN || "";
const OUT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "assets");

const MONO = "'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace";
const SERIF = "Georgia, 'Iowan Old Style', 'Times New Roman', serif";

const C = {
  paper: "#F3EDE3",
  ink: "#17130F",
  muted: "#7A6C5D",
  hair: "#D8CEBF",
  wash: "#E9E1D4",
  accent: "#B23A1E",
  survive: "#1F6F5C",
};

const COPY = {
  name: "Prakhar Gupta",
  handle: "prx-my",
  kicker: "PRX-MY / FIELD NOTES 01",
  location: "JAIPUR, IN · 26.9124° N / 75.7873° E",
  role: "Backend & security tooling",
  stack: "TYPESCRIPT · PYTHON · NODE",
  availability: "OPEN TO SWE INTERNSHIPS · ANY TERM",
  site: "prxmy.in",
  wins: 3,
  products: 2,
  highlight: {
    pr: "1202",
    repo: "OWASP/cve-lite-cli",
    merged: "2026-10-01",
  },
};

const esc = (value) =>
  String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const num = (value) => new Intl.NumberFormat("en-US").format(value);

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

async function graphql(query, variables) {
  const res = await fetch("https://api.github.com/graphql", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    },
    body: JSON.stringify({ query, variables }),
  });
  const data = await res.json();
  if (!res.ok || data.errors) {
    throw new Error(
      `GraphQL -> ${res.status} ${data.errors?.map((e) => e.message).join("; ") ?? ""}`,
    );
  }
  return data.data;
}

function displayTitle(title) {
  return title
    .replace(/^[a-z]+(?:\([^)]+\))?!?:\s*/i, "")
    .replace(/\s*\(#\d+\)\s*$/, "")
    .trim();
}

async function mergedPullRequests(repo) {
  const query = `/search/issues?q=${encodeURIComponent(
    `repo:${repo} is:pr is:merged author:${USER}`,
  )}&per_page=100&sort=updated&order=desc`;
  const result = await api(query);
  return {
    total: result.total_count,
    items: result.items
      .map((item) => ({
        number: item.number,
        title: displayTitle(item.title),
        date: (item.pull_request?.merged_at ?? "").slice(0, 10),
        repo,
      }))
      .filter((item) => item.date),
  };
}

async function loadData() {
  const [profile, cve, owasp, sugar, calendar] = await Promise.all([
    api(`/users/${USER}`),
    api("/repos/OWASP/cve-lite-cli"),
    mergedPullRequests("OWASP/cve-lite-cli"),
    mergedPullRequests("sugarlabs/musicblocks-v4"),
    graphql(
      `query($login: String!) {
        user(login: $login) {
          contributionsCollection {
            contributionCalendar {
              totalContributions
              weeks { contributionDays { date contributionCount } }
            }
          }
          repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
            nodes { languages(first: 10) { edges { size node { name } } } }
          }
        }
      }`,
      { login: USER },
    ),
  ]);

  const days = calendar.user.contributionsCollection.contributionCalendar.weeks
    .flatMap((week) => week.contributionDays)
    .slice(-365);

  let longest = 0;
  let run = 0;
  for (const day of days) {
    run = day.contributionCount > 0 ? run + 1 : 0;
    longest = Math.max(longest, run);
  }

  const merges = [...owasp.items, ...sugar.items].sort((a, b) =>
    a.date < b.date ? 1 : -1,
  );

  const mergeFirst = merges[merges.length - 1]?.date ?? merges[0]?.date ?? "";
  const mergeLast = merges[0]?.date ?? "";
  const mergeWeeks = Math.max(
    1,
    (new Date(mergeLast) - new Date(mergeFirst)) / (7 * 24 * 60 * 60 * 1000),
  );

  const bytes = new Map();
  for (const repo of calendar.user.repositories.nodes) {
    for (const edge of repo.languages.edges) {
      bytes.set(edge.node.name, (bytes.get(edge.node.name) ?? 0) + edge.size);
    }
  }
  const byteTotal = [...bytes.values()].reduce((sum, size) => sum + size, 0) || 1;
  const languages = [...bytes.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([name, size]) => ({ name, pct: (size / byteTotal) * 100 }));

  return {
    merged: {
      owasp: owasp.total,
      sugar: sugar.total,
    },
    merges,
    latest: merges.slice(0, 3),
    cadence: merges.length / mergeWeeks,
    languages,
    stars: cve.stargazers_count,
    followers: profile.followers,
    repos: profile.public_repos,
    joined: profile.created_at.slice(0, 4),
    days,
    total: days.reduce((sum, day) => sum + day.contributionCount, 0),
    active: days.filter((day) => day.contributionCount > 0).length,
    longest,
    peak: days.reduce((max, day) => Math.max(max, day.contributionCount), 0),
    peakDate: days.reduce((best, day) => (day.contributionCount > best.contributionCount ? day : best), days[0]).date,
  };
}

function text(x, y, value, options = {}) {
  const {
    size = 12,
    fill = C.ink,
    family = MONO,
    weight = 400,
    anchor = "start",
    spacing = 0,
    opacity = 1,
    style = "",
  } = options;
  return `<text x="${x}" y="${y}" font-family="${family}" font-size="${size}" fill="${fill}" font-weight="${weight}" text-anchor="${anchor}" letter-spacing="${spacing}" opacity="${opacity}"${style ? ` style="${style}"` : ""}>${esc(value)}</text>`;
}

function rule(x1, y1, x2, y2, color = C.hair, width = 1, dash = "") {
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${width}"${dash ? ` stroke-dasharray="${dash}"` : ""}/>`;
}

function defs({ sweepTo }) {
  return `<defs>
    <pattern id="hatch" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
      <line x1="0" y1="0" x2="0" y2="6" stroke="${C.hair}" stroke-width="1"/>
    </pattern>
    <style>
      @keyframes pulse { 0%, 100% { opacity: 1 } 50% { opacity: 0.3 } }
      @keyframes scan { 0%, 12% { transform: translateX(0); opacity: 0 } 18% { opacity: 0.55 } 64% { transform: translateX(${sweepTo}px); opacity: 0.55 } 72%, 100% { transform: translateX(${sweepTo}px); opacity: 0 } }
      .pulse { animation: pulse 2.6s ease-in-out infinite; }
      .sweep { animation: scan 7.5s linear infinite; }
      @media (prefers-reduced-motion: reduce) { .pulse, .sweep { animation: none; } }
    </style>
  </defs>`;
}

// One horizontal run of file ticks. `cap` is the index where scanning stops;
// `survivor` is the tick that still carries a finding.
function fileGrid({ x, y, width, height, ticks, cap, survivor }) {
  const pitch = width / ticks;
  const barW = Math.max(1.6, pitch * 0.42);
  const capX = x + pitch * cap;
  const survivorX = x + pitch * survivor + barW / 2;

  const bars = [];
  for (let i = 0; i < ticks; i += 1) {
    const bx = x + pitch * i + (pitch - barW) / 2;
    const scanned = i < cap;
    const isSurvivor = i === survivor;
    bars.push(
      `<rect x="${bx.toFixed(1)}" y="${y}" width="${barW.toFixed(1)}" height="${height}" fill="${
        isSurvivor ? C.survive : scanned ? C.muted : C.hair
      }" opacity="${isSurvivor ? 1 : scanned ? 0.55 : 0.7}"/>`,
    );
  }

  return `<g>
    <rect x="${capX}" y="${y - 12}" width="${(x + width - capX).toFixed(1)}" height="${height + 24}" fill="${C.wash}" opacity="0.55"/>
    <rect x="${capX}" y="${y - 12}" width="${(x + width - capX).toFixed(1)}" height="${height + 24}" fill="url(#hatch)" opacity="0.8"/>
    ${bars.join("")}
    <rect class="sweep" x="${x}" y="${y - 10}" width="1.5" height="${height + 20}" fill="${C.accent}" opacity="0"/>
    ${rule(capX, y - 30, capX, y + height + 12, C.accent, 1, "4 4")}
    <circle cx="${survivorX}" cy="${y - 10}" r="4" fill="${C.survive}"/>
    ${rule(survivorX, y - 10, survivorX, y, C.survive, 1)}
    ${text(capX - 8, y - 36, "5,000 FILES", { size: 10, fill: C.accent, anchor: "end", spacing: 1 })}
    ${text(capX + 8, y + height + 26, "UNSCANNED", { size: 10, fill: C.muted, spacing: 1.5 })}
  </g>`;
}

function polar(cx, cy, r, degrees) {
  const rad = (degrees * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
}

function shortDate(iso) {
  return new Date(`${iso}T00:00:00Z`)
    .toLocaleString("en-US", { day: "numeric", month: "short", timeZone: "UTC" })
    .toUpperCase();
}

const clip = (value, length) =>
  value.length > length ? `${value.slice(0, length - 1)}…` : value;

// One year of daily contributions as a radial instrument, with each merged
// upstream PR plotted as an inner orbit.
function yearRing(data, { cx, cy, tickR, outerR, mergeR, scale = 1, skipLabelX = 0 }) {
  const days = data.days;
  const max = Math.max(1, data.peak);
  const n = days.length;
  const angleAt = (index) => -90 + (index / n) * 360;
  const tickLen = outerR - tickR - 4;

  const ticks = days
    .map((day, index) => {
      const angle = angleAt(index);
      const [x1, y1] = polar(cx, cy, tickR, angle);
      const active = day.contributionCount > 0;
      const ratio = Math.sqrt(day.contributionCount / max);
      const length = active ? 2 + ratio * tickLen : 1.5;
      const [x2, y2] = polar(cx, cy, tickR + length, angle);
      return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="${
        active ? C.accent : C.hair
      }" stroke-width="${active ? 1.25 : 1}" opacity="${active ? 0.35 + 0.65 * ratio : 0.7}"/>`;
    })
    .join("");

  const monthMarks = [];
  let lastMonth = "";
  days.forEach((day, index) => {
    const month = day.date.slice(0, 7);
    if (month === lastMonth) return;
    lastMonth = month;
    const angle = angleAt(index);
    const [x, y] = polar(cx, cy, outerR + 15, angle);
    const cos = Math.cos((angle * Math.PI) / 180);
    monthMarks.push({
      x,
      y,
      angle,
      day,
      anchor: cos > 0.25 ? "start" : cos < -0.25 ? "end" : "middle",
      label: new Date(`${day.date}T00:00:00Z`)
        .toLocaleString("en-US", { month: "short", timeZone: "UTC" })
        .toUpperCase(),
    });
  });

  // The window starts mid-month, so the first label would collide with the
  // second. Drop it and stamp the year on the first and last labels instead.
  const marks = Number(days[0].date.slice(8, 10)) > 15 ? monthMarks.slice(1) : monthMarks;
  const monthLabels = marks.map((mark, index) => {
    const edge = index === 0 || index === marks.length - 1;
    const label = edge ? `${mark.label} '${mark.day.date.slice(2, 4)}` : mark.label;
    if (skipLabelX && mark.x < skipLabelX) return "";
    const [tx1, ty1] = polar(cx, cy, outerR + 4, mark.angle);
    const [tx2, ty2] = polar(cx, cy, outerR + 10, mark.angle);
    return (
      `<line x1="${tx1.toFixed(1)}" y1="${ty1.toFixed(1)}" x2="${tx2.toFixed(1)}" y2="${ty2.toFixed(1)}" stroke="${C.hair}"/>` +
      text(mark.x, mark.y + 3, label, {
        size: 8.5 * scale,
        fill: C.muted,
        spacing: 1,
        anchor: mark.anchor,
      })
    );
  });

  const mergeDots = data.merges
    .map((merge, index) => {
      const dayIndex = days.findIndex((day) => day.date === merge.date);
      if (dayIndex < 0) return "";
      const angle = angleAt(dayIndex);
      const r = mergeR + (index % 3) * 4.5 * scale;
      const [x, y] = polar(cx, cy, r, angle);
      const color = merge.repo.startsWith("OWASP") ? C.accent : C.survive;
      return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${2.6 * scale}" fill="${color}"/>`;
    })
    .join("");

  const peak = days.reduce(
    (best, day) => (day.contributionCount > best.contributionCount ? day : best),
    days[0],
  );
  const peakAngle = angleAt(days.indexOf(peak));
  const [px, py] = polar(cx, cy, tickR + 4 + Math.sqrt(peak.contributionCount / max) * tickLen, peakAngle);

  return `<g>
    <circle cx="${cx}" cy="${cy}" r="${tickR}" fill="none" stroke="${C.hair}" stroke-width="1"/>
    <circle cx="${cx}" cy="${cy}" r="${outerR}" fill="none" stroke="${C.hair}" stroke-width="1"/>
    ${ticks}
    ${monthLabels.join("")}
    <circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="${2.2 * scale}" fill="${C.accent}"/>
    ${mergeDots}
  </g>`;
}

function heroDesktop(data) {
  const width = 1200;
  const height = 800;
  const left = 56;
  const right = width - left;
  const today = new Date().toISOString().slice(0, 10);
  const stats = [
    [String(data.merged.owasp), "MERGED / OWASP"],
    [String(data.merged.sugar).padStart(2, "0"), "MERGED / SUGAR LABS"],
    [num(data.stars), "STARS / CVE-LITE-CLI"],
    [String(COPY.wins).padStart(2, "0"), "HACKATHON WINS"],
  ];

  const statSvg = stats
    .map(([value, label], i) => {
      const x = left + (i % 2) * 186;
      const y = 372 + Math.floor(i / 2) * 78;
      return `<g>
        ${text(x, y, value, { family: SERIF, size: 34, weight: 700 })}
        ${text(x, y + 18, label, { size: 9, fill: C.muted, spacing: 1.1 })}
      </g>`;
    })
    .join("");

  const latest = data.latest
    .map((pr, i) => {
      const y = 532 + i * 22;
      const repo = pr.repo.startsWith("OWASP") ? "OWASP" : "SUGAR";
      return `${text(left, y, `#${pr.number}`, { size: 10, fill: C.accent, spacing: 0.4 })}
        ${text(left + 58, y, clip(pr.title, 38), { family: SERIF, size: 12 })}
        ${text(430, y, `${repo} · ${shortDate(pr.date)}`, { size: 8, fill: C.muted, spacing: 0.5, anchor: "end" })}`;
    })
    .join("");

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img">
  <title>${esc(COPY.name)} — ${esc(COPY.role)}</title>
  <desc>${esc(`${COPY.role} in TypeScript and Python. ${data.merged.owasp} merged pull requests in OWASP cve-lite-cli (${num(data.stars)} stars) and ${data.merged.sugar} in Sugar Labs. ${num(data.total)} contributions in the last year, longest streak ${data.longest} days. ${COPY.availability}.`)}</desc>
  ${defs({ sweepTo: (79 * (600 / 96)).toFixed(0) })}
  <rect width="${width}" height="${height}" fill="${C.paper}"/>
  <rect x="0.5" y="0.5" width="${width - 1}" height="${height - 1}" fill="none" stroke="${C.hair}"/>

  ${rule(left, 40, right, 40)}
  ${text(left, 28, COPY.kicker, { size: 10, fill: C.muted, spacing: 2 })}
  ${text(width / 2, 28, "SHEET 01 / 03", { size: 9, fill: C.muted, spacing: 1.8, anchor: "middle" })}
  ${text(right, 28, COPY.location, { size: 10, fill: C.muted, spacing: 1.5, anchor: "end" })}

  ${text(left - 2, 132, "Prakhar", { family: SERIF, size: 58, weight: 700, spacing: -1.5 })}
  ${text(left - 2, 190, "Gupta", { family: SERIF, size: 58, weight: 700, spacing: -1.5 })}
  ${rule(left, 212, 430, 212)}
  ${text(left, 246, COPY.role, { size: 20 })}
  ${text(left, 270, COPY.stack, { size: 11, fill: C.muted, spacing: 1.8 })}
  <circle cx="${left + 4}" cy="306" r="4.5" fill="${C.accent}" class="pulse"/>
  ${text(left + 18, 311, COPY.availability, { size: 11.5, fill: C.accent, spacing: 1.3, weight: 500 })}

  ${statSvg}

  ${text(left, 504, "LATEST LANDED", { size: 9, fill: C.muted, spacing: 1.8 })}
  ${rule(left, 512, 430, 512)}
  ${latest}

  ${rule(470, 62, 470, 596)}
  ${yearRing(data, { cx: 880, cy: 330, tickR: 196, outerR: 240, mergeR: 126, skipLabelX: 660 })}

  ${text(486, 96, "YEAR IN CONTRIBUTIONS", { size: 9, fill: C.muted, spacing: 1.6 })}
  ${text(486, 112, `365 DAYS · ENDING ${today}`, { size: 8.5, fill: C.muted, spacing: 1.1 })}
  ${text(right, 96, `MERGED UPSTREAM / ${data.merges.length}`, { size: 9, fill: C.muted, spacing: 1.2, anchor: "end" })}
  <circle cx="1009" cy="108" r="3" fill="${C.accent}"/>
  ${text(1017, 111, `OWASP ${data.merged.owasp}`, { size: 8.5, fill: C.muted, spacing: 0.6 })}
  <circle cx="1080" cy="108" r="3" fill="${C.survive}"/>
  ${text(1088, 111, `SUGAR ${data.merged.sugar}`, { size: 8.5, fill: C.muted, spacing: 0.6 })}

  ${text(478, 154, "PUBLIC REPOS / BYTES", { size: 9, fill: C.muted, spacing: 1.2 })}
  ${data.languages
    .map((lang, i) => {
      const y = 178 + i * 30;
      return `${text(478, y, lang.name.toUpperCase(), { size: 8.5, fill: C.muted, spacing: 0.8 })}
        ${text(578, y, `${lang.pct.toFixed(0)}%`, { size: 8.5, fill: C.muted, spacing: 0.4, anchor: "end" })}
        <rect x="478" y="${y + 5}" width="100" height="2.5" fill="${C.hair}"/>
        <rect x="478" y="${y + 5}" width="${((lang.pct / 100) * 100).toFixed(1)}" height="2.5" fill="${C.accent}" opacity="0.8"/>`;
    })
    .join("")}
  ${rule(478, 292, 578, 292)}
  ${text(478, 314, "FOLLOWERS", { size: 9, fill: C.muted, spacing: 1.1 })}
  ${text(578, 315, num(data.followers), { family: SERIF, size: 16, weight: 700, anchor: "end" })}
  ${text(478, 338, "PUBLIC REPOS", { size: 9, fill: C.muted, spacing: 1.1 })}
  ${text(578, 339, num(data.repos), { family: SERIF, size: 16, weight: 700, anchor: "end" })}
  ${text(478, 362, "JOINED", { size: 9, fill: C.muted, spacing: 1.1 })}
  ${text(578, 363, data.joined, { family: SERIF, size: 16, weight: 700, anchor: "end" })}
  ${rule(478, 382, 578, 382)}
  ${text(478, 404, "LAST MERGE", { size: 9, fill: C.muted, spacing: 1.1 })}
  ${text(578, 405, shortDate(data.merges[0].date), { family: SERIF, size: 14, weight: 700, anchor: "end" })}
  ${text(478, 428, "CADENCE", { size: 9, fill: C.muted, spacing: 1.1 })}
  ${text(578, 429, `${data.cadence.toFixed(1)} / WK`, { family: SERIF, size: 14, weight: 700, anchor: "end" })}

  ${text(880, 316, num(data.total), { family: SERIF, size: 46, weight: 700, anchor: "middle" })}
  ${text(880, 338, "CONTRIBUTIONS / 365 DAYS", { size: 8.5, fill: C.muted, spacing: 1.2, anchor: "middle" })}
  ${rule(810, 354, 950, 354)}
  ${text(880, 376, `${data.longest}-DAY STREAK`, { size: 10, fill: C.accent, spacing: 1.2, anchor: "middle" })}
  ${text(880, 394, `PEAK ${data.peak} · ${shortDate(data.peakDate)}`, { size: 8.5, fill: C.muted, spacing: 0.8, anchor: "middle" })}

  ${rule(left, 610, right, 610)}
  ${text(left, 636, `PR #${COPY.highlight.pr} / TRUNCATED SCAN`, { size: 10, fill: C.muted, spacing: 1.6 })}
  ${text(left, 654, "THE CAP IS FINE; THE AMBIGUITY WAS THE BUG.", { size: 8.5, fill: C.muted, spacing: 1.1 })}
  ${fileGrid({ x: 340, y: 666, width: 600, height: 22, ticks: 96, cap: 79, survivor: 86 })}
  ${text(right, 640, "A scan that stops early", { family: SERIF, size: 16, style: "font-style:italic", anchor: "end" })}
  ${text(right, 660, "is not a clean scan.", { family: SERIF, size: 16, style: "font-style:italic", anchor: "end" })}
  ${text(right, 682, `MERGED ${COPY.highlight.merged}`, { size: 8.5, fill: C.muted, spacing: 1.1, anchor: "end" })}

  ${rule(left, 748, right, 748)}
  ${text(left, 772, `${COPY.site} · github.com/${COPY.handle}`, { size: 9.5, fill: C.muted, spacing: 0.9 })}
  ${text(right, 772, `RENDERED ${today} · DATA GITHUB API`, { size: 9.5, fill: C.muted, spacing: 0.9, anchor: "end" })}
</svg>`;
}

function heroPhone(data) {
  const width = 480;
  const height = 1180;
  const left = 28;
  const right = width - left;
  const today = new Date().toISOString().slice(0, 10);
  const stats = [
    [String(data.merged.owasp), "MERGED / OWASP"],
    [String(data.merged.sugar).padStart(2, "0"), "MERGED / SUGAR"],
    [num(data.stars), "STARS / CVE-LITE-CLI"],
    [String(COPY.wins).padStart(2, "0"), "HACKATHON WINS"],
  ];

  const statSvg = stats
    .map(([value, label], i) => {
      const x = left + (i % 2) * 210;
      const y = 342 + Math.floor(i / 2) * 62;
      return `<g>
        ${text(x, y, value, { family: SERIF, size: 29, weight: 700 })}
        ${text(x, y + 17, label, { size: 8, fill: C.muted, spacing: 1 })}
      </g>`;
    })
    .join("");

  const latest = data.latest
    .slice(0, 2)
    .map((pr, i) => {
      const y = 478 + i * 22;
      return `${text(left, y, `#${pr.number}`, { size: 9, fill: C.accent, spacing: 0.4 })}
        ${text(left + 52, y, clip(pr.title, 40), { family: SERIF, size: 11 })}
        ${text(right, y, shortDate(pr.date), { size: 7.5, fill: C.muted, spacing: 0.5, anchor: "end" })}`;
    })
    .join("");

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img">
  <title>${esc(COPY.name)} — ${esc(COPY.role)}</title>
  <desc>${esc(`${COPY.role} in TypeScript and Python. ${data.merged.owasp} merged pull requests in OWASP cve-lite-cli. ${num(data.total)} contributions in the last year. ${COPY.availability}.`)}</desc>
  ${defs({ sweepTo: (52 * ((width - 56) / 64)).toFixed(0) })}
  <rect width="${width}" height="${height}" fill="${C.paper}"/>
  <rect x="0.5" y="0.5" width="${width - 1}" height="${height - 1}" fill="none" stroke="${C.hair}"/>

  ${rule(left, 40, right, 40)}
  ${text(left, 28, COPY.kicker, { size: 8.5, fill: C.muted, spacing: 1.6 })}
  ${text(right, 28, "SHEET 01 / 03", { size: 8, fill: C.muted, spacing: 1.4, anchor: "end" })}

  ${text(left - 1, 118, "Prakhar", { family: SERIF, size: 46, weight: 700, spacing: -1 })}
  ${text(left - 1, 166, "Gupta", { family: SERIF, size: 46, weight: 700, spacing: -1 })}
  ${rule(left, 188, right, 188)}
  ${text(left, 220, COPY.role, { size: 17 })}
  ${text(left, 244, COPY.stack, { size: 9.5, fill: C.muted, spacing: 1.6 })}
  <circle cx="${left + 4}" cy="282" r="4" fill="${C.accent}" class="pulse"/>
  ${text(left + 16, 286, COPY.availability, { size: 10, fill: C.accent, spacing: 1, weight: 500 })}

  ${statSvg}

  ${text(left, 448, "LATEST LANDED", { size: 8, fill: C.muted, spacing: 1.6 })}
  ${rule(left, 456, right, 456)}
  ${latest}

  ${yearRing(data, { cx: 240, cy: 700, tickR: 138, outerR: 172, mergeR: 96, scale: 0.78 })}

  ${text(240, 690, num(data.total), { family: SERIF, size: 33, weight: 700, anchor: "middle" })}
  ${text(240, 708, "CONTRIBUTIONS / 365 DAYS", { size: 7.5, fill: C.muted, spacing: 0.9, anchor: "middle" })}
  ${rule(188, 720, 292, 720)}
  ${text(240, 738, `${data.longest}-DAY STREAK`, { size: 8.5, fill: C.accent, spacing: 0.9, anchor: "middle" })}
  ${text(240, 754, `PEAK ${data.peak} · ${shortDate(data.peakDate)}`, { size: 7.5, fill: C.muted, spacing: 0.6, anchor: "middle" })}
  <circle cx="197" cy="769" r="2.4" fill="${C.accent}"/>
  ${text(203, 772, `OWASP ${data.merged.owasp}`, { size: 7.5, fill: C.muted, spacing: 0.5 })}
  <circle cx="261" cy="769" r="2.4" fill="${C.survive}"/>
  ${text(267, 772, `SUGAR ${data.merged.sugar}`, { size: 7.5, fill: C.muted, spacing: 0.5 })}

  ${text(left, 930, `PR #${COPY.highlight.pr} / TRUNCATED SCAN`, { size: 8.5, fill: C.muted, spacing: 1.2 })}
  ${fileGrid({ x: left, y: 950, width: width - left * 2, height: 16, ticks: 64, cap: 52, survivor: 57 })}
  ${text(left, 1014, "A scan that stops early", { family: SERIF, size: 15, style: "font-style:italic" })}
  ${text(right, 1014, "1 FINDING SURVIVES", { size: 8, fill: C.survive, spacing: 0.8, anchor: "end" })}
  ${text(left, 1034, "is not a clean scan.", { family: SERIF, size: 15, style: "font-style:italic" })}
  ${text(right, 1034, `MERGED ${COPY.highlight.merged}`, { size: 7.5, fill: C.muted, spacing: 0.8, anchor: "end" })}

  ${rule(left, 1108, right, 1108)}
  ${text(left, 1132, `${COPY.site} · github.com/${COPY.handle}`, { size: 8.5, fill: C.muted, spacing: 0.8 })}
  ${text(right, 1132, today, { size: 8.5, fill: C.muted, spacing: 0.8, anchor: "end" })}
</svg>`;
}

function signalPath(days, x, y, w, h, max) {
  const step = w / (days.length - 1);
  const points = days.map((day, i) => {
    const px = x + i * step;
    const ratio = Math.sqrt(day.contributionCount / max);
    const py = y + h - ratio * h;
    return [px, py];
  });
  const line = points
    .map(([px, py], i) => `${i === 0 ? "M" : "L"}${px.toFixed(1)},${py.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${(x + w).toFixed(1)},${y + h} L${x.toFixed(1)},${y + h} Z`;
  return { line, area, points };
}

function monthMarks(days, x, w) {
  const step = w / (days.length - 1);
  const marks = [];
  let lastMonth = "";
  days.forEach((day, i) => {
    const month = day.date.slice(0, 7);
    if (month !== lastMonth) {
      const label = new Date(`${day.date}T00:00:00Z`).toLocaleString("en-US", {
        month: "short",
        timeZone: "UTC",
      });
      marks.push({ x: x + i * step, label, year: day.date.slice(0, 4) });
      lastMonth = month;
    }
  });
  return marks;
}

function peakMark(days, x, y, w, h, max, size = 9) {
  const peak = days.reduce(
    (best, day) => (day.contributionCount > best.contributionCount ? day : best),
    days[0],
  );
  const index = days.indexOf(peak);
  const px = x + (index * w) / (days.length - 1);
  const py = y + h - Math.sqrt(peak.contributionCount / max) * h;
  const date = new Date(`${peak.date}T00:00:00Z`).toLocaleString("en-US", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
  const flip = px > x + w * 0.75;
  return `<g>
    ${rule(x, y, x + w, y, C.hair, 1, "2 4")}
    <circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="2.6" fill="${C.accent}"/>
    ${text(flip ? px - 8 : px + 8, Math.max(y + 10, py - 9), `${num(peak.contributionCount)} · ${date.toUpperCase()}`, { size, fill: C.muted, spacing: 0.8, anchor: flip ? "end" : "start" })}
  </g>`;
}

function activityDesktop(data) {
  const width = 1200;
  const height = 330;
  const left = 56;
  const chartX = left;
  const chartY = 168;
  const chartW = width - left * 2;
  const chartH = 96;
  const max = Math.max(1, data.peak);
  const { line, area } = signalPath(data.days, chartX, chartY, chartW, chartH, max);
  const months = monthMarks(data.days, chartX, chartW);

  const stats = [
    [num(data.total), "CONTRIBUTIONS"],
    [num(data.active), "ACTIVE DAYS"],
    [num(data.longest), "LONGEST STREAK"],
  ];

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img">
  <title>Contribution signal, last 52 weeks</title>
  <desc>${esc(`${num(data.total)} contributions across ${num(data.active)} active days, longest streak ${num(data.longest)} days.`)}</desc>
  <rect width="${width}" height="${height}" fill="${C.paper}"/>
  <rect x="0.5" y="0.5" width="${width - 1}" height="${height - 1}" fill="none" stroke="${C.hair}"/>

  ${rule(left, 40, width - left, 40)}
  ${text(left, 28, "ACTIVITY / LAST 52 WEEKS", { size: 10, fill: C.muted, spacing: 2 })}
  ${text(width - left, 28, "SHEET 02 · DAILY CONTRIBUTIONS · √ SCALE", { size: 10, fill: C.muted, spacing: 1.2, anchor: "end" })}

  ${stats
    .map(
      ([value, label], i) => `<g>
        ${text(left + i * 200, 100, value, { family: SERIF, size: 32, weight: 700 })}
        ${text(left + i * 200, 118, label, { size: 9, fill: C.muted, spacing: 1.4 })}
      </g>`,
    )
    .join("")}

  ${rule(chartX, chartY + chartH, chartX + chartW, chartY + chartH, C.ink, 1)}
  ${rule(chartX, chartY + chartH / 2, chartX + chartW, chartY + chartH / 2, C.hair, 1, "2 4")}
  <path d="${area}" fill="${C.accent}" opacity="0.10"/>
  <path d="${line}" fill="none" stroke="${C.accent}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
  ${peakMark(data.days, chartX, chartY, chartW, chartH, max)}
  ${months
    .map((mark, i) => {
      const last = i === months.length - 1;
      const show = i % 2 === 0 || last;
      const label = i === 0 || last ? `${mark.label} '${mark.year.slice(2)}` : mark.label;
      return `${rule(mark.x, chartY + chartH, mark.x, chartY + chartH + 6, C.hair, 1)}${
        show
          ? text(mark.x, chartY + chartH + 22, label, {
              size: 9,
              fill: C.muted,
              spacing: 0.8,
              anchor: last ? "end" : "start",
            })
          : ""
      }`;
    })
    .join("")}
</svg>`;
}

function activityPhone(data) {
  const width = 480;
  const height = 350;
  const left = 28;
  const chartX = left;
  const chartY = 172;
  const chartW = width - left * 2;
  const chartH = 112;
  const max = Math.max(1, data.peak);
  const { line, area } = signalPath(data.days, chartX, chartY, chartW, chartH, max);
  const months = monthMarks(data.days, chartX, chartW);

  const stats = [
    [num(data.total), "CONTRIBUTIONS"],
    [num(data.active), "ACTIVE DAYS"],
    [num(data.longest), "LONGEST STREAK"],
  ];

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img">
  <title>Contribution signal, last 52 weeks</title>
  <desc>${esc(`${num(data.total)} contributions across ${num(data.active)} active days, longest streak ${num(data.longest)} days.`)}</desc>
  <rect width="${width}" height="${height}" fill="${C.paper}"/>
  <rect x="0.5" y="0.5" width="${width - 1}" height="${height - 1}" fill="none" stroke="${C.hair}"/>
  ${rule(left, 40, width - left, 40)}
  ${text(left, 28, "ACTIVITY / LAST 52 WEEKS", { size: 8.5, fill: C.muted, spacing: 1.6 })}
  ${text(width - left, 28, "√ SCALE", { size: 8.5, fill: C.muted, spacing: 1.2, anchor: "end" })}

  ${stats
    .map(
      ([value, label], i) => `<g>
        ${text(left + i * 145, 92, value, { family: SERIF, size: 26, weight: 700 })}
        ${text(left + i * 145, 108, label, { size: 8, fill: C.muted, spacing: 1 })}
      </g>`,
    )
    .join("")}

  ${rule(chartX, chartY + chartH, chartX + chartW, chartY + chartH, C.ink, 1)}
  ${rule(chartX, chartY + chartH / 2, chartX + chartW, chartY + chartH / 2, C.hair, 1, "2 4")}
  <path d="${area}" fill="${C.accent}" opacity="0.10"/>
  <path d="${line}" fill="none" stroke="${C.accent}" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/>
  ${peakMark(data.days, chartX, chartY, chartW, chartH, max, 9)}
  ${months
    .map((mark, i) => {
      const last = i === months.length - 1;
      const show = i % 2 === 0 || last;
      const label = i === 0 || last ? `${mark.label} '${mark.year.slice(2)}` : mark.label;
      return show
        ? text(mark.x, chartY + chartH + 20, label, {
            size: 8,
            fill: C.muted,
            spacing: 0.6,
            anchor: last ? "end" : "start",
          })
        : "";
    })
    .join("")}
</svg>`;
}

async function main() {
  if (!TOKEN) {
    throw new Error("GITHUB_TOKEN is required for the contribution calendar.");
  }
  await mkdir(OUT, { recursive: true });
  const data = await loadData();

  const assets = {
    "hero.svg": heroDesktop(data),
    "hero-phone.svg": heroPhone(data),
    "activity.svg": activityDesktop(data),
    "activity-phone.svg": activityPhone(data),
  };

  for (const [name, svg] of Object.entries(assets)) {
    await writeFile(resolve(OUT, name), svg, "utf8");
  }

  console.log(
    `Rendered ${Object.keys(assets).length} assets: ${data.merged.owasp} OWASP + ${data.merged.sugar} Sugar Labs merged, ${num(data.total)} contributions.`,
  );
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
