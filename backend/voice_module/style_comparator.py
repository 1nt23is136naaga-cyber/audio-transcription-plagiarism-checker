"""
style_comparator.py — Communication style shift analysis for AI-assistance detection.

Compares vocabulary level, sentence structure, tone, fluency, and grammar
between personal and technical interview responses. No technical domain
analysis or claim evaluation — purely style-based authenticity detection.

Scoring tiers (shift score):
  < 20  → LOW       → Genuine
  20-40 → MODERATE  → Slight Concern
  40-60 → HIGH      → Suspicious
  > 60  → VERY HIGH → Highly Suspicious
"""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── Text profile builders ──────────────────────────────────────────────────────

def _sentences(text: str) -> list:
    return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

def _words(text: str) -> list:
    return re.findall(r'\b[a-z]+\b', text.lower())

def _avg_sentence_len(text: str) -> float:
    sents = _sentences(text)
    if not sents:
        return 0.0
    return round(sum(len(s.split()) for s in sents) / len(sents), 1)

def _lexical_diversity(text: str) -> float:
    w = _words(text)
    if not w:
        return 0.0
    return round(len(set(w)) / len(w), 3)

def _vocabulary_level(text: str) -> float:
    """Proxy for vocabulary sophistication: avg word length + long-word ratio (0-100)."""
    w = _words(text)
    if not w:
        return 0.0
    long_ratio = sum(1 for x in w if len(x) > 7) / len(w)
    avg_len = sum(len(x) for x in w) / len(w)
    return round(min(100.0, avg_len * 8 + long_ratio * 40), 1)

def _grammar_score(text: str) -> float:
    """Grammar stability proxy (0-100). Penalises fragments and disfluencies."""
    score = 80.0
    for s in _sentences(text):
        parts = s.split()
        if not parts:
            continue
        if len(parts) < 3:
            score -= 1.5
        if parts[0][0].islower():
            score -= 2.0
    words_all = text.lower().split()
    repeats = sum(1 for a, b in zip(words_all, words_all[1:]) if a == b and len(a) > 2)
    score -= repeats * 3
    return round(max(0.0, min(100.0, score)), 1)

_FILLERS = {
    'um', 'uh', 'like', 'basically', 'actually', 'literally',
    'kind of', 'sort of', 'i think', 'i feel', 'i guess', 'you know',
}

def _filler_ratio(text: str) -> float:
    lower = text.lower()
    count = sum(1 for f in _FILLERS if f in lower)
    total = max(1, len(text.split()))
    return round(count / total, 3)


# Formal transition / connector words — high density = structured, written text
_TRANSITIONS = {
    'however', 'furthermore', 'additionally', 'therefore', 'consequently',
    'subsequently', 'nevertheless', 'nonetheless', 'specifically',
    'particularly', 'notably', 'in addition', 'as a result', 'in order to',
    'such as', 'for example', 'in particular', 'as well as', 'in terms of',
    'with respect to', 'on the other hand', 'in contrast', 'that is',
    'for instance', 'to summarize', 'in conclusion', 'to illustrate',
    'as mentioned', 'it is important', 'it is worth', 'it should be noted',
}

def _transition_density(text: str) -> float:
    """Ratio of formal transition/connector phrases to total words (0-1).
    Higher = more structured / written text.  Very diagnostic in AI-vs-spoken comparison."""
    lower = text.lower()
    total = max(1, len(text.split()))
    count = sum(1 for t in _TRANSITIONS if t in lower)
    return round(count / total, 4)

def _formality_score(text: str) -> float:
    """Higher = more formal (0-100)."""
    score = (
        _vocabulary_level(text) * 0.5
        + min(_avg_sentence_len(text) * 2, 40)
        - _filler_ratio(text) * 200
    )
    return round(max(0.0, min(100.0, score)), 1)

