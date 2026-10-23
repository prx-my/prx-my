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

async function mergedPrCount(repo) {
  const query = `/search/issues?q=${encodeURIComponent(
    `repo:${repo} is:pr is:merged author:${USER}`,
  )}&per_page=1`;
  const result = await api(query);
  return result.total_count;
}

async function loadData() {
  const [profile, cve, owasp, sugar, calendar] = await Promise.all([
    api(`/users/${USER}`),
    api("/repos/OWASP/cve-lite-cli"),
    mergedPrCount("OWASP/cve-lite-cli"),
    mergedPrCount("sugarlabs/musicblocks-v4"),
    graphql(
      `query($login: String!) {
        user(login: $login) {
          contributionsCollection {
            contributionCalendar {
              totalContributions
              weeks { contributionDays { date contributionCount } }
            }
          }
        }
      }`,
      { login: USER },
    ),
  ]);

  const days = calendar.user.contributionsCollection.contributionCalendar.weeks
    .flatMap((week) => week.contributionDays)
    .slice(-364);

  let longest = 0;
  let run = 0;
  for (const day of days) {
    run = day.contributionCount > 0 ? run + 1 : 0;
    longest = Math.max(longest, run);
  }

  return {
    merged: {
      owasp,
      sugar,
    },
    stars: cve.stargazers_count,
    followers: profile.followers,
    days,
    total: days.reduce((sum, day) => sum + day.contributionCount, 0),
    active: days.filter((day) => day.contributionCount > 0).length,
    longest,
    peak: days.reduce((max, day) => Math.max(max, day.contributionCount), 0),
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

function heroDesktop(data) {
  const width = 1200;
  const height = 450;
  const left = 56;
  const panelX = 744;
  const panelW = 400;
  const stats = [
    [String(data.merged.owasp), "MERGED / OWASP"],
    [String(data.merged.sugar).padStart(2, "0"), "MERGED / SUGAR LABS"],
    [num(data.stars), "STARS / CVE-LITE-CLI"],
    [String(COPY.wins).padStart(2, "0"), "HACKATHON WINS"],
  ];

  const statSvg = stats
    .map(([value, label], i) => {
      const x = left + i * 172;
      return `<g>
        ${text(x, 366, value, { family: SERIF, size: 34, weight: 700 })}
        ${text(x, 386, label, { size: 9, fill: C.muted, spacing: 1.2 })}
      </g>`;
    })
    .join("");

  const gridY = 214;
  const gridH = 46;
  const capTick = 53;
  const survivorTick = 58;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img">
  <title>${esc(COPY.name)} — ${esc(COPY.role)}</title>
  <desc>${esc(`${COPY.role} in TypeScript and Python. ${data.merged.owasp} merged pull requests in OWASP cve-lite-cli (${num(data.stars)} stars). ${COPY.availability}. Diagram: pull request 1202, a scan that stopped at 5,000 files and still surfaced a finding.`)}</desc>
  ${defs({ sweepTo: (capTick * ((panelW - 48) / 64)).toFixed(0) })}
  <rect width="${width}" height="${height}" fill="${C.paper}"/>
  <rect x="0.5" y="0.5" width="${width - 1}" height="${height - 1}" fill="none" stroke="${C.hair}"/>

  ${rule(left, 40, width - left, 40)}
  ${text(left, 28, COPY.kicker, { size: 10, fill: C.muted, spacing: 2 })}
  ${text(width - left, 28, COPY.location, { size: 10, fill: C.muted, spacing: 1.5, anchor: "end" })}

  ${text(left - 2, 148, COPY.name, { family: SERIF, size: 62, weight: 700, spacing: -1.5 })}
  ${rule(left, 172, 700, 172)}
  ${text(left, 208, COPY.role, { size: 21 })}
  ${text(left, 234, COPY.stack, { size: 11, fill: C.muted, spacing: 2 })}

  <circle cx="${left + 4}" cy="286" r="4.5" fill="${C.accent}" class="pulse"/>
  ${text(left + 18, 291, COPY.availability, { size: 12, fill: C.accent, spacing: 1.6, weight: 500 })}

  ${statSvg}

  ${rule(left, 408, width - left, 408)}
  ${text(left, 430, `${COPY.site}  ·  github.com/${COPY.handle}`, { size: 10, fill: C.muted, spacing: 1 })}
  ${text(width - left, 430, `UPDATED ${new Date().toISOString().slice(0, 10)}`, { size: 10, fill: C.muted, spacing: 1, anchor: "end" })}

  ${rule(panelX, 92, panelX, 380)}
  ${text(panelX + 24, 116, `PR #${COPY.highlight.pr} / TRUNCATED SCAN`, { size: 10, fill: C.muted, spacing: 1.6 })}
  ${text(panelX + 24, 154, "1 FINDING", { family: SERIF, size: 24, weight: 700, fill: C.survive })}
  ${text(panelX + 24, 176, "SURVIVES", { family: SERIF, size: 24, weight: 700, fill: C.survive })}
  ${fileGrid({ x: panelX + 24, y: gridY, width: panelW - 48, height: gridH, ticks: 64, cap: capTick, survivor: survivorTick })}
  ${text(panelX + 24, 314, "A scan that stops early", { family: SERIF, size: 17, style: "font-style:italic" })}
  ${text(panelX + 24, 334, "is not a clean scan.", { family: SERIF, size: 17, style: "font-style:italic" })}
  ${text(panelX + 24, 360, `MERGED ${COPY.highlight.merged}`, { size: 9, fill: C.muted, spacing: 1.4 })}
</svg>`;
}

function heroPhone(data) {
  const width = 480;
  const height = 780;
  const left = 28;
  const gridY = 548;
  const gridH = 40;
  const capTick = 39;
  const survivorTick = 43;
  const stats = [
    [String(data.merged.owasp), "MERGED / OWASP"],
    [String(data.merged.sugar).padStart(2, "0"), "MERGED / SUGAR"],
    [num(data.stars), "STARS / CVE-LITE-CLI"],
    [String(COPY.wins).padStart(2, "0"), "HACKATHON WINS"],
  ];

  const statSvg = stats
    .map(([value, label], i) => {
      const x = left + (i % 2) * 210;
      const y = 330 + Math.floor(i / 2) * 62;
      return `<g>
        ${text(x, y, value, { family: SERIF, size: 30, weight: 700 })}
        ${text(x, y + 17, label, { size: 8.5, fill: C.muted, spacing: 1.1 })}
      </g>`;
    })
    .join("");

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img">
  <title>${esc(COPY.name)} — ${esc(COPY.role)}</title>
  <desc>${esc(`${COPY.role} in TypeScript and Python. ${data.merged.owasp} merged pull requests in OWASP cve-lite-cli. ${COPY.availability}.`)}</desc>
  ${defs({ sweepTo: (capTick * ((width - 56) / 48)).toFixed(0) })}
  <rect width="${width}" height="${height}" fill="${C.paper}"/>
  <rect x="0.5" y="0.5" width="${width - 1}" height="${height - 1}" fill="none" stroke="${C.hair}"/>

  ${rule(left, 42, width - left, 42)}
  ${text(left, 30, COPY.kicker, { size: 8.5, fill: C.muted, spacing: 1.6 })}
  ${text(width - left, 30, "JAIPUR, IN", { size: 8.5, fill: C.muted, spacing: 1.4, anchor: "end" })}

  ${text(left - 1, 124, "Prakhar", { family: SERIF, size: 46, weight: 700, spacing: -1 })}
  ${text(left - 1, 168, "Gupta", { family: SERIF, size: 46, weight: 700, spacing: -1 })}
  ${rule(left, 190, width - left, 190)}
  ${text(left, 222, COPY.role, { size: 17 })}
  ${text(left, 246, COPY.stack, { size: 9.5, fill: C.muted, spacing: 1.8 })}

  <circle cx="${left + 4}" cy="286" r="4" fill="${C.accent}" class="pulse"/>
  ${text(left + 16, 290, COPY.availability, { size: 10.5, fill: C.accent, spacing: 1, weight: 500 })}

  ${statSvg}

  ${rule(left, 440, width - left, 440)}
  ${text(left, 468, `PR #${COPY.highlight.pr} / TRUNCATED SCAN`, { size: 9, fill: C.muted, spacing: 1.4 })}
  ${text(width - left, 468, "1 FINDING SURVIVES", { size: 9, fill: C.survive, spacing: 1.2, anchor: "end" })}
  ${fileGrid({ x: left, y: gridY, width: width - left * 2, height: gridH, ticks: 48, cap: capTick, survivor: survivorTick })}
  ${text(left, 650, "A scan that stops early", { family: SERIF, size: 16, style: "font-style:italic" })}
  ${text(left, 670, "is not a clean scan.", { family: SERIF, size: 16, style: "font-style:italic" })}
  ${text(left, 696, `MERGED ${COPY.highlight.merged} · OWASP/CVE-LITE-CLI`, { size: 8, fill: C.muted, spacing: 1.2 })}

  ${rule(left, 704, width - left, 704)}
  ${text(left, 728, `${COPY.site} · github.com/${COPY.handle}`, { size: 8.5, fill: C.muted, spacing: 0.8 })}
  ${text(width - left, 728, new Date().toISOString().slice(0, 10), { size: 8.5, fill: C.muted, spacing: 0.8, anchor: "end" })}
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
