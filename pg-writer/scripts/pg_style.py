"""
Feature extraction and scoring for Paul Graham-style prose.

Everything here is stdlib-only. The reference numbers live in
references/pg_profile.json, which build_profile.py derives from the real
essay corpus. Nothing in this module hardcodes PG's statistics.

The key design choice: a text is compared against PG *chunks of similar
length*, not against whole essays. Rates like "questions per 1000 words"
swing much more in a 400-word piece than in a 4000-word one, so judging a
short draft against full-essay ranges produces false alarms.
"""

import json
import math
import os
import re
import statistics
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROFILE = os.path.join(HERE, "..", "references", "pg_profile.json")

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_RE = re.compile(rf"^\s*(?:{MONTHS})\s+((?:19|20)\d\d)\s*(?:,.*)?$")

# ---------------------------------------------------------------------------
# Cleaning: turn a markdown essay into body paragraphs of the author's prose.
# ---------------------------------------------------------------------------


def _strip_inline(s: str) -> str:
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\\?\[\\?\[?\d+\\?\]?(?:\([^)]*\))?\\?\]", "", s)  # footnote refs [1], \[[1](#f1n)\]
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"\\([\[\]\*_()#.\-!])", r"\1", s)
    s = re.sub(r"(\*\*|__)(.+?)\1", r"\2", s)
    s = re.sub(r"(?<![\w*])[*_](?!\s)(.+?)(?<!\s)[*_](?![\w*])", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\u00a0", " ")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return text


def clean_essay(text: str) -> dict:
    """Extract the prose body. Returns paragraphs plus structural counts."""
    text = normalize(text)
    fm = re.match(r"^---\n(.*?)\n---\s*\n", text, flags=re.S)
    fm_title = None
    if fm:  # YAML frontmatter from blog engines: keep the title, drop the rest
        t = re.search(r"^title:\s*['\"]?(.+?)['\"]?\s*$", fm.group(1), flags=re.M)
        fm_title = t.group(1) if t else None
        text = text[fm.end():]
    text = re.split(r"\n-{3,}\s*\n\*Source:", text)[0]
    text = re.sub(r"```.*?```", "\n", text, flags=re.S)

    year = None
    title = None
    paragraphs, headers, bullets, bold_inline = [], 0, 0, 0
    buf = []

    def flush():
        if buf:
            paragraphs.append(" ".join(buf).strip())
            buf.clear()

    for raw in text.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if re.match(r"^(?:\*\*|#+\s*)?Notes?(?:\*\*)?:?\s*$", stripped):
            break  # endnotes are a different register; stop here
        if not stripped:
            flush()
            continue
        if stripped.startswith("!["):
            continue
        m = DATE_RE.match(stripped)
        if m and year is None and sum(len(p.split()) for p in paragraphs + buf) < 60:
            year = int(m.group(1))
            flush()
            paragraphs.clear()  # anything above the date line is an epigraph or site chrome
            continue
        if re.match(r"^#{1,6}\s", stripped):
            flush()
            if title is None and stripped.startswith("# ") and not paragraphs:
                title = stripped[2:].strip()
            else:
                headers += 1
            continue
        if re.match(r"^\*\*[^*]{1,60}\*\*$", stripped):
            flush()
            headers += 1
            continue
        if stripped.startswith(">") or re.match(r"^( {4,}|\t)", line):
            flush()
            continue  # quotations and code aren't the author's prose
        if re.match(r"^(?:[-*+]|\d+[.)])\s+", stripped):
            flush()
            bullets += 1
            buf.append(re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", stripped))
            flush()
            continue
        bold_inline += len(re.findall(r"\*\*[^*]+\*\*", stripped))
        buf.append(stripped)
    flush()

    out = []
    for p in paragraphs:
        if re.match(r"^\**Thanks\**\s", p) or re.match(r"^\(?Thanks to ", p):
            continue
        p = _strip_inline(p).strip()
        if len(p.split()) >= 1:
            out.append(p)
    # Drop a leading editorial preamble like "(This essay is derived from a talk...)"
    if out and out[0].startswith("(") and out[0].endswith(")") and re.search(r"\b(essay|talk|article)\b", out[0][:80]):
        out = out[1:]
    return {"title": title or fm_title, "year": year, "paragraphs": out, "headers": headers,
            "bullets": bullets, "bold_inline": bold_inline}


# ---------------------------------------------------------------------------
# Tokenizing
# ---------------------------------------------------------------------------

ABBREV = ["e.g.", "i.e.", "etc.", "vs.", "Mr.", "Mrs.", "Ms.", "Dr.", "St.", "Jr.", "Sr.",
          "Inc.", "Co.", "Corp.", "cf.", "a.m.", "p.m.", "U.S.", "U.K.", "No.", "approx.", "Ph.D."]
WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")


def split_sentences(par: str) -> list:
    s = par
    for i, a in enumerate(ABBREV):
        s = s.replace(a, a.replace(".", "\u0001"))
    s = re.sub(r"\b([A-Z])\.(?=\s[A-Z])", "\\1\u0001", s)   # initials: J. Doe
    s = re.sub(r"(\d)\.(\d)", "\\1\u0001\\2", s)
    parts = re.split(r'(?<=[.!?])["\')\]]*\s+(?=["\'(\[]?[A-Z0-9])', s)
    out = []
    for p in parts:
        p = p.replace("\u0001", ".").strip()
        if WORD_RE.search(p):
            out.append(p)
    return out


def words_of(s: str) -> list:
    return WORD_RE.findall(s)


CONTRACTION_RE = re.compile(
    r"\b(?:\w+n't|\w+'(?:re|ve|ll|d|m)|(?:it|that|there|here|what|who|he|she|let|where|how|"
    r"everyone|nobody|someone|something|everything|nothing|one|this|which|why|when)'s)\b", re.I)

QUALIFIER_RE = re.compile(
    r"\b(?:I think|I suspect|I'd guess|I guess|I believe|I'm not sure|I don't know|probably|perhaps|"
    r"maybe|presumably|it seems|seems|seemed|apparently|I imagine|as far as I can tell|I bet)\b", re.I)

CONJ_START_RE = re.compile(r'^["\'(]?(?:And|But|So|Or|Yet|Which|Because)\b')

FORMAL_TRANSITIONS = ["moreover", "furthermore", "additionally", "consequently", "nevertheless",
                      "nonetheless", "henceforth", "notwithstanding", "thus", "hence", "therefore",
                      "subsequently", "accordingly"]

# Negation-then-reframe ("It's not X. It's Y."), the most common modern LLM cadence.
ANTITHESIS_RES = [
    # Two sentences: "X isn't (just) Y. It's Z."
    re.compile(r"\b(?:it's not|it is not|this is not|that's not|that is not|this isn't|that isn't|"
               r"(?:is|are|was|were|does|do|did)n't|(?:is|are|was|were) not)\s+(?:just |merely |really |simply |only |about )?"
               r"[^.!?\n]{1,70}[.!?]\s+[\"']?(?:It's|It is|It was|They're|They are|That's|That is|This is|"
               r"It's about|The (?:real|actual) )", re.I),
    # One sentence with a pivot: "isn't about X; it's about Y" / "not X, it's Y"
    re.compile(r"\b(?:is|are|was|were|does|do)n't (?:just |merely |really |about |simply )?[^.;:!?\n]{1,60}"
               r"(?:;|,|:|\u2014| -- )\s*(?:it's|it is|they're|that's|it was)\b", re.I),
    # "It's not that X. It's that Y." / "Not because X, but because Y"
    re.compile(r"\bit(?:'s| is) not that\b[^.!?\n]{1,90}[.!?]\s+It(?:'s| is) that\b", re.I),
    re.compile(r"\bnot because\b[^.!?\n]{1,80}\bbut because\b", re.I),
    # "less about X and more about Y"
    re.compile(r"\bless about\b[^.!?\n]{1,60}\bmore about\b", re.I),
    # Fragment answer: "Not X. Y." at sentence start with a short fragment
    re.compile(r"(?:^|[.!?]\s+)Not (?:a |an |the |just |because |about )[^.!?\n]{1,40}\.\s+(?:A |An |The |It's |Just )", re.M),
]

META_OPENER_RE = re.compile(
    r"^(?:Here's (?:something|the thing|a thing|what)|I've been thinking|Let me (?:tell|explain|start)|"
    r"In today's|In an era|In a world|Throughout history|Have you ever|Imagine a world|"
    r"We live in|It's no secret|There's a (?:common|popular) (?:belief|saying|idea))", re.I)

SUMMARY_CLOSER_RE = re.compile(
    r"\b(?:In (?:summary|conclusion|short|the end)|To (?:sum up|recap|summarize)|The lesson (?:here )?is|"
    r"The takeaway|So the (?:real )?lesson|At the end of the day|Ultimately,|The bottom line)\b", re.I)

# Candidate modern-LLM tells. Whether each counts as a tell is decided by the
# profile (how often PG himself uses it), not by this list.
TELL_CANDIDATES = [
    "delve", "delves", "tapestry", "pivotal", "nuanced", "nuance", "realm", "underscore", "underscores",
    "navigate", "navigating", "intricate", "profoundly", "seamless", "seamlessly", "unlock", "unlocks",
    "empower", "empowers", "holistic", "vibrant", "resonate", "resonates", "showcase", "elevate", "lens",
    "landscape", "crucial", "robust", "foster", "journey", "testament", "compelling", "tension", "framing",
    "reframe", "unpack", "quietly", "stark", "starkly", "load-bearing", "texture", "gesture", "gestures",
    "at its core", "worth noting", "it's worth", "here's the thing", "the uncomfortable truth",
    "that's the point", "that's the whole point", "and that's okay", "and that's fine", "make no mistake",
    "let that sink in", "the kicker", "in summary", "in conclusion", "key insight", "hard truth",
    "here's why", "here's what", "counterintuitively", "game-changer", "game changer", "north star",
    "double down", "the reality is", "at the end of the day", "moving forward", "in today's",
    "in an era", "ever-evolving", "fast-paced", "rapidly evolving", "deep dive", "mental model",
    "stakeholder", "stakeholders", "utilize", "facilitate", "ideate", "synergy", "the real question",
    "the truth is", "to be clear", "the answer is simple", "the catch", "what matters", "full stop",
    "the shape of", "the real work", "the hard part", "the quiet part", "something deeper",
    "that's the trick", "that's the whole trick", "here's the", "the real reason", "the real answer",
    "not a bug", "the point isn't", "it turns out",
    # Announcers: a sentence that declares importance instead of making the point.
    "the whole story", "explains a lot", "says it all", "tells you everything", "that's everything",
    "is the key", "the crucial part", "the part that matters", "here's roughly", "this is where", "genuinely", "truly", "deeply", "fundamentally",
    "ultimately", "arguably", "essentially", "leverage", "meaningful", "paradigm",
] + FORMAL_TRANSITIONS

STOP = set("""a about above after again against all am an and any are aren't as at be because been before being
below between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each
few for from further had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him
himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself
no nor not of off on once only or other ought our ours ourselves out over own same shan't she she'd she'll she's
should shouldn't so some such than that that's the their theirs them themselves then there there's these they
they'd they'll they're they've this those through to too under until up very was wasn't we we'd we'll we're we've
were weren't what what's when when's where where's which while who who's whom why why's with won't would wouldn't
you you'd you'll you're you've your yours yourself yourselves just also even much many one ones thing things way
get got make made people like will""".split())


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s", "ly"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _vocab_tokens(sentences: list) -> list:
    """Lowercased tokens, skipping mid-sentence capitalized words (names) so
    proper nouns don't count as vocabulary choices."""
    toks = []
    for s in sentences:
        ws = words_of(s)
        for i, w in enumerate(ws):
            if i > 0 and w[0].isupper() and w != "I" and not w.startswith("I'"):
                continue
            toks.append(w.lower())
    return toks


def mattr(tokens: list, window: int = 100) -> float:
    if len(tokens) <= window:
        return len(set(tokens)) / max(1, len(tokens))
    counts = Counter(tokens[:window])
    total = len(counts)
    acc = total
    n = 1
    for i in range(window, len(tokens)):
        out, inn = tokens[i - window], tokens[i]
        counts[out] -= 1
        if counts[out] == 0:
            del counts[out]
            total -= 1
        if counts[inn] == 0:
            total += 1
        counts[inn] += 1
        acc += total
        n += 1
    return acc / n / window


def count_phrase(text_lower: str, phrase: str) -> int:
    return len(re.findall(r"(?<![\w'-])" + re.escape(phrase) + r"(?![\w'-])", text_lower))


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

METRICS = {
    # key: (label, side, weight, group, hint)
    # side: "both" = too high or too low is off-voice; "upper" = only high is a problem; "lower" = only low.
    "em_dash_per_1k":        ("Em dashes /1k words", "upper", 3, "tells",
                              "Replace most dashes with commas, parentheses, or a new sentence."),
    "antithesis_per_1k":     ('"Not X. It\'s Y." reframes /1k', "upper", 3, "tells",
                              "Say what the thing is. Drop the negated straw version."),
    "tell_rate_per_1k":      ("Modern-LLM tell phrases /1k", "upper", 3, "tells",
                              "Swap flagged phrases for plain words, or cut the sentence."),
    "punchline_para_pct":    ("Paragraphs ending on a zinger (%)", "upper", 3, "tells",
                              "Let more paragraphs end mid-thought. Not every paragraph needs a mic drop."),
    "staccato_per_1k":       ("Staccato runs (3+ tiny sentences) /1k", "upper", 2, "tells",
                              "Merge runs of fragments into one sentence that carries the logic."),
    "formal_trans_per_1k":   ("Formal transitions /1k", "upper", 2, "tells",
                              "Use 'so', 'but', 'which means', or no connective at all."),
    "delta":                 ("Function-word distance (Burrows' Delta)", "upper", 3, "voice",
                              "Overall word-habit mismatch. See the over/under-used words below."),
    "oov_pct":               ("Words PG rarely uses (%)", "upper", 2, "voice",
                              "Too much vocabulary outside PG's working set. Prefer ordinary words."),
    "avg_word_len":          ("Avg word length (chars)", "both", 2, "voice",
                              "Use shorter, more ordinary words."),
    "long_word_pct":         ("Words of 10+ letters (%)", "upper", 1, "voice",
                              "Too many long words. PG says 'use', not 'utilize'."),
    "contractions_per_1k":   ("Contractions /1k", "both", 2, "voice",
                              "Write like you'd say it: it's, don't, you'll."),
    "qualifiers_per_1k":     ("Honest hedges (I think, probably) /1k", "both", 1, "voice",
                              "PG marks what he believes vs. knows. Too few reads as bluster, too many as mush."),
    "first_person_per_1k":   ("I / me / my /1k", "both", 1, "voice", "Check whether the narrator is present at PG's level."),
    "you_per_1k":            ("You / your /1k", "both", 1, "voice", "PG talks to the reader directly."),
    "mattr":                 ("Lexical variety (MATTR-100)", "both", 1, "voice",
                              "High = thesaurus prose. Low = repetitive."),
    "sent_len_mean":         ("Avg sentence length", "both", 2, "rhythm", "Adjust sentence length toward PG's range."),
    "sent_len_median":       ("Median sentence length", "both", 1, "rhythm", ""),
    "sent_len_sd":           ("Sentence length variety (sd)", "both", 2, "rhythm",
                              "Mix short plain sentences with long spoken-sounding ones."),
    "short_sent_pct":        ("Sentences of 8 words or fewer (%)", "both", 2, "rhythm", ""),
    "long_sent_pct":         ("Sentences of 30+ words (%)", "both", 1, "rhythm", ""),
    "para_len_mean":         ("Avg paragraph length (words)", "both", 1, "rhythm", ""),
    "one_sent_para_pct":     ("One-sentence paragraphs (%)", "both", 2, "rhythm",
                              "One-line paragraphs are emphasis. Overuse turns an essay into a LinkedIn post."),
    "conj_start_pct":        ("Sentences opening And/But/So/Which (%)", "both", 2, "rhythm",
                              "PG's logic moves through plain conjunctions at sentence starts."),
    "questions_per_1k":      ("Questions /1k", "both", 2, "rhythm", "PG asks the question the reader is thinking."),
    "semicolons_per_1k":     ("Semicolons /1k", "upper", 1, "punctuation", ""),
    "colons_per_1k":         ("Colons /1k", "upper", 1, "punctuation", "Colon reveals are a template tell when overused."),
    "parens_per_1k":         ("Parenthetical asides /1k", "both", 1, "punctuation", ""),
    "exclaims_per_1k":       ("Exclamation marks /1k", "upper", 1, "punctuation", ""),
    "para_sim_max":          ("Most similar paragraph pair (cosine)", "upper", 2, "structure",
                              "Two paragraphs are doing the same job. Merge or cut one."),
    "repeat_trigram_per_1k": ("Repeated content phrases /1k", "upper", 1, "structure",
                              "The same phrase keeps coming back. Vary it or cut the lap."),
    "headers_per_1k":        ("Section headers /1k", "upper", 1, "structure", "Most PG essays have no headers."),
    "bullets_per_1k":        ("Bullet/list lines /1k", "upper", 2, "structure", "PG enumerates in prose."),
}


# Two-sided metrics whose fix depends on which side of PG's range you're on: (too low, too high).
DIRECTIONAL_HINTS = {
    "avg_word_len": ("Shorter words than PG. Usually harmless if it comes from plain speech; check for choppy "
                     "baby-talk or lots of numbers and symbols.", "Use shorter, more ordinary words."),
    "contractions_per_1k": ("Write like you'd say it: it's, don't, you'll.",
                            "More contractions than PG. Fine in a casual piece, but check it isn't forced."),
    "conj_start_pct": ("PG's logic moves through plain conjunctions at sentence starts.",
                       "Too many And/But/So openers. Some sentences should carry their own weight."),
    "questions_per_1k": ("PG asks the question the reader is thinking.",
                         "Too many questions. Answer more of them, or turn some into claims."),
    "you_per_1k": ("PG talks to the reader directly.", "Heavy on 'you'. Check it isn't lecturing the reader."),
    "sent_len_mean": ("Sentences shorter than PG's. Join fragments that belong to one thought.",
                      "Sentences longer than PG's. Split the ones that carry two ideas."),
}


def _para_vectors(paragraphs):
    vecs = []
    for p in paragraphs:
        toks = [_stem(w.lower()) for w in words_of(p)]
        toks = [t for t in toks if t not in STOP and len(t) > 2]
        vecs.append(Counter(toks))
    return vecs


def _cos(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b[k] for k in a if k in b)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb)


def extract(paragraphs: list, headers: int = 0, bullets: int = 0, profile: dict = None) -> dict:
    """Compute raw features plus evidence for a list of prose paragraphs."""
    para_sents = [split_sentences(p) for p in paragraphs]
    para_sents = [ps for ps in para_sents if ps]
    sents = [s for ps in para_sents for s in ps]
    body = "\n\n".join(" ".join(ps) for ps in para_sents)
    lower = body.lower()
    words = words_of(body)
    wc = len(words)
    if wc < 60 or len(sents) < 4:
        return {"word_count": wc, "error": "Too short to analyze (need ~60+ words)."}
    k = 1000.0 / wc
    slen = [len(words_of(s)) for s in sents]
    plen = [sum(len(words_of(s)) for s in ps) for ps in para_sents]
    ev = {}

    dash_hits = [s for s in sents if "\u2014" in s or " -- " in s or " \u2013 " in s]
    dashes = body.count("\u2014") + body.count(" -- ") + body.count(" \u2013 ")
    ev["em_dash_per_1k"] = dash_hits

    # Locate each match's sentence so the evidence shows the whole move, not a regex fragment.
    starts, pos = [], 0
    for s in sents:
        i = body.find(s, pos)
        starts.append(i if i >= 0 else pos)
        pos = max(pos, i + len(s)) if i >= 0 else pos
    anti = []
    for rx in ANTITHESIS_RES:
        for m in rx.finditer(body):
            first = max(0, sum(1 for st in starts if st <= m.start()) - 1)
            last = first
            while last + 1 < len(sents) and starts[last + 1] < m.end():
                last += 1
            anti.append(" ".join(sents[first:last + 1]))
    ev["antithesis_per_1k"] = anti

    # Punchline paragraphs: 3+ sentences, last one short and much shorter than the rest.
    punch = []
    eligible = 0
    for ps in para_sents:
        if len(ps) >= 3:
            eligible += 1
            lens = [len(words_of(s)) for s in ps]
            rest = statistics.mean(lens[:-1])
            if lens[-1] <= 7 and lens[-1] <= 0.5 * rest:
                punch.append(ps[-1])
    ev["punchline_para_pct"] = punch

    stacc, run = [], []
    for s, n in zip(sents, slen):
        if n <= 6:
            run.append(s)
        else:
            if len(run) >= 3:
                stacc.append(" ".join(run))
            run = []
    if len(run) >= 3:
        stacc.append(" ".join(run))
    ev["staccato_per_1k"] = stacc

    formal = [w for w in FORMAL_TRANSITIONS for _ in range(count_phrase(lower, w))]
    ev["formal_trans_per_1k"] = formal

    conj = [s for s in sents if CONJ_START_RE.match(s)]
    alpha = [w for w in words if w.isalpha()]
    vocab_toks = _vocab_tokens(sents)

    vecs = _para_vectors([" ".join(ps) for ps in para_sents])
    best, pair = 0.0, None
    for i in range(len(vecs)):
        if sum(vecs[i].values()) < 12:
            continue
        for j in range(i + 1, len(vecs)):
            if sum(vecs[j].values()) < 12:
                continue
            c = _cos(vecs[i], vecs[j])
            if c > best:
                best, pair = c, (i, j)
    ev["para_sim_max"] = ([" ".join(para_sents[pair[0]])[:160] + "...",
                           " ".join(para_sents[pair[1]])[:160] + "..."] if pair else [])

    content = [_stem(w.lower()) for w in words]
    tris = Counter()
    for s in sents:
        toks = [_stem(w.lower()) for w in words_of(s)]
        toks = [t for t in toks if t not in STOP and len(t) > 2]
        for i in range(len(toks) - 2):
            tris[tuple(toks[i:i + 3])] += 1
    rep = {" ".join(t): c for t, c in tris.items() if c >= 2}
    ev["repeat_trigram_per_1k"] = [f"{t} (x{c})" for t, c in sorted(rep.items(), key=lambda x: -x[1])]

    f = {
        "word_count": wc,
        "em_dash_per_1k": dashes * k,
        "antithesis_per_1k": len(anti) * k,
        "punchline_para_pct": 100.0 * len(punch) / eligible if eligible else 0.0,
        "staccato_per_1k": len(stacc) * k,
        "formal_trans_per_1k": len(formal) * k,
        "avg_word_len": statistics.mean(len(w) for w in alpha) if alpha else 0.0,
        "long_word_pct": 100.0 * sum(1 for w in alpha if len(w) >= 10) / max(1, len(alpha)),
        "contractions_per_1k": len(CONTRACTION_RE.findall(body)) * k,
        "qualifiers_per_1k": len(QUALIFIER_RE.findall(body)) * k,
        "first_person_per_1k": len(re.findall(r"\b(?:I|me|my|myself|I'd|I'll|I've|I'm)\b", body)) * k,
        "you_per_1k": len(re.findall(r"\b(?:you|your|yourself|you're|you'll|you've|you'd)\b", body, re.I)) * k,
        "mattr": mattr(vocab_toks),
        "sent_len_mean": statistics.mean(slen),
        "sent_len_median": statistics.median(slen),
        "sent_len_sd": statistics.stdev(slen) if len(slen) > 1 else 0.0,
        "short_sent_pct": 100.0 * sum(1 for n in slen if n <= 8) / len(slen),
        "long_sent_pct": 100.0 * sum(1 for n in slen if n >= 30) / len(slen),
        "para_len_mean": statistics.mean(plen),
        "one_sent_para_pct": 100.0 * sum(1 for ps in para_sents if len(ps) == 1) / len(para_sents),
        "conj_start_pct": 100.0 * len(conj) / len(sents),
        "questions_per_1k": body.count("?") * k,
        "semicolons_per_1k": body.count(";") * k,
        "colons_per_1k": len(re.findall(r":\s", body)) * k,
        "parens_per_1k": body.count("(") * k,
        "exclaims_per_1k": body.count("!") * k,
        "para_sim_max": best,
        "repeat_trigram_per_1k": len(rep) * k,
        "headers_per_1k": headers * k,
        "bullets_per_1k": bullets * k,
    }

    # Openers and closers (reported as notes, not scored)
    notes = []
    if META_OPENER_RE.match(sents[0]):
        notes.append(f"Opener talks about the essay instead of the idea: \"{sents[0][:100]}\"")
    last_par = " ".join(para_sents[-1])
    if SUMMARY_CLOSER_RE.search(last_par):
        notes.append(f"Closing paragraph reads like a summary: \"{last_par[:120]}\"")
    ev["_notes"] = notes

    if profile:
        f.update(_profile_features(lower, vocab_toks, words, profile, ev))
    f["_evidence"] = ev
    return f


def _profile_features(lower, vocab_toks, words, profile, ev):
    """Features that need corpus data: tells, OOV, Burrows' Delta."""
    out = {}
    wc = len(words)
    tells = []
    for phrase, pg_rate in profile["tell_rates_per_1k"].items():
        n = count_phrase(lower, phrase)
        if not n:
            continue
        expected = pg_rate * wc / 1000.0
        # A phrase counts only if PG basically never uses it, or the draft uses it far more than he does.
        if (pg_rate < 0.004 and n >= 1) or (n >= 2 and n > 4 * expected + 1):
            tells.append((phrase, n))
    out["tell_rate_per_1k"] = sum(n for _, n in tells) * 1000.0 / wc
    ev["tell_rate_per_1k"] = [f"{p} (x{n})" for p, n in sorted(tells, key=lambda x: -x[1])]

    vocab = set(profile["vocab"])
    oov = [t for t in vocab_toks if t not in vocab]
    out["oov_pct"] = 100.0 * len(oov) / max(1, len(vocab_toks))
    ev["oov_pct"] = [w for w, _ in Counter(oov).most_common(12)]

    out["delta"], ev["delta"] = burrows_delta(words, profile["function_words"], profile["fw_stats"])
    return out


def fw_freqs(words: list, fws: list) -> list:
    c = Counter(w.lower() for w in words)
    n = max(1, len(words))
    return [c[w] / n for w in fws]


def pick_bucket(fw_stats: dict, wc: int) -> str:
    sizes = sorted(int(s) for s in fw_stats)
    return str(min(sizes, key=lambda s: abs(math.log(s) - math.log(max(wc, 1)))))


def burrows_delta(words, fws, fw_stats, bucket=None):
    bucket = bucket or pick_bucket(fw_stats, len(words))
    st = fw_stats[bucket]
    freqs = fw_freqs(words, fws)
    zs = []
    for w, x, mu, sd in zip(fws, freqs, st["mean"], st["sd"]):
        zs.append((w, (x - mu) / sd if sd > 0 else 0.0))
    # Winsorize: one topical word ("many" in an essay about how many people can't write)
    # shouldn't dominate a measure meant to capture broad habits.
    delta = sum(min(abs(z), 3.0) for _, z in zs) / len(zs)
    top = sorted(zs, key=lambda t: -abs(t[1]))[:8]
    ev = [f"{w} {'over' if z > 0 else 'under'}used ({z:+.1f} sd)" for w, z in top if abs(z) >= 1.5]
    return delta, ev


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

QS = [1, 5, 10, 25, 50, 75, 90, 95, 99]


def quantiles(vals: list) -> dict:
    v = sorted(vals)
    n = len(v)
    out = {}
    for q in QS:
        pos = (n - 1) * q / 100.0
        lo, hi = int(math.floor(pos)), int(math.ceil(pos))
        out[str(q)] = v[lo] + (v[hi] - v[lo]) * (pos - lo)
    return out


def percentile_of(value: float, q: dict) -> float:
    pts = [(float(k), q[k]) for k in sorted(q, key=float)]
    if value <= pts[0][1]:
        return pts[0][0] if value == pts[0][1] else 0.5
    if value >= pts[-1][1]:
        return pts[-1][0] if value == pts[-1][1] else 99.5
    for (p1, v1), (p2, v2) in zip(pts, pts[1:]):
        if v1 <= value <= v2:
            if v2 == v1:
                return (p1 + p2) / 2
            return p1 + (p2 - p1) * (value - v1) / (v2 - v1)
    return 50.0


# Credit per status. A FAIL (beyond anything but PG's rarest 1%) costs more than
# a missing point: in cross-validation this separated fluent-but-not-PG prose
# from real PG better than a 0-floor did, at the same false-alarm rate.
CREDIT = {"ok": 1.0, "edge": 0.8, "warn": 0.3, "fail": -0.5}


def grade(value: float, q: dict, side: str) -> tuple:
    """Return (status, credit) by where value falls in PG's distribution."""
    lo_ok = side == "upper" or value >= q["10"]
    hi_ok = side == "lower" or value <= q["90"]
    if lo_ok and hi_ok:
        status = "ok"
    elif not hi_ok:
        status = "edge" if value <= q["95"] else "warn" if value <= q["99"] else "fail"
    else:
        status = "edge" if value >= q["5"] else "warn" if value >= q["1"] else "fail"
    return status, CREDIT[status]


def load_profile(path: str = None) -> dict:
    with open(path or DEFAULT_PROFILE) as fh:
        return json.load(fh)


def score(text: str, profile: dict, era: str = "all") -> dict:
    doc = clean_essay(text)
    f = extract(doc["paragraphs"], doc["headers"], doc["bullets"], profile)
    if "error" in f:
        return {"word_count": f["word_count"], "error": f["error"]}
    ev = f.pop("_evidence")
    eras = profile["eras"]
    era = era if era in eras else "all"
    bucket = pick_bucket(eras[era], f["word_count"])
    qtab = eras[era][bucket]["quantiles"]
    results, num, den = {}, 0.0, 0.0
    for key, (label, side, weight, group, hint) in METRICS.items():
        if key not in f or key not in qtab:
            continue
        q = qtab[key]
        status, credit = grade(f[key], q, side)
        if key in DIRECTIONAL_HINTS and status != "ok":
            hint = DIRECTIONAL_HINTS[key][0 if f[key] < q["50"] else 1]
        results[key] = {
            "label": label, "group": group, "value": round(f[key], 3), "status": status,
            "percentile": round(percentile_of(f[key], q), 1),
            "pg_p10": round(q["10"], 3), "pg_p50": round(q["50"], 3), "pg_p90": round(q["90"], 3),
            "hint": hint, "evidence": ev.get(key, [])[:6],
        }
        num += weight * credit
        den += weight
    return {
        "title": doc["title"], "word_count": f["word_count"], "era": era, "bucket_words": int(bucket),
        "bucket_chunks": eras[era][bucket]["n"], "score": round(max(0.0, 100.0 * num / den), 1),
        # Prefer cross-validated PG scores (honest) over in-sample ones (optimistic).
        "pg_score_quantiles": profile.get("cv_score_quantiles") or eras[era][bucket].get("score_quantiles"),
        "metrics": results, "notes": ev.get("_notes", []),
    }
