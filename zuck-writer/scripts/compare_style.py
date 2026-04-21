#!/usr/bin/env python3
"""
Compare generated text against the Zuckerberg style baseline.

Takes generated text (file or stdin) and the baseline JSON, computes
per-metric deviation scores, and outputs a pass/fail style fidelity report.

Usage:
    # Compare a file against baseline
    python compare_style.py generated.txt --baseline baseline.json

    # Pipe in text
    echo "..." | python compare_style.py --baseline baseline.json

    # JSON output for programmatic use
    python compare_style.py generated.txt --baseline baseline.json --json

    # Generate baseline first if needed
    python generate_baseline.py -o baseline.json
    python compare_style.py generated.txt --baseline baseline.json
"""

import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from style_analyzer import analyze, format_report


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASELINE = os.path.join(SCRIPT_DIR, '..', 'references', 'baseline.json')


def score_metric(value: float, guardrail: dict) -> dict:
    """Score a single metric against its guardrail.

    Returns:
        {
            'status': 'pass' | 'warn' | 'fail',
            'value': float,
            'deviation': float (how far outside the range, 0 if in range),
            'message': str
        }
    """
    if guardrail is None:
        return {'status': 'skip', 'value': value, 'deviation': 0, 'message': 'Not guardrailed'}

    # Hard ceiling (semicolons, exclamations, em dashes)
    if 'max' in guardrail and 'low' not in guardrail:
        ceiling = guardrail['max']
        if value <= ceiling:
            return {'status': 'pass', 'value': value, 'deviation': 0,
                    'message': f'{value} <= {ceiling}'}
        else:
            return {'status': 'fail', 'value': value, 'deviation': value - ceiling,
                    'message': f'{value} exceeds ceiling of {ceiling}'}

    # Range guardrail
    lo, hi = guardrail['low'], guardrail['high']
    if lo <= value <= hi:
        return {'status': 'pass', 'value': value, 'deviation': 0,
                'message': f'{value} in [{lo}, {hi}]'}

    # How far outside?
    if value < lo:
        deviation = lo - value
        pct = (deviation / (hi - lo)) * 100 if (hi - lo) else 0
        severity = 'warn' if pct < 50 else 'fail'
        return {'status': severity, 'value': value, 'deviation': -deviation,
                'message': f'{value} below range [{lo}, {hi}] by {deviation:.1f}'}
    else:
        deviation = value - hi
        pct = (deviation / (hi - lo)) * 100 if (hi - lo) else 0
        severity = 'warn' if pct < 50 else 'fail'
        return {'status': severity, 'value': value, 'deviation': deviation,
                'message': f'{value} above range [{lo}, {hi}] by {deviation:.1f}'}


def compare(text: str, baseline: dict) -> dict:
    """Compare text metrics against baseline. Returns full comparison report."""
    metrics = asdict(analyze(text))
    baseline_metrics = baseline['metrics']

    results = {}
    pass_count = 0
    warn_count = 0
    fail_count = 0
    skip_count = 0

    for key, value in metrics.items():
        if key not in baseline_metrics:
            continue

        bl = baseline_metrics[key]
        guardrail = bl.get('guardrail')
        result = score_metric(value, guardrail)
        result['baseline_mean'] = bl['mean']
        result['baseline_stdev'] = bl['stdev']
        if guardrail:
            result['guardrail'] = guardrail

        results[key] = result

        if result['status'] == 'pass':
            pass_count += 1
        elif result['status'] == 'warn':
            warn_count += 1
        elif result['status'] == 'fail':
            fail_count += 1
        else:
            skip_count += 1

    scored = pass_count + warn_count + fail_count
    score = round((pass_count / scored) * 100, 1) if scored else 0

    return {
        'score': score,
        'summary': {
            'pass': pass_count,
            'warn': warn_count,
            'fail': fail_count,
            'skip': skip_count,
            'total_scored': scored,
        },
        'results': results,
    }


def format_comparison(report: dict) -> str:
    """Format comparison report as human-readable text."""
    lines = []
    lines.append(f"STYLE FIDELITY SCORE: {report['score']}%")
    s = report['summary']
    lines.append(f"  Pass: {s['pass']}  |  Warn: {s['warn']}  |  Fail: {s['fail']}  |  Skipped: {s['skip']}")
    lines.append("")

    # Group by status for readability
    categories = {
        'Sentence': ['avg_sentence_words', 'max_sentence_words', 'min_sentence_words',
                      'sentence_words_stdev', 'avg_word_length'],
        'Paragraph': ['avg_paragraph_sentences', 'avg_paragraph_words'],
        'Punctuation': ['commas_per_sentence', 'parentheses_per_1k', 'double_hyphens_per_1k',
                         'semicolons', 'exclamations', 'em_dashes'],
        'Voice': ['i_we_ratio', 'hedges_per_1k', 'contractions_per_1k',
                   'passive_per_1k', 'adverbs_per_1k'],
        'Reasoning': ['questions_per_1k', 'if_conditionals_per_1k', 'numbers_per_1k'],
    }

    STATUS_ICONS = {'pass': '\u2705', 'warn': '\u26a0\ufe0f ', 'fail': '\u274c', 'skip': '\u23ed\ufe0f '}

    for cat_name, keys in categories.items():
        lines.append(f"  {cat_name}")
        for key in keys:
            if key not in report['results']:
                continue
            r = report['results'][key]
            icon = STATUS_ICONS.get(r['status'], '?')
            lines.append(f"    {icon} {key:<28} {r['message']}")
        lines.append("")

    # Highlight issues
    issues = [(k, v) for k, v in report['results'].items()
              if v['status'] in ('warn', 'fail')]
    if issues:
        lines.append("ISSUES TO ADDRESS:")
        for key, r in issues:
            icon = STATUS_ICONS[r['status']]
            lines.append(f"  {icon} {key}: {r['message']}")

    return '\n'.join(lines)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Compare text against Zuckerberg style baseline')
    parser.add_argument('input', nargs='?', help='Input text file (reads stdin if omitted)')
    parser.add_argument('--baseline', '-b', default=DEFAULT_BASELINE,
                        help='Path to baseline.json')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--score-only', action='store_true', help='Print only the score (0-100)')
    args = parser.parse_args()

    # Load baseline
    if not os.path.exists(args.baseline):
        print(f"Error: baseline file not found at {args.baseline}", file=sys.stderr)
        print("Run: python generate_baseline.py -o baseline.json", file=sys.stderr)
        sys.exit(1)

    with open(args.baseline) as f:
        baseline = json.load(f)

    # Load input text
    if args.input:
        with open(args.input) as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    report = compare(text, baseline)

    if args.score_only:
        print(report['score'])
    elif args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_comparison(report))
