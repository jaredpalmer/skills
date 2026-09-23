#!/usr/bin/env python3
"""
Score a draft against Paul Graham's measured habits and point at the sentences to fix.

Usage:
    python3 scripts/analyze_essay.py essay.md               # report
    python3 scripts/analyze_essay.py essay.md --era recent  # compare to 2015+ essays only
    python3 scripts/analyze_essay.py a.md b.md              # several drafts, side-by-side scores
    python3 scripts/analyze_essay.py drafts/                # every .md in a directory
    python3 scripts/analyze_essay.py - < essay.md           # stdin
    python3 scripts/analyze_essay.py essay.md --json        # machine-readable
    python3 scripts/analyze_essay.py essay.md --all         # show every metric, not just problems

How to read it: each metric is placed on PG's own distribution, measured on
chunks of his essays that are about as long as your draft. "ok" means inside
his p10-p90 band; "fail" means beyond all but his rarest 1%. The score is a
weighted share of metrics in band, and fails cost extra. Held-out PG essays
mostly land 80-100 (the report prints the exact band). The score is a smoke
alarm, not a target: it catches slop, but it can't tell you whether the essay
has an idea worth reading.
"""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pg_style as S  # noqa: E402

ORDER = {"fail": 0, "warn": 1, "edge": 2, "ok": 3}
MARK = {"fail": "FAIL", "warn": "warn", "edge": "edge", "ok": " ok "}
GROUPS = ["tells", "voice", "rhythm", "punctuation", "structure"]


def verdict(score: float, sq: dict) -> str:
    if sq and score >= sq["25"]:
        return "reads like PG on the measurable axes"
    if sq and score >= sq["5"]:
        return "within PG's range, a few habits drifting"
    if score >= 60:
        return "noticeably off-voice in places"
    return "reads as generated or as someone else's voice"


def fmt(v: float) -> str:
    return f"{v:.2f}" if abs(v) < 10 else f"{v:.1f}"


def print_report(r: dict, name: str, show_all: bool):
    if "error" in r:
        print(f"\n{name}: {r['error']}")
        return
    sq = r["pg_score_quantiles"] or {}
    print("\n" + "=" * 78)
    print(f"  {name}  |  {r['word_count']} words  |  vs PG {r['era']} essays, {r['bucket_words']}-word chunks (n={r['bucket_chunks']})")
    band = f"  (real PG: p10 {sq['10']:.0f}, median {sq['50']:.0f})" if sq else ""
    print(f"  SCORE {r['score']:.0f}/100{band}")
    print(f"  {verdict(r['score'], sq)}")
    print("=" * 78)

    problems = sorted((m for m in r["metrics"].values() if m["status"] in ("fail", "warn")),
                      key=lambda m: (ORDER[m["status"]], m["group"]))
    if problems:
        print("\n  WHAT TO FIX")
        for m in problems:
            print(f"\n  [{MARK[m['status']]}] {m['label']}: {fmt(m['value'])}  "
                  f"(PG p10-p90: {fmt(m['pg_p10'])}-{fmt(m['pg_p90'])}, you're at p{m['percentile']:.0f})")
            if m["hint"]:
                print(f"         {m['hint']}")
            for e in m["evidence"][:4]:
                print(f"         > {e[:150]}")
    else:
        print("\n  Nothing outside PG's p1-p99 range.")

    for n in r["notes"]:
        print(f"\n  [note] {n}")

    edges = [m for m in r["metrics"].values() if m["status"] == "edge"]
    if edges and not show_all:
        print("\n  Near the edge (p90-p95 or p5-p10, usually fine): " +
              ", ".join(f"{m['label']} {fmt(m['value'])}" for m in edges))

    if show_all:
        for g in GROUPS:
            rows = [m for m in r["metrics"].values() if m["group"] == g]
            if not rows:
                continue
            print(f"\n  {g.upper()}")
            for m in rows:
                print(f"   {MARK[m['status']]}  {m['label']:<42} {fmt(m['value']):>7}   "
                      f"PG {fmt(m['pg_p10'])}-{fmt(m['pg_p90'])} (med {fmt(m['pg_p50'])})")
        d = r["metrics"].get("delta")
        if d and d["evidence"]:
            print("\n  Function words furthest from PG's habits: " + "; ".join(d["evidence"]))
    print()


def collect(paths):
    out = []
    for p in paths:
        if p == "-":
            out.append(("stdin", sys.stdin.read()))
        elif os.path.isdir(p):
            for f in sorted(glob.glob(os.path.join(p, "*.md"))):
                out.append((f, open(f).read()))
        else:
            out.append((p, open(p).read()))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--era", choices=["all", "recent"], default="all",
                    help="'recent' compares against essays from 2015 on (shorter, plainer)")
    ap.add_argument("--profile", default=None, help="path to pg_profile.json")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="print every metric")
    args = ap.parse_args()

    profile = S.load_profile(args.profile)
    docs = collect(args.paths)
    results = [(name, S.score(text, profile, args.era)) for name, text in docs]

    if args.json:
        print(json.dumps(results[0][1] if len(results) == 1 else dict(results), indent=2))
        return
    for name, r in results:
        print_report(r, os.path.basename(name), args.all)
    if len(results) > 1:
        print("  SUMMARY")
        for name, r in results:
            if "error" in r:
                continue
            fails = sum(1 for m in r["metrics"].values() if m["status"] == "fail")
            print(f"   {r['score']:5.1f}  {fails} fail  {r['word_count']:5d}w  {os.path.basename(name)}")
        print()


if __name__ == "__main__":
    main()
