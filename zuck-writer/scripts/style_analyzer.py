#!/usr/bin/env python3
"""
Style analyzer for Zuckerberg voice writing.

Extracts quantitative writing metrics from text input.
Used standalone or as a module by baseline and comparison scripts.

Usage:
    # Analyze a file
    python style_analyzer.py input.txt

    # Analyze from stdin
    echo "Some text" | python style_analyzer.py

    # Output as JSON
    python style_analyzer.py input.txt --json

    # Analyze only quoted ("> ") lines from a markdown file (for reference samples)
    python style_analyzer.py references/style-samples.md --extract-samples
"""

import re
import json
import sys
import statistics
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class StyleMetrics:
    # Scale
    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0

    # Sentence-level
    avg_sentence_words: float = 0.0
    max_sentence_words: int = 0
    min_sentence_words: int = 0
    sentence_words_stdev: float = 0.0

    # Paragraph-level
    avg_paragraph_sentences: float = 0.0
    avg_paragraph_words: float = 0.0

    # Word-level
    avg_word_length: float = 0.0

    # Punctuation (rates per 1000 words unless noted)
    commas_per_sentence: float = 0.0
    parentheses_per_1k: float = 0.0
    double_hyphens_per_1k: float = 0.0
    semicolons: int = 0
    exclamations: int = 0
    em_dashes: int = 0

    # Voice
    i_we_ratio: float = 0.0  # I / (I + we), 0 = all "we", 1 = all "I"
    hedges_per_1k: float = 0.0
    contractions_per_1k: float = 0.0
    passive_per_1k: float = 0.0
    adverbs_per_1k: float = 0.0

    # Reasoning patterns
    questions_per_1k: float = 0.0
    if_conditionals_per_1k: float = 0.0
    numbers_per_1k: float = 0.0


