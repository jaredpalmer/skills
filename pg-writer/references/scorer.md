# The PG style scorer

`scripts/analyze_essay.py` compares a draft against measurements of Paul Graham's own essays and quotes the sentences behind each flag. It's stdlib Python with no dependencies.

## How it works

- **Cleaning.** Titles, date lines, images, headers, blockquotes (other people's words), code, footnote markers, endnotes, and "Thanks to" lines are removed before measuring. Both PG's essays and your draft go through the same cleaning, so the comparison is fair.
- **Length-matched comparison.** PG's essays are cut into chunks of about 300, 600, 1200, and 2400 words, and the draft is compared against the chunk size closest to its length. This matters because a 400-word piece naturally varies much more than a 4000-word one. Judging short drafts against full-essay ranges, as the old scorer did, flagged real PG as off-voice.
- **Grading.** Each metric is placed on PG's distribution. `ok` means inside p10-p90. `edge` means p5-p10 or p90-p95. `warn` means p1-p5 or p95-p99. `fail` means beyond that. Some metrics are one-sided: nobody is penalized for using *fewer* em dashes than PG.
- **Score.** This is a weighted average of per-metric credit (ok 1, edge 0.8, warn 0.3, fail -0.5), scaled to 100. Fails cost more than a missing point because in cross-validation that separated fluent non-PG prose from real PG better, with no increase in false alarms. The report shows where held-out PG essays land, so you can tell whether a score is normal.

## Metrics

| Group | Metric | What it catches |
|---|---|---|
| tells | Em dashes /1k | The best-known generated-text tell. PG's median is about 0.8/1k. |
| tells | "Not X. It's Y." reframes /1k | Negation-then-reframe in several forms, including one-sentence pivots, "not because... but because", and "less about... more about". |
| tells | Modern-LLM tell phrases /1k | Phrases from a candidate list that PG almost never uses, *as measured in the corpus*. Candidates he does use (like "genuinely" or "leverage") only count when a draft uses them far more often than he does. |
| tells | Paragraphs ending on a zinger | A paragraph of 3+ sentences whose last sentence is 7 words or fewer and under half the length of the others. |
| tells | Staccato runs | Three or more consecutive sentences of 6 words or fewer. |
| tells | Formal transitions | moreover, furthermore, additionally, thus, hence, etc. |
| voice | Burrows' Delta | Standard authorship stylometry: mean absolute z-score over PG's 120 most common function words, winsorized at 3 sd. The report names the words furthest off. |
| voice | Words PG rarely uses | Share of tokens (proper nouns excluded) outside the words that appear in at least 3 of his essays. Computed leave-one-out during calibration. |
| voice | Word length, 10+ letter words, contractions, hedges, I, you, MATTR | Register and diction. MATTR is a length-independent measure of vocabulary variety. |
| rhythm | Sentence length mean/median/sd, short and long share, paragraph length, one-sentence paragraphs, conjunction starts, questions | Cadence. |
| punctuation | Semicolons, colons, parentheses, exclamations | Register. |
| structure | Most similar paragraph pair | Cosine similarity of content words, to catch two paragraphs doing the same job. |
| structure | Repeated content trigrams, headers, bullets | Circling, and memo-style formatting. |

The report also adds notes (these aren't scored) when an opener narrates the essay ("Here's something...") or a closer summarizes it ("In the end...").

## Validation (as of the last rebuild)

5-fold cross-validation, where each essay is scored against a profile built without it:

- Held-out PG essays: p5 = 76, p10 = 82, median = 92. 1.8% score below 70.
- Six non-PG fixtures in `evals/fixtures/not-pg/` (corporate blog, academic, thread-style, an old-model PG imitation, a literary essay, and a polished modern-LLM essay) score 23 to 73. AUC for PG vs. these is 0.99.
- The hardest negative is the polished modern-LLM essay, at about 73. It avoids every classic tell and gets caught on register instead: no contractions, long words, semicolons, and no "you". Expect good generated prose to land in the 70s, so don't read a score in the high 70s as proof of PG's voice.

## Rebuilding

The corpus isn't committed (it's PG's copyrighted text). To regenerate it and recalibrate:

```
cd samples && npm install && node download-essays.mjs && node normalize-essays.mjs && cd ..
python3 scripts/build_profile.py                   # writes references/pg_profile.json
python3 scripts/validate_scorer.py --negatives evals/fixtures/not-pg --update-profile
```

`pg_profile.json` contains only aggregate statistics: quantiles, function-word frequencies, a vocabulary list, and phrase rates. No essay text is stored in it.

When you change a metric in `scripts/pg_style.py`, run all three steps and check that held-out PG essays don't start failing it more than a few percent of the time. A metric that fires on PG himself is measuring topic, not voice.
