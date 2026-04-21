#!/usr/bin/env node
/**
 * Normalize / polish downloaded PG essay markdown files.
 *
 * Performs:
 *  - Collapse excessive blank lines (max 2 consecutive)
 *  - Remove leftover HTML artifacts & entities
 *  - Normalize unicode quotes/dashes
 *  - Remove trailing whitespace
 *  - Ensure consistent heading hierarchy (single H1)
 *  - Strip stray navigation / footer text
 *  - Ensure file ends with a single newline
 *
 * Usage:
 *   node normalize-essays.mjs                  # normalize all
 *   node normalize-essays.mjs essays/foo.md    # normalize one file
 *   node normalize-essays.mjs --dry-run        # preview without writing
 */

import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ESSAYS_DIR = path.join(__dirname, "essays");

const args = process.argv.slice(2);
const DRY_RUN = args.includes("--dry-run");
const specificFiles = args.filter((a) => !a.startsWith("--"));

// ── Normalization passes ─────────────────────────────────────────────
function normalize(text) {
  let s = text;

  // Decode common HTML entities
  s = s
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&mdash;/g, "—")
    .replace(/&ndash;/g, "–")
    .replace(/&hellip;/g, "…")
    .replace(/&rsquo;/g, "'")
    .replace(/&lsquo;/g, "'")
    .replace(/&rdquo;/g, "\u201D")
    .replace(/&ldquo;/g, "\u201C")
    .replace(/&#\d+;/g, ""); // strip remaining numeric entities

  // Remove leftover HTML tags that turndown missed
  s = s.replace(/<\/?(?:font|br|img|td|tr|table|map|area|div|span)[^>]*>/gi, "");

  // Strip PG site navigation remnants
  s = s.replace(
    /\[?(Home|Articles|Books|Arc|Bel|Lisp|Spam|FAQ|RAQ|Quotes?|RSS|Bio|Twitter)\]?\s*\n?/g,
    ""
  );

  // Collapse multiple blank lines to max 2
  s = s.replace(/\n{4,}/g, "\n\n\n");

  // Remove trailing whitespace per line
  s = s.replace(/[ \t]+$/gm, "");

  // Normalize curly quotes to straight (optional — comment out to keep curly)
  // s = s.replace(/[\u2018\u2019]/g, "'");
  // s = s.replace(/[\u201C\u201D]/g, '"');

  // Ensure single H1 — if multiple H1s exist, demote extras to H2
  const h1Matches = s.match(/^# .+$/gm);
  if (h1Matches && h1Matches.length > 1) {
    let firstSeen = false;
    s = s.replace(/^# (.+)$/gm, (match, title) => {
      if (!firstSeen) {
        firstSeen = true;
        return match; // keep first H1
      }
      return `## ${title}`;
    });
  }

  // Remove lines that are just bullet-point images/icons (PG uses gif bullets)
  s = s.replace(/^!\[.*?\]\(.*?trans_1x1\.gif.*?\)\s*$/gm, "");
  s = s.replace(/^!\[.*?\]\(.*?the-reddits.*?\)\s*$/gm, "");

  // Collapse again after removals
  s = s.replace(/\n{4,}/g, "\n\n\n");

  // Ensure ends with single newline
  s = s.trimEnd() + "\n";

  return s;
}

// ── Main ─────────────────────────────────────────────────────────────
async function main() {
  let files;

  if (specificFiles.length) {
    files = specificFiles.map((f) => path.resolve(f));
  } else {
    const entries = await fs.readdir(ESSAYS_DIR);
    files = entries
      .filter((f) => f.endsWith(".md"))
      .map((f) => path.join(ESSAYS_DIR, f));
  }

  console.log(`\n🔧 Normalizing ${files.length} file(s)${DRY_RUN ? " (dry run)" : ""}\n`);

  let changed = 0;
  for (const file of files) {
    const original = await fs.readFile(file, "utf-8");
    const normalized = normalize(original);

    if (normalized !== original) {
      changed++;
      const name = path.basename(file);
      if (DRY_RUN) {
        console.log(`  would change: ${name}`);
      } else {
        await fs.writeFile(file, normalized, "utf-8");
        console.log(`  ✓ ${name}`);
      }
    }
  }

  console.log(`\n── Done: ${changed}/${files.length} files ${DRY_RUN ? "would be " : ""}modified ──\n`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
