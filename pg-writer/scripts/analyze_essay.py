#!/usr/bin/env python3
"""
Analyze an essay against Paul Graham's writing statistics.

Usage:
    python3 analyze_essay.py <essay.md>                    # analyze a single essay
    python3 analyze_essay.py <essay.md> --json             # output as JSON
    python3 analyze_essay.py <essay.md> --pg-corpus <dir>  # compare against PG corpus
    python3 analyze_essay.py <dir_of_essays>               # analyze all .md files in dir

PG reference ranges are baked in from analysis of 230 real PG essays.
"""

import argparse
import glob
import json
import os
import re
import statistics
import sys

# Reference ranges from 230 real PG essays: (median, p10, p90)
PG_RANGES = {
    "em_dashes_per_1k":          (0.67,  0.00,  2.48),
    "contrast_pattern_per_1k":   (0.00,  0.00,  0.45),
    "contractions_per_1k":       (28.93, 18.51, 39.89),
    "qualifications_per_1k":     (3.39,  1.25,  7.22),
    "avg_sent_len":              (16.53, 14.11, 18.58),
    "med_sent_len":              (15.00, 12.50, 17.00),
    "avg_para_len":              (54.00, 37.50, 67.79),
    "sent_len_stddev":           (9.34,  7.59,  11.38),
    "short_sent_pct":            (19.90, 14.18, 30.34),
    "long_sent_pct":             (9.08,  3.75,  15.35),
    "questions_per_1k":          (3.24,  0.65,  5.94),
    "conj_starts_per_1k":        (8.14,  4.51,  12.35),
    "avg_word_len":              (4.37,  4.18,  4.61),
    "formal_transitions_per_1k": (0.00,  0.00,  0.79),
    "one_sent_para_pct":         (9.65,  3.53,  22.22),
    "parentheticals_per_1k":     (1.20,  0.00,  3.66),
    "semicolons_per_1k":         (1.25,  0.00,  3.13),
    "exclamations_per_1k":       (0.00,  0.00,  0.35),
    "first_person_per_1k":       (10.52, 2.58,  25.56),
    "you_per_1k":                (20.61, 6.59,  45.25),
    "passive_per_1k":            (1.78,  0.00,  4.55),
}

# Labels for human-readable output
LABELS = {
    "em_dashes_per_1k":          "Em dashes / 1000w",
    "contrast_pattern_per_1k":   "\"Not X. It's Y.\" / 1000w",
    "contractions_per_1k":       "Contractions / 1000w",
    "qualifications_per_1k":     "Qualifications / 1000w",
    "avg_sent_len":              "Avg sentence length",
    "med_sent_len":              "Median sentence length",
    "avg_para_len":              "Avg paragraph length",
    "sent_len_stddev":           "Sentence length variety (σ)",
    "short_sent_pct":            "Short sentences ≤8w (%)",
    "long_sent_pct":             "Long sentences ≥30w (%)",
    "questions_per_1k":          "Questions / 1000w",
    "conj_starts_per_1k":        "Conj. starts (And/But/So) / 1000w",
    "avg_word_len":              "Avg word length (chars)",
    "formal_transitions_per_1k": "Formal transitions / 1000w",
    "one_sent_para_pct":         "One-sentence paragraphs (%)",
    "parentheticals_per_1k":     "Parenthetical asides / 1000w",
    "semicolons_per_1k":         "Semicolons / 1000w",
    "exclamations_per_1k":       "Exclamations / 1000w",
    "first_person_per_1k":       "First person (I/me/my) / 1000w",
    "you_per_1k":                "You/your / 1000w",
    "passive_per_1k":            "Passive voice / 1000w",
}

# Priority tiers for display
TIER_CRITICAL = ["em_dashes_per_1k", "contrast_pattern_per_1k"]
TIER_HIGH = [
    "questions_per_1k", "conj_starts_per_1k", "short_sent_pct",
    "sent_len_stddev", "avg_word_len", "contractions_per_1k",
]
TIER_MODERATE = [
    "qualifications_per_1k", "avg_sent_len", "med_sent_len", "avg_para_len",
    "formal_transitions_per_1k", "one_sent_para_pct", "long_sent_pct",
    "parentheticals_per_1k", "semicolons_per_1k",
]
TIER_REFERENCE = [
    "exclamations_per_1k", "first_person_per_1k", "you_per_1k", "passive_per_1k",
]


def clean_text(text: str) -> str:
    """Strip markdown formatting for analysis."""
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    return text


