#!/usr/bin/env python3
"""
Build references/pg_profile.json from a directory of real PG essays.

The profile holds only aggregate statistics (quantiles, word frequencies, a
vocabulary list), never essay text, so it can be committed even though the
corpus itself shouldn't be.

Usage:
    node samples/download-essays.mjs && node samples/normalize-essays.mjs
    python3 scripts/build_profile.py                       # samples/essays -> references/pg_profile.json
    python3 scripts/build_profile.py --corpus DIR -o OUT.json
"""

import argparse
import glob
import json
import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pg_style as S  # noqa: E402

SIZES = [300, 600, 1200, 2400]
RECENT_YEAR = 2015
N_FUNCTION_WORDS = 120
MIN_DF = 3

EXTRA_FUNCTION = set("""really actually probably often usually never always something anything everything nothing
anyone someone everyone kind lot still though although even ever whether rather quite pretty enough else
another every either neither since till unless yet may might must shall seems seem already almost""".split())


def load_corpus(corpus_dir: str) -> list:
    essays = []
    for path in sorted(glob.glob(os.path.join(corpus_dir, "*.md"))):
        with open(path) as fh:
            doc = S.clean_essay(fh.read())
        wc = sum(len(S.words_of(p)) for p in doc["paragraphs"])
        # Skip very short pieces and scraped book chapters that arrive as one giant blob.
        if wc < 250 or wc / max(1, len(doc["paragraphs"])) > 400:
            continue
        doc["name"] = os.path.basename(path)
        doc["wc"] = wc
        essays.append(doc)
    return essays


def chunk(paragraphs: list, size: int) -> list:
    chunks, cur, n = [], [], 0
    for p in paragraphs:
        cur.append(p)
        n += len(S.words_of(p))
        if n >= size:
            chunks.append(cur)
            cur, n = [], 0
    if cur:
        if chunks and n < 0.7 * size:
            chunks[-1] = chunks[-1] + cur
        elif n >= 0.7 * size:
            chunks.append(cur)
    return chunks


def essay_vocab(doc) -> set:
    sents = [s for p in doc["paragraphs"] for s in S.split_sentences(p)]
    return set(S._vocab_tokens(sents))


def build(essays: list) -> dict:
    # Pass 1: corpus-wide counts
    df = Counter()
    wordcount = Counter()
    total_words = 0
    lowers = []
    for d in essays:
        v = essay_vocab(d)
        d["_vocab"] = v
        df.update(v)
        ws = [w.lower() for p in d["paragraphs"] for w in S.words_of(p)]
        wordcount.update(ws)
        total_words += len(ws)
        lowers.append("\n\n".join(d["paragraphs"]).lower())

    function_set = S.STOP | EXTRA_FUNCTION
    fws = [w for w, _ in wordcount.most_common() if w in function_set][:N_FUNCTION_WORDS]
    vocab = sorted(w for w, c in df.items() if c >= MIN_DF)
    big = "\n\n".join(lowers)
    tell_rates = {t: S.count_phrase(big, t) * 1000.0 / total_words for t in S.TELL_CANDIDATES}

    chunks = {s: [] for s in SIZES}
    for d in essays:
        for s in SIZES:
            for c in chunk(d["paragraphs"], s):
                chunks[s].append((d, c))

    fw_stats = {}
    for s in SIZES:
        rows = [S.fw_freqs([w for p in c for w in S.words_of(p)], fws) for _, c in chunks[s]]
        cols = list(zip(*rows))
        fw_stats[str(s)] = {"mean": [statistics.mean(c) for c in cols],
                            "sd": [statistics.stdev(c) for c in cols]}

    base = {"function_words": fws, "fw_stats": fw_stats, "tell_rates_per_1k": tell_rates}

    # Pass 2: per-chunk features, with a leave-one-out vocabulary so an essay's
    # own rare words don't count as "PG vocabulary" when scoring that essay.
    vocab_set = set(vocab)
    feats = {s: [] for s in SIZES}
    for s in SIZES:
        for d, c in chunks[s]:
            own_rare = {w for w in d["_vocab"] if df[w] == MIN_DF}
            prof = dict(base, vocab=vocab_set - own_rare)
            f = S.extract(c, headers=0, bullets=0, profile=prof)
            if "error" in f:
                continue
            f.pop("_evidence")
            f["_year"] = d["year"]
            f["delta"], _ = S.burrows_delta([w for p in c for w in S.words_of(p)], fws, fw_stats, str(s))
            # Headers and bullets are per-essay properties; every chunk inherits its essay's rate.
            f["headers_per_1k"] = d["headers"] / d["wc"] * 1000
            f["bullets_per_1k"] = d["bullets"] / d["wc"] * 1000
            feats[s].append(f)

    eras = {}
    for era, keep in (("all", lambda y: True), ("recent", lambda y: (y or 0) >= RECENT_YEAR)):
        eras[era] = {}
        for s in SIZES:
            rows = [f for f in feats[s] if keep(f["_year"])]
            if len(rows) < 20:
                continue
            q = {k: S.quantiles([r[k] for r in rows]) for k in S.METRICS if k in rows[0]}
            scores = []
            for r in rows:
                num = den = 0.0
                for k, (_, side, w, _, _) in S.METRICS.items():
                    if k in q:
                        num += w * S.grade(r[k], q[k], side)[1]
                        den += w
                scores.append(max(0.0, 100 * num / den))
            eras[era][str(s)] = {"n": len(rows), "quantiles": q, "score_quantiles": S.quantiles(scores)}

    return {
        "built_from_essays": len(essays),
        "recent_year": RECENT_YEAR,
        "sizes": SIZES,
        "function_words": fws,
        "fw_stats": fw_stats,
        "tell_rates_per_1k": {k: round(v, 5) for k, v in tell_rates.items()},
        "vocab": vocab,
        "eras": eras,
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default=os.path.join(here, "..", "samples", "essays"))
    ap.add_argument("-o", "--out", default=S.DEFAULT_PROFILE)
    args = ap.parse_args()
    essays = load_corpus(args.corpus)
    if not essays:
        sys.exit(f"No essays found in {args.corpus}. Run samples/download-essays.mjs first.")
    prof = build(essays)
    with open(args.out, "w") as fh:
        json.dump(prof, fh, separators=(",", ":"))
    print(f"Built profile from {len(essays)} essays -> {os.path.relpath(args.out)}")
    for era, buckets in prof["eras"].items():
        for s, b in buckets.items():
            sq = b["score_quantiles"]
            print(f"  {era:6s} {s:>5}w  chunks={b['n']:4d}  PG self-score p10={sq['10']:.0f} p50={sq['50']:.0f}")


if __name__ == "__main__":
    main()
