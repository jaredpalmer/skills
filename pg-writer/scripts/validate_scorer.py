#!/usr/bin/env python3
"""
Check the scorer against held-out PG essays (false alarms) and, optionally,
against a directory of non-PG text (misses).

Usage:
    python3 scripts/validate_scorer.py                        # 5-fold CV on samples/essays
    python3 scripts/validate_scorer.py --negatives DIR        # also score non-PG drafts, report AUC
    python3 scripts/validate_scorer.py --chunk 600            # score held-out 600-word excerpts instead of whole essays

Run this after changing any metric in pg_style.py, then rebuild the profile.
"""

import argparse
import glob
import json
import os
import random
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_profile as B  # noqa: E402
import pg_style as S  # noqa: E402


def as_md(paragraphs):
    return "\n\n".join(paragraphs)


def auc(pos, neg):
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default=os.path.join(here, "..", "samples", "essays"))
    ap.add_argument("--negatives", help="directory of .md files NOT written by PG")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--chunk", type=int, default=0, help="score held-out excerpts of ~N words")
    ap.add_argument("--update-profile", action="store_true",
                    help="write held-out score quantiles into references/pg_profile.json so reports "
                         "compare drafts against honest (not in-sample) PG scores")
    args = ap.parse_args()

    essays = B.load_corpus(args.corpus)
    random.Random(0).shuffle(essays)
    folds = [essays[i::args.folds] for i in range(args.folds)]
    scores, fails, statuses = [], Counter(), Counter()
    last_profile = None
    for i, test in enumerate(folds):
        train = [e for j, f in enumerate(folds) if j != i for e in f]
        prof = B.build(train)
        last_profile = prof
        for d in test:
            pieces = B.chunk(d["paragraphs"], args.chunk)[:2] if args.chunk else [d["paragraphs"]]
            for p in pieces:
                r = S.score(as_md(p), prof)
                if "error" in r:
                    continue
                scores.append(r["score"])
                for k, m in r["metrics"].items():
                    statuses[m["status"]] += 1
                    if m["status"] == "fail":
                        fails[k] += 1
        print(f"  fold {i + 1}/{args.folds} done", file=sys.stderr)

    n = len(scores)
    q = S.quantiles(scores)
    print(f"\nHeld-out PG ({n} {'excerpts' if args.chunk else 'essays'}):")
    print(f"  score p5={q['5']:.0f} p10={q['10']:.0f} p25={q['25']:.0f} median={q['50']:.0f}")
    print(f"  share below 80: {100 * sum(s < 80 for s in scores) / n:.1f}%   below 70: {100 * sum(s < 70 for s in scores) / n:.1f}%")
    total = sum(statuses.values())
    print(f"  metric statuses: " + ", ".join(f"{k} {100 * v / total:.1f}%" for k, v in statuses.most_common()))
    print("  metrics that FAIL on real PG most often (per document):")
    for k, v in fails.most_common(8):
        print(f"    {k:<24} {100 * v / n:5.1f}%")

    if args.update_profile:
        prof = S.load_profile()
        prof["cv_score_quantiles"] = {k: round(v, 1) for k, v in q.items()}
        with open(S.DEFAULT_PROFILE, "w") as fh:
            json.dump(prof, fh, separators=(",", ":"))
        print(f"\n  wrote cv_score_quantiles to {os.path.relpath(S.DEFAULT_PROFILE)}")

    if args.negatives:
        neg = []
        for f in sorted(glob.glob(os.path.join(args.negatives, "*.md"))):
            r = S.score(open(f).read(), last_profile)
            if "error" not in r:
                neg.append((r["score"], os.path.basename(f)))
        if neg:
            print(f"\nNegatives ({len(neg)}):")
            for s, name in sorted(neg):
                print(f"  {s:5.1f}  {name}")
            print(f"  AUC (PG vs negatives): {auc(scores, [s for s, _ in neg]):.3f}")
            print(f"  median negative score: {statistics.median(s for s, _ in neg):.0f}")


if __name__ == "__main__":
    main()
