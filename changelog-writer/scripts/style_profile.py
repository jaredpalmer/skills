#!/usr/bin/env python3
"""
style_profile.py — writing-style profiler and grader for changelog prose.

Two modes:

  profile  Compute a style profile (JSON) from one or more reference texts:
             python style_profile.py profile corpus/vercel/*.md corpus/cursor/*.md \
                 --out baseline_profile.json

  grade    Grade a candidate text against a baseline profile:
             python style_profile.py grade draft.md --baseline baseline_profile.json
           Prints a human-readable report and exits 0 if the draft matches the
           baseline within tolerance, 1 otherwise. Use --json for machine output.

The metrics focus on distributional stats — median and p95 — rather than means,
because prose style is about the *shape* of sentences (a few long ones among
mostly short ones reads very differently from uniformly medium ones).
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`([^`]*)`")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
HEADING_RE = re.compile(r"^#{1,6}\s.*$", re.MULTILINE)
META_RE = re.compile(r"^(Date|Source)\s*:.*$", re.MULTILINE | re.IGNORECASE)
MD_CHARS_RE = re.compile(r"[*_~#]")


def normalize(text: str) -> str:
    """Strip markdown/code so stats reflect prose, not syntax."""
    text = CODE_BLOCK_RE.sub(" ", text)
    # Headings and corpus metadata lines aren't prose sentences — drop them
    # entirely so they don't merge with adjacent sentences.
    text = HEADING_RE.sub("", text)
    text = META_RE.sub("", text)
    text = IMAGE_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(r"\1", text)
    text = LINK_RE.sub(r"\1", text)
    text = MD_CHARS_RE.sub("", text)
    # Treat double-hyphen as em-dash so both conventions count the same.
    text = text.replace("--", "—")
    return text


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-_.:/+]*")

# Split on sentence-final punctuation followed by whitespace/end. Common
# abbreviations and version numbers are shielded first.
ABBREVS = ["e.g.", "i.e.", "etc.", "vs.", "v.", "cf.", "approx.", "No."]
DECIMAL_RE = re.compile(r"(\d)\.(\d)")
VERSION_RE = re.compile(r"\b(v?\d+)\.(\d+)")


def split_sentences(text: str) -> list[str]:
    shielded = text
    for ab in ABBREVS:
        shielded = shielded.replace(ab, ab.replace(".", "\x00"))
    shielded = DECIMAL_RE.sub(lambda m: m.group(1) + "\x00" + m.group(2), shielded)
    shielded = VERSION_RE.sub(lambda m: m.group(1) + "\x00" + m.group(2), shielded)
    parts = re.split(r"(?<=[.!?])\s+|(?<=[.!?])$", shielded, flags=re.MULTILINE)
    return [p.replace("\x00", ".").strip() for p in parts if p.strip()]


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (p / 100)
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def dist(vals: list[float]) -> dict:
    s = sorted(vals)
    return {
        "median": round(percentile(s, 50), 2),
        "p95": round(percentile(s, 95), 2),
        "n": len(vals),
    }


# ---------------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------------

SECOND_PERSON_RE = re.compile(r"\b(you|your|yours|you're|you'll|you've)\b", re.I)
FIRST_PLURAL_RE = re.compile(r"\b(we|our|we're|we've|we'll|us)\b", re.I)


def compute_metrics(text: str) -> dict:
    clean = normalize(text)

    # Split into blocks on blank lines; within each block separate bullet items
    # from paragraph lines. Sentence stats use paragraph prose only — bullets
    # often lack terminal punctuation and would merge into fake mega-sentences.
    bullets: list[str] = []
    paragraphs: list[str] = []
    total_lines = 0
    for block in re.split(r"\n\s*\n", clean):
        plines = []
        for ln in block.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            total_lines += 1
            m = re.match(r"^[-*•]\s+(.*)", ln)
            if m:
                bullets.append(m.group(1))
            else:
                plines.append(ln)
        if plines:
            paragraphs.append(" ".join(plines))

    body = " ".join(paragraphs + bullets)   # for density metrics
    prose = " ".join(paragraphs)            # for sentence-shape metrics
    sents = split_sentences(prose)
    all_words = words(body)
    n_words = max(len(all_words), 1)
    per100 = lambda n: round(n / n_words * 100, 3)

    sent_word_counts = [len(words(s)) for s in sents]
    word_char_counts = [len(w) for w in all_words]
    para_sent_counts = [len(split_sentences(p)) for p in paragraphs] or [0]
    bullet_word_counts = [len(words(b)) for b in bullets]

    metrics = {
        "word_count": n_words,
        # --- sentence shape (median + p95, in words) ---
        "sentence_len": dist(sent_word_counts),
        "word_len": dist(word_char_counts),
        "paragraph_sentences": dist(para_sent_counts),
        # --- punctuation density (occurrences per 100 words) ---
        "comma_per100": per100(body.count(",")),
        "emdash_per100": per100(body.count("—")),
        # Hyphens here means hyphenated compounds ("content-addressed"), a real
        # signature of terse technical changelog prose — not en-dashes.
        "hyphen_per100": per100(len(re.findall(r"(?<!-)-(?!-)", clean.replace("—", "")))),
        "colon_per100": per100(len(re.findall(r":(?!//)", body))),
        "semicolon_per100": per100(body.count(";")),
        "paren_per100": per100(body.count("(") + body.count(")")),
        "exclaim_per100": per100(body.count("!")),
        "question_per100": per100(body.count("?")),
        # --- structural/verbal habits ---
        "fragment_pct": round(100 * sum(1 for c in sent_word_counts if c <= 4) / max(len(sents), 1), 1),
        "long_sent_pct": round(100 * sum(1 for c in sent_word_counts if c >= 25) / max(len(sents), 1), 1),
        "second_person_per100": per100(len(SECOND_PERSON_RE.findall(body))),
        "first_plural_per100": per100(len(FIRST_PLURAL_RE.findall(body))),
        "bullet_share": round(len(bullets) / max(total_lines, 1), 3),
    }
    if bullet_word_counts:
        metrics["bullet_len"] = dist(bullet_word_counts)
    return metrics


def profile_files(paths: list[Path]) -> dict:
    combined = "\n\n".join(p.read_text(encoding="utf-8") for p in paths)
    return compute_metrics(combined)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

# How close the candidate must be to the baseline to "match".
# rel = max allowed relative deviation; abs = max allowed absolute deviation
# (used when the baseline is near zero, e.g. semicolons). Whichever is looser wins.
TOLERANCES = {
    "sentence_len.median": {"rel": 0.25, "abs": 3.0},
    "sentence_len.p95": {"rel": 0.30, "abs": 6.0},
    "word_len.median": {"rel": 0.10, "abs": 0.4},
    "word_len.p95": {"rel": 0.15, "abs": 1.5},
    "paragraph_sentences.median": {"rel": 0.50, "abs": 1.0},
    "paragraph_sentences.p95": {"rel": 0.50, "abs": 2.0},
    "bullet_len.median": {"rel": 0.40, "abs": 5.0},
    "bullet_len.p95": {"rel": 0.40, "abs": 8.0},
    "comma_per100": {"rel": 0.35, "abs": 0.8},
    "emdash_per100": {"rel": 0.50, "abs": 0.3},
    "hyphen_per100": {"rel": 0.75, "abs": 0.3},
    "colon_per100": {"rel": 0.50, "abs": 0.4},
    "semicolon_per100": {"rel": 1.00, "abs": 0.2},
    "paren_per100": {"rel": 0.60, "abs": 0.4},
    "exclaim_per100": {"rel": 1.00, "abs": 0.2},
    "question_per100": {"rel": 1.00, "abs": 0.2},
    "fragment_pct": {"rel": 0.60, "abs": 6.0},
    "long_sent_pct": {"rel": 0.60, "abs": 5.0},
    "second_person_per100": {"rel": 0.60, "abs": 0.6},
    "first_plural_per100": {"rel": 0.60, "abs": 0.6},
    "bullet_share": {"rel": 0.60, "abs": 0.15},
}

DIST_KEYS = ("median", "p95")


def flatten(metrics: dict) -> dict[str, float]:
    flat = {}
    for k, v in metrics.items():
        if isinstance(v, dict) and "median" in v:
            for dk in DIST_KEYS:
                flat[f"{k}.{dk}"] = v[dk]
        elif isinstance(v, (int, float)):
            flat[k] = float(v)
    return flat


def grade(candidate_metrics: dict, baseline: dict) -> list[dict]:
    cand, base = flatten(candidate_metrics), flatten(baseline)
    n_words = max(candidate_metrics.get("word_count", 1), 1)
    results = []
    for name, tol in TOLERANCES.items():
        if name not in base or name not in cand:
            continue
        b, c = base[name], cand[name]
        allowed = max(abs(b) * tol["rel"], tol["abs"])
        # Per-100-word rates are quantized on short drafts: one occurrence of
        # anything shifts the rate by 100/n_words. Give density metrics slack
        # of ~1 occurrence so a 120-word draft isn't graded as if it were a
        # 6,000-word corpus.
        if name.endswith("_per100"):
            allowed = max(allowed, 1.25 * 100 / n_words)
        dev = abs(c - b)
        results.append({
            "metric": name,
            "baseline": b,
            "candidate": round(c, 3),
            "allowed_dev": round(allowed, 3),
            "passed": dev <= allowed,
        })
    return results


def print_report(results: list[dict], candidate_metrics: dict) -> None:
    passed = sum(r["passed"] for r in results)
    print(f"\n{'metric':<32}{'baseline':>10}{'candidate':>11}{'±allowed':>10}  verdict")
    print("-" * 72)
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"{r['metric']:<32}{r['baseline']:>10}{r['candidate']:>11}{r['allowed_dev']:>10}  {mark}")
    print("-" * 72)
    print(f"{passed}/{len(results)} metrics within tolerance "
          f"(candidate words: {candidate_metrics.get('word_count', '?')})")
    fails = [r["metric"] for r in results if not r["passed"]]
    if fails:
        print("\nFailing metrics — revise the draft to move these toward the baseline:")
        for f in fails:
            print(f"  - {f}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_prof = sub.add_parser("profile", help="Compute a style profile from reference texts")
    p_prof.add_argument("files", nargs="+", type=Path)
    p_prof.add_argument("--out", type=Path, help="Write profile JSON here (default: stdout)")

    p_grade = sub.add_parser("grade", help="Grade a candidate against a baseline profile")
    p_grade.add_argument("candidate", type=Path)
    p_grade.add_argument("--baseline", type=Path, required=True)
    p_grade.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    p_grade.add_argument("--allow-failures", type=int, default=0,
                         help="Pass even if up to N metrics fail (default 0)")

    args = ap.parse_args()

    if args.cmd == "profile":
        prof = profile_files(args.files)
        out = json.dumps(prof, indent=2)
        if args.out:
            args.out.write_text(out + "\n", encoding="utf-8")
            print(f"Wrote profile from {len(args.files)} file(s) to {args.out}", file=sys.stderr)
        else:
            print(out)
        return 0

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    cand_metrics = compute_metrics(args.candidate.read_text(encoding="utf-8"))
    results = grade(cand_metrics, baseline)
    n_fail = sum(1 for r in results if not r["passed"])
    ok = n_fail <= args.allow_failures

    if args.json:
        print(json.dumps({"passed": ok, "failures": n_fail, "results": results,
                          "candidate_metrics": cand_metrics}, indent=2))
    else:
        print_report(results, cand_metrics)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