def split_sentences(text: str) -> list[str]:
    """Split text into sentences. Handles abbreviations and decimal numbers."""
    text = re.sub(r'\s+', ' ', text).strip()
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z"\'])', text)
    return [s.strip() for s in parts if len(s.strip()) > 3]


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on blank lines."""
    paras = re.split(r'\n\s*\n', text)
    return [p.strip() for p in paras if p.strip()]


def count_pattern(text: str, pattern: str, flags: int = 0) -> int:
    return len(re.findall(pattern, text, flags))


def per_1k(count: int, word_count: int) -> float:
    if word_count == 0:
        return 0.0
    return round((count / word_count) * 1000, 1)


def analyze(text: str) -> StyleMetrics:
    """Analyze text and return StyleMetrics."""
    m = StyleMetrics()

    paragraphs = split_paragraphs(text)
    sentences = split_sentences(text)
    words = text.split()

    m.word_count = len(words)
    m.sentence_count = len(sentences)
    m.paragraph_count = len(paragraphs)

    if not words:
        return m

    # Word lengths
    clean_words = [re.sub(r'[^a-zA-Z]', '', w) for w in words]
    clean_words = [w for w in clean_words if w]
    m.avg_word_length = round(statistics.mean(len(w) for w in clean_words), 1) if clean_words else 0

    # Sentence lengths
    if sentences:
        sent_word_counts = [len(s.split()) for s in sentences]
        m.avg_sentence_words = round(statistics.mean(sent_word_counts), 1)
        m.max_sentence_words = max(sent_word_counts)
        m.min_sentence_words = min(sent_word_counts)
        m.sentence_words_stdev = round(statistics.stdev(sent_word_counts), 1) if len(sent_word_counts) > 1 else 0

    # Paragraph metrics
    if paragraphs:
        para_sent_counts = []
        para_word_counts = []
        for p in paragraphs:
            p_sents = split_sentences(p)
            para_sent_counts.append(len(p_sents) if p_sents else 1)
            para_word_counts.append(len(p.split()))
        m.avg_paragraph_sentences = round(statistics.mean(para_sent_counts), 1)
        m.avg_paragraph_words = round(statistics.mean(para_word_counts), 1)

    # Punctuation
    comma_count = text.count(',')
    m.commas_per_sentence = round(comma_count / len(sentences), 1) if sentences else 0
    m.parentheses_per_1k = per_1k(text.count('('), m.word_count)
    m.double_hyphens_per_1k = per_1k(count_pattern(text, r' -- '), m.word_count)
    m.semicolons = text.count(';')
    m.exclamations = text.count('!')
    m.em_dashes = count_pattern(text, r'—')

    # Voice: I vs We
    i_count = count_pattern(text, r'\bI\b')
    we_count = count_pattern(text, r'\b[Ww]e\b')
    m.i_we_ratio = round(i_count / (i_count + we_count), 2) if (i_count + we_count) else 0

    # Hedging markers
    hedge_count = count_pattern(
        text,
        r'\bI think\b|\bI believe\b|\bI worry\b|\bI wonder\b|'
        r'\bMy (?:theory|sense|guess|instinct|intuition)\b|'
        r"\bI'm not confident\b|\bI'm not sure\b",
        re.I
    )
    m.hedges_per_1k = per_1k(hedge_count, m.word_count)

    # Contractions
    contraction_count = count_pattern(text, r"\b\w+'(?:t|s|re|ve|ll|d|m)\b")
    m.contractions_per_1k = per_1k(contraction_count, m.word_count)

    # Passive voice (rough heuristic)
    passive_count = count_pattern(text, r'\b(?:is|are|was|were|be|been|being)\s+\w+ed\b', re.I)
    m.passive_per_1k = per_1k(passive_count, m.word_count)

    # Adverbs (-ly words, excluding common false positives)
    ly_exclusions = {'only', 'early', 'likely', 'family', 'daily', 'weekly', 'rally',
                     'apply', 'supply', 'reply', 'july', 'holy', 'ugly', 'rely',
                     'fly', 'multiply', 'italy', 'ally'}
    ly_words = re.findall(r'\b\w+ly\b', text, re.I)
    ly_words = [w for w in ly_words if w.lower() not in ly_exclusions]
    m.adverbs_per_1k = per_1k(len(ly_words), m.word_count)

    # Reasoning
    m.questions_per_1k = per_1k(text.count('?'), m.word_count)
    m.if_conditionals_per_1k = per_1k(count_pattern(text, r'\bIf\b'), m.word_count)
    m.numbers_per_1k = per_1k(count_pattern(text, r'\b\d[\d,.%]*\b'), m.word_count)

    return m


def extract_samples(filepath: str) -> list[tuple[str, str]]:
    """Extract individual writing samples from the reference markdown file.
    Returns list of (title, text) tuples."""
    with open(filepath) as f:
        raw = f.read()

    sample_blocks = re.split(r'## Sample \d+:', raw)[1:]
    samples = []

    for block in sample_blocks:
        title_match = re.match(r'([^\n]+)', block.strip())
        title = title_match.group(1).strip() if title_match else "Unknown"

        quoted_lines = []
        for line in block.split('\n'):
            line = line.strip()
            if line.startswith('> '):
                quoted_lines.append(line[2:])
            elif line == '>':
                quoted_lines.append('')

        text = '\n'.join(quoted_lines).strip()
        if text:
            samples.append((title, text))

    return samples


def format_report(metrics: StyleMetrics, title: str = "Text") -> str:
    """Format metrics as a human-readable report."""
    lines = [
        f"=== Style Analysis: {title} ===",
        "",
        "SCALE",
        f"  Words: {metrics.word_count}  |  Sentences: {metrics.sentence_count}  |  Paragraphs: {metrics.paragraph_count}",
        "",
        "SENTENCE STRUCTURE",
        f"  Avg words/sentence: {metrics.avg_sentence_words}  (stdev: {metrics.sentence_words_stdev})",
        f"  Range: {metrics.min_sentence_words} - {metrics.max_sentence_words} words",
        f"  Avg word length: {metrics.avg_word_length} chars",
        "",
        "PARAGRAPH STRUCTURE",
        f"  Avg sentences/paragraph: {metrics.avg_paragraph_sentences}",
        f"  Avg words/paragraph: {metrics.avg_paragraph_words}",
        "",
        "PUNCTUATION",
        f"  Commas/sentence: {metrics.commas_per_sentence}",
        f"  Parentheses per 1k words: {metrics.parentheses_per_1k}",
        f"  Double hyphens (--) per 1k words: {metrics.double_hyphens_per_1k}",
        f"  Semicolons: {metrics.semicolons}",
        f"  Exclamation marks: {metrics.exclamations}",
        f"  Em dashes (\u2014): {metrics.em_dashes}",
        "",
        "VOICE",
        f"  I/We ratio: {metrics.i_we_ratio}  (0=all 'we', 1=all 'I')",
        f"  Hedges per 1k words: {metrics.hedges_per_1k}",
        f"  Contractions per 1k words: {metrics.contractions_per_1k}",
        f"  Passive voice per 1k words: {metrics.passive_per_1k}",
        f"  Adverbs (-ly) per 1k words: {metrics.adverbs_per_1k}",
        "",
        "REASONING PATTERNS",
        f"  Questions per 1k words: {metrics.questions_per_1k}",
        f"  'If' conditionals per 1k words: {metrics.if_conditionals_per_1k}",
        f"  Numbers/data per 1k words: {metrics.numbers_per_1k}",
    ]
    return '\n'.join(lines)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Analyze writing style metrics')
    parser.add_argument('input', nargs='?', help='Input file (reads stdin if omitted)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--extract-samples', action='store_true',
                        help='Extract and analyze individual samples from reference markdown')
    args = parser.parse_args()

    if args.extract_samples:
        if not args.input:
            print("Error: --extract-samples requires an input file", file=sys.stderr)
            sys.exit(1)
        samples = extract_samples(args.input)
        results = []
        for title, text in samples:
            m = analyze(text)
            if args.json:
                results.append({'title': title, 'metrics': asdict(m)})
            else:
                print(format_report(m, title))
                print()
        if args.json:
            print(json.dumps(results, indent=2))
    else:
        if args.input:
            with open(args.input) as f:
                text = f.read()
        else:
            text = sys.stdin.read()

        m = analyze(text)
        if args.json:
            print(json.dumps(asdict(m), indent=2))
        else:
            print(format_report(m))
