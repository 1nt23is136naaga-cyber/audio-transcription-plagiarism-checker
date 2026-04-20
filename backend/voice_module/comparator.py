"""
comparator.py — Dual-mode comparison of interview responses.

Stage 1 (always runs): difflib SequenceMatcher + word-level cosine similarity.
Stage 2 (requires OpenAI key): GPT-4o-mini deep analysis returning strict JSON.
"""

import difflib
import json
import logging
import math
import os
import re
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)


# ── Stage 1: Basic similarity ─────────────────────────────────────────────────

def _word_freq(text: str) -> Counter:
    return Counter(re.findall(r"\b\w+\b", text.lower()))


def _cosine_similarity(text1: str, text2: str) -> float:
    """Word-frequency cosine similarity in [0, 1]."""
    freq1, freq2 = _word_freq(text1), _word_freq(text2)
    if not freq1 or not freq2:
        return 0.0
    vocab = set(freq1) | set(freq2)
    dot = sum(freq1[w] * freq2[w] for w in vocab)
    mag1 = math.sqrt(sum(v ** 2 for v in freq1.values()))
    mag2 = math.sqrt(sum(v ** 2 for v in freq2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def _sequence_similarity(text1: str, text2: str) -> float:
    """Character-level SequenceMatcher ratio in [0, 1]."""
    return difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def basic_similarity(text1: str, text2: str) -> dict[str, float]:
    """Return both similarity metrics as percentages (0–100)."""
    return {
        "sequence": round(_sequence_similarity(text1, text2) * 100, 2),
        "cosine":   round(_cosine_similarity(text1, text2) * 100, 2),
    }


# ── Stage 2: Deep AI analysis ─────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are an expert interview analyst and psycholinguist. "
    "Analyse the provided interview responses and return ONLY valid JSON — "
    "no markdown fences, no prose, no extra keys."
)

_USER_PROMPT_TEMPLATE = """Compare two interview responses from the SAME candidate.

---
PERSONAL INTRODUCTION:
\"\"\"{personal}\"\"\"

---
TECHNICAL EXPLANATION:
\"\"\"{technical}\"\"\"

---
Evaluate:
1. Consistency — do both responses describe the same person coherently?
2. Contradictions — any conflicting facts, dates, or claims?
3. Confidence — does the language suggest confidence or hesitation/hedging?
4. Memorization signals — does the technical portion sound scripted or rehearsed?

Return STRICT JSON with exactly these keys:
{{
  "similarity_score":       <integer 0-100>,
  "consistency_score":      <integer 0-100>,
  "flags":                  [<short flag strings, empty list if none>],
  "summary":                "<2-4 sentence narrative>",
  "improvement_suggestions":[<actionable suggestion strings>]
}}"""


async def deep_compare(personal: str, technical: str) -> dict[str, Any]:
    """
    Full comparison: basic metrics + GPT-4o-mini analysis.

    Returns a dict safe to JSON-serialise and return from an API endpoint.
    Falls back to basic-only result if OpenAI is unavailable.
    """
    from openai import OpenAI  # deferred import — keeps module importable without key

    basics = basic_similarity(personal, technical)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[voice_module] OPENAI_API_KEY not set — returning basic stats only")
        return {
            "similarity_score": basics["cosine"],
            "consistency_score": 0,
            "flags": ["AI analysis unavailable — OPENAI_API_KEY not set"],
            "summary": "Only basic similarity computed. Set OPENAI_API_KEY for deep analysis.",
            "improvement_suggestions": [],
            "basic_similarity": basics,
        }

    client = OpenAI(api_key=api_key)
    prompt = _USER_PROMPT_TEMPLATE.format(personal=personal, technical=technical)

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.2,
            max_tokens=900,
        )
    except Exception as exc:
        logger.exception("[voice_module] OpenAI chat error")
        return {
            "similarity_score": basics["cosine"],
            "consistency_score": 0,
            "flags": [f"AI analysis error: {exc}"],
            "summary": "AI analysis failed. Basic similarity used as fallback.",
            "improvement_suggestions": [],
            "basic_similarity": basics,
        }

    raw = (resp.choices[0].message.content or "").strip()
    # Strip accidental markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE).strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("[voice_module] AI returned non-JSON:\n%s", raw)
        result = {
            "similarity_score": basics["cosine"],
            "consistency_score": 0,
            "flags": ["AI analysis returned malformed JSON"],
            "summary": raw[:500],  # include raw for debugging
            "improvement_suggestions": [],
        }

    # Always inject our objective basic metrics alongside the AI result
    result["basic_similarity"] = basics
    return result