def analyze_essay(text: str) -> dict:
    """Compute all writing statistics for a single essay."""
    raw = text
    clean = clean_text(text)
    words = clean.split()
    wc = len(words)

    if wc < 20:
        return {"word_count": wc, "error": "Too short to analyze"}

    # Sentences
    sentences = re.split(r'(?<=[.!?])\s+', clean)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip().split()) >= 2]
    sent_lengths = [len(s.split()) for s in sentences]
    if not sent_lengths:
        sent_lengths = [wc]

    # Paragraphs
    paragraphs = [p.strip() for p in clean.split('\n\n') if p.strip() and len(p.strip().split()) >= 3]
    para_lengths = [len(p.split()) for p in paragraphs]
    if not para_lengths:
        para_lengths = [wc]

    # Word-level
    alpha_words = re.findall(r'\b[a-zA-Z]+\b', clean)

    # Contrast pattern: "isn't/doesn't/not just X. It's/That's/This is Y."
    contrast_pattern = re.compile(
        r"(?:It(?:'s| is) not |(?:isn't|aren't|doesn't|don't|wasn't|won't) (?:just |merely |really |simply )?)"
        r"[^.!?\n]{3,50}\."
        r"\s+"
        r"(?:It(?:'s| is) |They(?:'re| are) |That(?:'s| is) |This (?:is )|What )"
        r"[^.!?\n]{3,80}\.",
        re.IGNORECASE
    )

    stats = {
        "word_count": wc,
        "em_dashes_per_1k": raw.count('—') / wc * 1000,
        "contrast_pattern_per_1k": len(contrast_pattern.findall(clean)) / wc * 1000,
        "contractions_per_1k": len(re.findall(r"\b\w+'\w+\b", clean)) / wc * 1000,
        "qualifications_per_1k": len(re.findall(
            r'\b(?:I think|I suspect|probably|perhaps|it seems|I believe|I\'m not sure|maybe|might be|could be)\b',
            clean, re.I
        )) / wc * 1000,
        "avg_sent_len": statistics.mean(sent_lengths),
        "med_sent_len": statistics.median(sent_lengths),
        "avg_para_len": statistics.mean(para_lengths),
        "sent_len_stddev": statistics.stdev(sent_lengths) if len(sent_lengths) > 1 else 0,
        "short_sent_pct": sum(1 for s in sent_lengths if s <= 8) / len(sent_lengths) * 100,
        "long_sent_pct": sum(1 for s in sent_lengths if s >= 30) / len(sent_lengths) * 100,
        "questions_per_1k": clean.count('?') / wc * 1000,
        "conj_starts_per_1k": len(re.findall(r'(?:^|\.\s+)(?:And|But|So|Or|Yet)\s', clean)) / wc * 1000,
        "avg_word_len": statistics.mean([len(w) for w in alpha_words]) if alpha_words else 0,
        "formal_transitions_per_1k": len(re.findall(
            r'\b(?:moreover|furthermore|nevertheless|additionally|consequently|subsequently|henceforth|notwithstanding)\b',
            clean, re.I
        )) / wc * 1000,
        "one_sent_para_pct": (
            sum(1 for p in paragraphs if len(re.split(r'[.!?]+', p.strip())) <= 2 and len(p.split()) < 25)
            / len(paragraphs) * 100
        ) if paragraphs else 0,
        "parentheticals_per_1k": len(re.findall(r'\([^)]{10,}\)', clean)) / wc * 1000,
        "semicolons_per_1k": clean.count(';') / wc * 1000,
        "exclamations_per_1k": clean.count('!') / wc * 1000,
        "first_person_per_1k": len(re.findall(r"\b(?:I|me|my|myself|I'd|I'll|I've|I'm)\b", clean)) / wc * 1000,
        "you_per_1k": len(re.findall(r"\b(?:you|your|yourself|you're|you'll|you've|you'd)\b", clean, re.I)) / wc * 1000,
        "passive_per_1k": len(re.findall(r'\b(?:was|were|been|being|is|are)\s+\w+ed\b', clean, re.I)) / wc * 1000,
    }

    return {k: round(v, 2) if isinstance(v, float) else v for k, v in stats.items()}


def grade_metric(key: str, value: float) -> str:
    """Grade a metric against PG ranges. Returns: ✅, ⚠️ HIGH, ⚠️ LOW, or 🔴."""
    if key not in PG_RANGES:
        return ""
    med, p10, p90 = PG_RANGES[key]

    # Critical metrics use stricter thresholds
    if key in TIER_CRITICAL:
        if key == "em_dashes_per_1k" and value > 2.5:
            return "🔴 FAIL"
        if key == "contrast_pattern_per_1k" and value > 0.5:
            return "🔴 FAIL"
        if value <= p90:
            return "✅"
        return "⚠️  HIGH"

    if value < p10:
        return "⚠️  LOW"
    elif value > p90:
        return "⚠️  HIGH"
    return "✅"


