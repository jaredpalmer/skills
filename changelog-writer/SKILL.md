---
name: changelog-writer
description: Write product changelogs and release notes in the house style of Vercel and Cursor — punchy, technical, marketing-inflected — and iteratively refine drafts until their measured writing statistics (sentence length, punctuation density, em-dash usage, etc.) match the real Vercel/Cursor baseline. Use whenever the user asks for a changelog, release notes, "what's new" posts, launch announcements, or wants draft release prose to sound like Vercel or Cursor, even if they don't mention this skill explicitly.
---

# Changelog Writer

Write changelogs that read like they came from Vercel or Cursor, and prove it with numbers.

The point of this skill is not just to vibe-imitate those companies — it's to
*measure* the draft's prose style against a baseline profile computed from their
actual published changelogs, and loop until the measurements match. Intuition
about style is unreliable; the grader is not.

## What the style is (qualitative)

Read a few files in `references/corpus/` before writing — nothing teaches the
voice like the real thing. The entries are not distributed with the skill; if
the folder has only `MANIFEST.md`, read 2–3 entries from the source URLs it
lists instead. What the corpus shows:

- **"Now" is the temporal anchor.** Vercel titles are sentence case built on
  "X now Y" / "X is now available". Cursor versioned releases open with
  "This release introduces..." or "X is now available in Cursor."
- **Short declarative paragraphs.** Median paragraph is a single sentence; p95
  is three. Median sentence is ~16 words; ~13% of sentences run 25+ words —
  long sentences are seasoning, not the base.
- **Second person, present tense.** "You can now...", "Your deploys...". The
  reader is a developer and the feature already works. "We" is rare (~0.4 per
  100 words) — benefit follows mechanism, framed around the user.
- **Em-dashes are essentially absent** (~0.2 per 100 words). Colons and
  parentheses do the aside work instead. Don't reach for em-dashes.
- **No exclamation marks or questions. Ever.** The excitement is implied by
  the facts.
- **Bullets carry the details** (about a third of lines), often grammatically
  parallel fragments. Vercel favors bold lead-ins with colons
  ("**Approval by default:** ..."); Cursor's "Improvements"/"Bug Fixes" bullets
  start with past-tense verbs ("Added...", "Fixed...").
- **Lead with the outcome, not the effort.** "Builds are 40% faster," not
  "We're excited to announce that we've been working hard on..."
- **Specific numbers and names** beat adjectives. "2.3x faster cold starts" >
  "dramatically improved performance."
- **Close with a pointer, not a pitch.** "See the docs for the full setup."
  "Read more in the announcement."

## The workflow

### 1. Draft

Write the changelog entry. Get the substance right first: what's the feature,
who gets it, what changes for the user. Don't contort the draft to hit metrics
on the first pass — that's what the loop is for.

### 2. Grade

```bash
python3 scripts/style_profile.py grade <draft.md> \
    --baseline references/baseline_profile.json
```

The grader reports, per metric: baseline value, your draft's value, the allowed
deviation, and PASS/FAIL. It exits nonzero if any metric is out of tolerance.

### 3. Revise against the failing metrics

Each failing metric is a concrete editing instruction:

| Failing metric | What to do |
|---|---|
| `sentence_len.median` / `.p95` too high | Split compound sentences. Cut subordinate clauses. |
| `sentence_len.median` too low | Merge choppy fragments into flowing sentences. |
| `emdash_per100` too low/high | Add or remove em-dash asides — Vercel/Cursor use them sparingly. |
| `fragment_pct` too low | Add punchy 2–4 word sentences ("It's on by default."). |
| `long_sent_pct` too high | Find your 25+ word sentences and break them up. |
| `second_person_per100` off | Reframe around "you"/"your" (or pull back if overdone). |
| `bullet_share` off | Move detail into bullets, or prose-ify a bulleted list. |
| `colon_per100` off | Add/remove lead-in colons ("Now available:"). |

Prefer edits that improve the *writing*, not metric-gaming hacks (e.g., don't
sprinkle random em-dashes). If a metric won't move without hurting the prose,
use judgment — a great changelog that fails one metric beats a stilted one
that passes all.

### 4. Loop

Re-grade after each revision. Iterate until the grader passes, or until ~4
rounds have passed — then show the user the best draft along with the grader
report so they can make the final call. Don't silently loop forever.

## The grader

`scripts/style_profile.py` (stdlib-only Python) has two modes:

- `profile <files...> --out profile.json` — compute a style profile from
  reference texts. The baseline in `references/baseline_profile.json` was built
  this way from the corpus. Rebuild it if the corpus changes.
- `grade <draft.md> --baseline profile.json [--json]` — compare a draft to the
  baseline. Metrics use **median and p95** (not means), because prose style
  lives in the distribution: the occasional long sentence among short ones
  reads completely differently from uniformly medium sentences.

Metrics measured:

- **Shape**: sentence length (words), word length (chars), sentences per
  paragraph, bullet item length — each as median + p95.
- **Punctuation density** per 100 words: commas, em-dashes (both `—` and `--`
  count), hyphens in compounds, colons, semicolons, parentheses, `!`, `?`.
- **Habits**: % fragment sentences (≤4 words), % long sentences (≥25 words),
  second-person and first-plural pronoun rates, share of lines that are bullets.

Tolerances are per-metric (relative + absolute floor) in the `TOLERANCES` dict —
tighten or loosen there if the user wants stricter or looser matching. Density
metrics (`*_per100`) additionally get slack of roughly one occurrence, because
rates are quantized on short texts: a single parenthetical in a 120-word draft
moves the rate by ~0.8 per 100 words, and a real changelog entry is short.

`--allow-failures N` lets a draft pass with up to N out-of-tolerance metrics;
useful near the end of a loop when the last metric is a stylistic toss-up.

## Reference material

- `references/baseline_profile.json` — the style baseline (median/p95 stats).
- `references/corpus/` — real Vercel and Cursor changelog entries the baseline
  was computed from (local only; not in the published skill). Read 2–3 before
  drafting; imitate their rhythm, not their content.
- `references/corpus/MANIFEST.md` — source URL and date for every corpus file.