def _build_profile(text: str) -> dict:
    return {
        "word_count":          len(text.split()),
        "sentence_count":      max(1, len(_sentences(text))),
        "avg_sentence_len":    _avg_sentence_len(text),
        "lexical_diversity":   _lexical_diversity(text),
        "vocabulary_level":    _vocabulary_level(text),
        "grammar_score":       _grammar_score(text),
        "filler_ratio":        _filler_ratio(text),
        "formality_score":     _formality_score(text),
        "transition_density":  _transition_density(text),
    }


# ── Shift scoring ──────────────────────────────────────────────────────────────

def _pct_diff(p_val: float, t_val: float) -> float:
    denom = max(abs(p_val), abs(t_val), 1.0)
    return abs(t_val - p_val) / denom * 100


# ── Main entry point ───────────────────────────────────────────────────────────

def calculate_style_shift(personal: str, technical: str) -> dict[str, Any]:
    """
    Compare communication style between personal and technical responses.
    Returns only style-based authenticity signals — no domain/technical analysis.

    Weights (higher = more diagnostic):
      vocabulary_level  2.5
      formality_score   2.0
      grammar_score     1.5
      avg_sentence_len  1.2
      lexical_diversity 1.0
      filler_ratio      0.8   (inverted: big drop = suspicious)
    """
    p = _build_profile(personal)
    t = _build_profile(technical)

    WEIGHT_MAP = [
        ("vocabulary_level",   2.5, False),
        ("formality_score",    2.0, False),
        ("grammar_score",      1.5, False),
        ("transition_density", 2.0, False),  # written/structured text marker
        ("avg_sentence_len",   1.2, False),
        ("lexical_diversity",  1.0, False),
        ("filler_ratio",       0.8, True),   # inverted: big DROP = suspicious
    ]

    total_weight = sum(w for _, w, _ in WEIGHT_MAP)
    breakdown: dict[str, float] = {}
    weighted_shift = 0.0

    for key, weight, inverted in WEIGHT_MAP:
        diff = _pct_diff(p[key], t[key])
        if inverted and t[key] < p[key]:
            diff = min(100, diff * 1.5)   # amplify suspicious drop
        breakdown[key] = round(diff, 1)
        weighted_shift += diff * weight

    shift_score = round(min(100.0, weighted_shift / total_weight), 1)

    # ── Directional jump values ────────────────────────────────────────────────
    voc_jump  = t["vocabulary_level"] - p["vocabulary_level"]
    form_jump = t["formality_score"]  - p["formality_score"]
    gram_jump = t["grammar_score"]    - p["grammar_score"]
    sent_jump = t["avg_sentence_len"] - p["avg_sentence_len"]
    fill_drop = p["filler_ratio"]     - t["filler_ratio"]

    # ── Word count ratio penalty ──────────────────────────────────────────────
    # If technical response is 2x+ longer, over-elaboration is itself a signal.
    word_ratio = t["word_count"] / max(1, p["word_count"])
    if word_ratio > 2.0:
        shift_score = min(100.0, shift_score + (word_ratio - 2.0) * 10)

    # ── Single run-on sentence vs multiple structured sentences ───────────────
    # e.g. personal=1 rushed sentence, technical=4 well-formed sentences
    if p["sentence_count"] == 1 and t["sentence_count"] >= 3:
        shift_score = min(100.0, shift_score + 12.0)

    # ── Rule 1: Multiple strong signals → minimum shift of 50 ─────────────────
    strong_signal_count = sum([
        voc_jump  > 15,
        form_jump > 18,
        gram_jump > 12,
        sent_jump > 6,
        fill_drop > 0.03 and p["filler_ratio"] > 0.02,
    ])
    if strong_signal_count >= 3:
        shift_score = max(shift_score, 50.0)

    # ── Rule 2: Simple personal → complex technical: +20 penalty ──────────────
    personal_simple   = p["vocabulary_level"] < 48 and p["avg_sentence_len"] < 16
    technical_complex = t["vocabulary_level"] > 55 or  t["avg_sentence_len"] > 20
    if personal_simple and technical_complex:
        shift_score = min(100.0, shift_score + 20.0)

    shift_score = round(shift_score, 1)

    # ── 4-tier threshold ───────────────────────────────────────────────────────
    if shift_score > 60:
        style_shift = "VERY HIGH"
    elif shift_score >= 40:
        style_shift = "HIGH"
    elif shift_score >= 20:
        style_shift = "MODERATE"
    else:
        style_shift = "LOW"

    # ── Proportional authenticity per tier ────────────────────────────────────
    # LOW   (0-19)  → 80-100
    # MOD   (20-39) → 60-80
    # HIGH  (40-60) → 40-60
    # VHIGH (>60)   → 0-40
    if style_shift == "VERY HIGH":
        authenticity_score = round(max(0.0,  40.0 - (shift_score - 60) * 0.8), 1)
    elif style_shift == "HIGH":
        authenticity_score = round(max(40.0, 60.0 - (shift_score - 40) * 1.0), 1)
    elif style_shift == "MODERATE":
        authenticity_score = round(max(60.0, 80.0 - (shift_score - 20) * 1.0), 1)
    else:
        authenticity_score = round(max(80.0, 100.0 - shift_score * 1.0), 1)

    # ── Style signal flags ─────────────────────────────────────────────────────
    flags: list[str] = []
    if voc_jump > 15:
        flags.append("Sudden vocabulary sophistication increase in technical round")
    if form_jump > 18:
        flags.append("Significant formality jump — personal and technical tones differ sharply")
    if gram_jump > 12:
        flags.append("Grammar quality improved substantially — may indicate AI-generated content")
    if t["transition_density"] > 0.04 and p["transition_density"] < 0.02:
        flags.append("High use of formal connectors in technical round — structured/written language detected")
    if word_ratio > 2.0:
        flags.append(
            f"Technical response is {word_ratio:.1f}x longer than personal — "
            "significant elaboration gap may indicate prepared/AI-generated content"
        )
    if p["sentence_count"] == 1 and t["sentence_count"] >= 3:
        flags.append("Single run-on sentence in personal vs multiple structured sentences in technical round")
    if sent_jump > 6:
        flags.append("Sentence complexity increased significantly in technical round")
    if personal_simple and technical_complex:
        flags.append("Simple-to-complex transition detected — personal language is significantly less sophisticated")
    if strong_signal_count >= 3:
        flags.append(f"{strong_signal_count}/5 style dimensions shifted simultaneously — strong AI-assistance indicator")
    if shift_score > 60 and not flags:
        flags.append("Overall communication fingerprint differs substantially between rounds")

    # ── Summary narrative ──────────────────────────────────────────────────────
    if style_shift == "VERY HIGH":
        summary = (
            f"Very high style shift detected (shift score: {shift_score}/100). "
            "The technical response shows a drastically different communication fingerprint. "
            "Strong indicators of AI-assisted or pre-written content."
        )
    elif style_shift == "HIGH":
        summary = (
            f"High style shift detected (shift score: {shift_score}/100). "
            "The technical response shows a markedly different communication fingerprint. "
            "This may indicate AI-assisted or pre-written content."
        )
    elif style_shift == "MODERATE":
        summary = (
            f"Moderate style shift detected (shift score: {shift_score}/100). "
            "Some differences exist between personal and technical responses. "
            "May reflect topic preparation — warrants further review."
        )
    else:
        summary = (
            f"Low style shift detected (shift score: {shift_score}/100). "
            "Communication style is consistent across both rounds. "
            "Responses appear naturally authored."
        )

    logger.info(
        "[style_comparator] shift=%.1f (%s) | auth=%.1f | signals=%d | flags=%d",
        shift_score, style_shift, authenticity_score, strong_signal_count, len(flags),
    )

    return {
        "authenticity_score":  authenticity_score,
        "style_shift":         style_shift,
        "shift_score":         shift_score,
        "flags":               flags,
        "summary":             summary,
        "personal_profile":    p,
        "technical_profile":   t,
        "shift_breakdown":     breakdown,
        "strong_signal_count": strong_signal_count,
        "_analysis_mode":      "style_comparison_only",
    }
