#!/usr/bin/env python3
"""
Generate baseline statistics from Zuckerberg reference samples.

Reads the reference style-samples.md, analyzes each sample, and produces
a baseline JSON file with per-metric ranges (mean, stdev, min, max, guardrails).

Usage:
    python generate_baseline.py                          # prints to stdout
    python generate_baseline.py -o baseline.json         # writes to file
    python generate_baseline.py --samples ../references/style-samples.md  # custom path
"""

import json
import os
import sys
import statistics
from dataclasses import asdict

# Allow importing from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from style_analyzer import analyze, extract_samples, StyleMetrics


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SAMPLES = os.path.join(SCRIPT_DIR, '..', 'references', 'style-samples.md')

# Metrics where lower = strictly better (hard ceilings, not ranges)
HARD_CEILING_METRICS = {'semicolons', 'exclamations', 'em_dashes'}

# Metrics that are scale-dependent and shouldn't be guardrailed
SCALE_METRICS = {'word_count', 'sentence_count', 'paragraph_count'}


def compute_baseline(samples_path: str) -> dict:
    """Analyze all reference samples and compute aggregate statistics."""
    samples = extract_samples(samples_path)
    if not samples:
        print(f"Error: no samples found in {samples_path}", file=sys.stderr)
        sys.exit(1)

    all_metrics = [asdict(analyze(text)) for _, text in samples]
    metric_keys = list(all_metrics[0].keys())

    baseline = {
        'sample_count': len(samples),
        'sample_titles': [t for t, _ in samples],
        'metrics': {}
    }

    for key in metric_keys:
        vals = [m[key] for m in all_metrics]
        mean = statistics.mean(vals)
        stdev = statistics.stdev(vals) if len(vals) > 1 else 0

        entry = {
            'mean': round(mean, 2),
            'stdev': round(stdev, 2),
            'min': round(min(vals), 2),
            'max': round(max(vals), 2),
            'values': [round(v, 2) for v in vals],
        }

        if key in SCALE_METRICS:
            entry['guardrail'] = None
            entry['note'] = 'Scale metric — varies by format, not guardrailed'
        elif key in HARD_CEILING_METRICS:
            entry['guardrail'] = {'max': round(max(vals), 1)}
            entry['note'] = f'Hard ceiling — Zuckerberg almost never uses these (max observed: {max(vals)})'
        else:
            lo = round(max(0, mean - stdev), 1)
            hi = round(mean + stdev, 1)
            entry['guardrail'] = {'low': lo, 'high': hi}

        baseline['metrics'][key] = entry

    return baseline


def print_summary(baseline: dict):
    """Print a human-readable summary of the baseline."""
    print(f"Baseline from {baseline['sample_count']} Zuckerberg samples")
    print("=" * 70)

    categories = {
        'Scale': ['word_count', 'sentence_count', 'paragraph_count'],
        'Sentence': ['avg_sentence_words', 'max_sentence_words', 'min_sentence_words',
                      'sentence_words_stdev', 'avg_word_length'],
        'Paragraph': ['avg_paragraph_sentences', 'avg_paragraph_words'],
        'Punctuation': ['commas_per_sentence', 'parentheses_per_1k', 'double_hyphens_per_1k',
                         'semicolons', 'exclamations', 'em_dashes'],
        'Voice': ['i_we_ratio', 'hedges_per_1k', 'contractions_per_1k',
                   'passive_per_1k', 'adverbs_per_1k'],
        'Reasoning': ['questions_per_1k', 'if_conditionals_per_1k', 'numbers_per_1k'],
    }

    for cat_name, keys in categories.items():
        print(f"\n  {cat_name}")
        print(f"  {'Metric':<28} {'Mean':>8} {'StDev':>8} {'Guardrail':>20}")
        print(f"  {'-'*28} {'-'*8} {'-'*8} {'-'*20}")
        for key in keys:
            m = baseline['metrics'][key]
            guardrail = m.get('guardrail')
            if guardrail is None:
                g_str = '(not guardrailed)'
            elif 'max' in guardrail and 'low' not in guardrail:
                g_str = f"max {guardrail['max']}"
            else:
                g_str = f"{guardrail['low']} - {guardrail['high']}"
            print(f"  {key:<28} {m['mean']:>8.1f} {m['stdev']:>8.1f} {g_str:>20}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Generate style baseline from reference samples')
    parser.add_argument('--samples', default=DEFAULT_SAMPLES,
                        help='Path to style-samples.md')
    parser.add_argument('-o', '--output', help='Output JSON file path')
    parser.add_argument('--summary', action='store_true', help='Print human-readable summary')
    args = parser.parse_args()

    baseline = compute_baseline(args.samples)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(baseline, f, indent=2)
        print(f"Baseline written to {args.output}")

    if args.summary or not args.output:
        print_summary(baseline)

    if args.output:
        print_summary(baseline)
