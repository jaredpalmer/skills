#!/usr/bin/env node
/**
 * Download all Paul Graham essays and convert to Markdown.
 *
 * Usage:
 *   node download-essays.mjs              # download all essays
 *   node download-essays.mjs --force      # re-download even if file exists
 *   node download-essays.mjs --concurrency 3
 *   node download-essays.mjs --delay 500  # ms between batches
 */

import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";
import TurndownService from "turndown";
import * as cheerio from "cheerio";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ESSAYS_DIR = path.join(__dirname, "essays");

// ── CLI flags ────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const FORCE = args.includes("--force");
const CONCURRENCY = parseInt(args[args.indexOf("--concurrency") + 1]) || 5;
const DELAY = parseInt(args[args.indexOf("--delay") + 1]) || 300;

// ── Parse essay list from the index markdown ─────────────────────────
async function loadEssayList() {
  const md = await fs.readFile(path.join(__dirname, "paul-graham-essays.md"), "utf-8");
  const entries = [];
  for (const line of md.split("\n")) {
    const m = line.match(/^\d+\.\s+\[(.+?)]\((.+?)\)$/);
    if (m) {
      const [, title, url] = m;
      // derive a filename slug from the URL path
      const slug = url
        .replace(/https?:\/\/[^/]+\//, "")
        .replace(/\.html$/, "")
        .replace(/[^a-z0-9_-]/gi, "-");
      entries.push({ title, url, slug });
    }
  }
  return entries;
}

// ── Turndown instance ────────────────────────────────────────────────
function makeTurndown() {
  const td = new TurndownService({
    headingStyle: "atx",
    codeBlockStyle: "fenced",
    bulletListMarker: "-",
    emDelimiter: "*",
  });
  // strip images, scripts, styles, nav
  td.remove(["script", "style", "nav", "img"]);
  return td;
}

// ── Download and convert one essay ───────────────────────────────────
async function downloadEssay(entry, td) {
  const outFile = path.join(ESSAYS_DIR, `${entry.slug}.md`);

  if (!FORCE) {
    try {
      await fs.access(outFile);
      return { status: "skipped", entry };
    } catch {}
  }

  let html;
  try {
    const res = await fetch(entry.url, {
      headers: { "User-Agent": "PG-Essay-Downloader/1.0" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    html = await res.text();
  } catch (err) {
    return { status: "error", entry, error: err.message };
  }

  // Extract the essay body with cheerio
  const $ = cheerio.load(html);

  // PG's site uses a table layout; the essay text is usually in the
  // widest <td> or inside <font> tags within the main table cell.
  // We try several selectors to find the content.
  let contentHtml = "";

  // Strategy 1: grab the main content table cell (width 375 or 435)
  const candidates = $('td[width="375"], td[width="435"], td[width="500"]');
  if (candidates.length) {
    // take the one with the most text
    let best = null;
    let bestLen = 0;
    candidates.each((_, el) => {
      const text = $(el).text().trim();
      if (text.length > bestLen) {
        bestLen = text.length;
        best = el;
      }
    });
    if (best) contentHtml = $(best).html();
  }

  // Strategy 2: fallback to body
  if (!contentHtml || contentHtml.length < 200) {
    contentHtml = $("body").html() || html;
  }

  // Convert to markdown
  let markdown = td.turndown(contentHtml);

  // Prepend a title
  markdown = `# ${entry.title}\n\n${markdown}`;

  // Append source link
  markdown += `\n\n---\n*Source: [${entry.url}](${entry.url})*\n`;

  await fs.writeFile(outFile, markdown, "utf-8");
  return { status: "ok", entry };
}

// ── Batch runner with concurrency control ────────────────────────────
async function runBatch(entries, concurrency, delayMs) {
  const td = makeTurndown();
  const results = { ok: 0, skipped: 0, error: 0, errors: [] };

  for (let i = 0; i < entries.length; i += concurrency) {
    const batch = entries.slice(i, i + concurrency);
    const outcomes = await Promise.all(
      batch.map((e) => downloadEssay(e, td))
    );

    for (const o of outcomes) {
      results[o.status]++;
      if (o.status === "error") {
        results.errors.push(`  ✗ ${o.entry.title}: ${o.error}`);
        console.error(`  ✗ ${o.entry.title}: ${o.error}`);
      } else if (o.status === "ok") {
        process.stdout.write(`  ✓ ${o.entry.title}\n`);
      }
    }

    // throttle between batches
    if (i + concurrency < entries.length) {
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }

  return results;
}

// ── Main ─────────────────────────────────────────────────────────────
async function main() {
  await fs.mkdir(ESSAYS_DIR, { recursive: true });

  const essays = await loadEssayList();
  console.log(`\n📚 Found ${essays.length} essays in index`);
  console.log(`   Concurrency: ${CONCURRENCY}  Delay: ${DELAY}ms  Force: ${FORCE}\n`);

  const results = await runBatch(essays, CONCURRENCY, DELAY);

  console.log(`\n── Summary ──`);
  console.log(`  Downloaded: ${results.ok}`);
  console.log(`  Skipped:    ${results.skipped}`);
  console.log(`  Errors:     ${results.error}`);
  if (results.errors.length) {
    console.log(`\nFailed:\n${results.errors.join("\n")}`);
  }
  console.log();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