def print_report(stats: dict, filename: str = "essay"):
    """Print a formatted report card."""
    wc = stats.get("word_count", 0)
    print(f"\n{'=' * 72}")
    print(f"  PG STYLE ANALYSIS: {filename}  ({wc} words)")
    print(f"{'=' * 72}")

    fails = []
    warnings = []

    def print_tier(title, keys):
        nonlocal fails, warnings
        print(f"\n  {title}")
        print(f"  {'─' * 68}")
        for key in keys:
            if key not in stats:
                continue
            val = stats[key]
            label = LABELS.get(key, key)
            med, p10, p90 = PG_RANGES.get(key, (0, 0, 0))
            grade = grade_metric(key, val)
            print(f"  {label:<38} {val:>7.1f}   (PG: {p10:.1f}–{p90:.1f})  {grade}")
            if "FAIL" in grade:
                fails.append((label, val, p10, p90))
            elif "⚠️" in grade:
                warnings.append((label, val, p10, p90))

    print_tier("🚨 CRITICAL (AI slop detectors)", TIER_CRITICAL)
    print_tier("📊 HIGH VALUE (strong PG signals)", TIER_HIGH)
    print_tier("📏 MODERATE (useful guardrails)", TIER_MODERATE)
    print_tier("📎 REFERENCE (wide ranges)", TIER_REFERENCE)

    # Summary
    total = len([k for k in PG_RANGES if k in stats])
    ok = total - len(fails) - len(warnings)
    print(f"\n  {'─' * 68}")
    print(f"  SCORE: {ok}/{total} in range", end="")
    if fails:
        print(f"  |  {len(fails)} FAIL", end="")
    if warnings:
        print(f"  |  {len(warnings)} warnings", end="")
    print()

    if fails:
        print(f"\n  🔴 FAILURES:")
        for label, val, p10, p90 in fails:
            print(f"     {label}: {val:.1f} (should be {p10:.1f}–{p90:.1f})")

    if warnings:
        print(f"\n  ⚠️  WARNINGS:")
        for label, val, p10, p90 in warnings:
            print(f"     {label}: {val:.1f} (PG range: {p10:.1f}–{p90:.1f})")

    print()


def analyze_corpus(corpus_dir: str) -> dict:
    """Analyze a directory of essays and return per-metric statistics."""
    files = sorted(glob.glob(os.path.join(corpus_dir, "*.md")))
    all_stats = []
    for f in files:
        with open(f) as fh:
            text = fh.read()
        s = analyze_essay(text)
        if "error" not in s:
            all_stats.append(s)

    if not all_stats:
        return {}

    metrics = [k for k in all_stats[0] if k != "word_count" and k != "error"]
    result = {}
    for m in metrics:
        vals = sorted([s[m] for s in all_stats])
        result[m] = {
            "median": round(statistics.median(vals), 2),
            "p10": round(vals[int(len(vals) * 0.1)], 2),
            "p90": round(vals[int(len(vals) * 0.9)], 2),
            "min": round(min(vals), 2),
            "max": round(max(vals), 2),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description="Analyze essay against PG writing statistics")
    parser.add_argument("path", help="Path to essay .md file or directory of essays")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--pg-corpus", help="Path to PG essays directory (to recompute reference ranges)")
    parser.add_argument("--compare", nargs="+", help="Additional essays to compare side-by-side")
    args = parser.parse_args()

    # Recompute reference ranges from corpus if provided
    if args.pg_corpus:
        corpus_stats = analyze_corpus(args.pg_corpus)
        for key, vals in corpus_stats.items():
            if key in PG_RANGES:
                PG_RANGES[key] = (vals["median"], vals["p10"], vals["p90"])

    # Directory mode: analyze all .md files
    if os.path.isdir(args.path):
        files = sorted(glob.glob(os.path.join(args.path, "*.md")))
        all_results = {}
        for f in files:
            with open(f) as fh:
                text = fh.read()
            stats = analyze_essay(text)
            name = os.path.basename(f)
            all_results[name] = stats
            if not args.json:
                print_report(stats, name)

        if args.json:
            print(json.dumps(all_results, indent=2))
        return

    # Single file mode
    with open(args.path) as f:
        text = f.read()

    stats = analyze_essay(text)

    if args.json:
        result = {"file": args.path, "stats": stats, "grades": {}}
        for key in PG_RANGES:
            if key in stats:
                result["grades"][key] = grade_metric(key, stats[key])
        print(json.dumps(result, indent=2))
    else:
        print_report(stats, os.path.basename(args.path))

    # Compare mode
    if args.compare:
        for comp_path in args.compare:
            with open(comp_path) as f:
                comp_text = f.read()
            comp_stats = analyze_essay(comp_text)
            if args.json:
                print(json.dumps({"file": comp_path, "stats": comp_stats}, indent=2))
            else:
                print_report(comp_stats, os.path.basename(comp_path))


if __name__ == "__main__":
    main()
