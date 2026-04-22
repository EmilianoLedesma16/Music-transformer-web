"""
Robust keyword-based NLP parser: free-text musical prompt → structured parameters.

Handles:
  - Spanish and English keywords
  - Negation detection with a sliding window (e.g. "no oscuro", "sin bajo")
  - Multi-word phrase matching (e.g. "bossa nova", "bajo volumen")
  - Per-dimension confidence scoring (positive matches minus negated matches)
  - Off-topic / low-confidence fallback to sensible defaults
"""

import re
import unicodedata
from dataclasses import dataclass, field


# ── Text normalisation ─────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase, strip accents/diacritics, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_text = nfkd.encode("ascii", errors="ignore").decode()
    return re.sub(r"[^a-z0-9\s&]", " ", ascii_text).strip()


def _to_words(norm: str) -> list[str]:
    return norm.split()


# ── Negation ───────────────────────────────────────────────────────────────────

_NEGATION = {
    "no", "sin", "nunca", "jamas", "ni", "nada", "tampoco",
    "without", "not", "neither", "nor",
}
_NEG_WINDOW = 3   # words after a negation word are considered negated


def _negation_mask(words: list[str]) -> list[bool]:
    """Return a bool list: True = this position is in a negation window."""
    negated = [False] * len(words)
    for i, w in enumerate(words):
        if w in _NEGATION:
            for j in range(i + 1, min(i + 1 + _NEG_WINDOW, len(words))):
                negated[j] = True
    return negated


# ── Keyword dictionaries ───────────────────────────────────────────────────────
# Rules for clean keyword lists:
#   * No instrument names inside energy/genre/mood lists (avoids "bajo" clash).
#   * No adjectives shared between dimensions without careful disambiguation.
#   * Multi-word phrases get weight 1.5x (more specific signal).

_GENRE: dict[str, list[str]] = {
    "ROCK": [
        "rock", "rockero", "rockera", "metal", "punk", "grunge",
        "alternativo", "alternativa", "distorsion", "distorsionado",
        "distorsionada", "pesado", "pesada", "hardcore", "heavy",
        "riff", "powerchord",
    ],
    "POP": [
        "pop", "popular", "comercial", "pegajoso", "pegajosa",
        "mainstream", "radio", "radiable", "bailable", "melodico", "melodica",
    ],
    "FUNK": [
        "funk", "funky", "groove", "groovy", "sincopado", "sincopada",
        "soul", "rnb", "r&b",
    ],
    "JAZZ": [
        "jazz", "jazzy", "swing", "improvisacion", "improvisation",
        "blues", "bossa nova", "cool jazz", "bebop", "be bop",
        "improvisado", "improvisada",
    ],
    "LATIN": [
        "latin", "latino", "latina", "salsa", "cumbia", "tropical",
        "reggaeton", "bachata", "merengue", "samba", "tango",
        "rumba", "mambo", "bolero", "vallenato",
    ],
    "CLASSICAL": [
        "clasico", "clasica", "classical", "orquestal", "orquesta",
        "sinfonico", "sinfonica", "sinfonia", "barroco", "barroca",
        "romantico", "romantica", "opera", "concierto", "sonata",
        "filarmonica",
    ],
    "ELECTRONIC": [
        "electronico", "electronica", "electronic", "synth", "sintetizador",
        "techno", "house", "dance", "edm", "trance", "dubstep",
        "programado", "programada", "beat electronico",
    ],
}

_MOOD: dict[str, list[str]] = {
    "HAPPY": [
        "alegre", "alegria", "feliz", "felicidad", "animado", "animada",
        "optimista", "positivo", "positiva", "divertido", "divertida",
        "emocionante", "vibrante", "festivo", "festiva", "celebracion",
        "euforico", "euforica", "contento", "contenta", "jovial",
        "happy", "cheerful", "upbeat", "joyful", "fun",
    ],
    "SAD": [
        "triste", "tristeza", "melancolico", "melancolica", "melancolia",
        "nostalgico", "nostalgica", "nostalgia", "sentimental",
        "depresivo", "depresiva", "llanto", "lagrimas", "pena",
        "dolor", "sufrimiento", "angustia",
        "sad", "melancholic", "blue", "gloomy",
    ],
    "DARK": [
        "oscuro", "oscura", "oscuridad", "sombrio", "sombria",
        "tenebroso", "tenebrosa", "misterioso", "misteriosa", "misterio",
        "amenazante", "inquietante", "perturbador", "perturbadora",
        "ominoso", "ominosa", "sinistro", "siniestra", "macabro", "macabra",
        "dark", "grim", "eerie", "ominous",
    ],
    "RELAXED": [
        "relajado", "relajada", "relajante", "tranquilo", "tranquila",
        "calmado", "calmada", "sereno", "serena", "apacible",
        "pacifico", "meditativo", "meditativa", "zen", "ambiental",
        "peaceful", "calm", "chill", "chilled", "relax",
    ],
    "TENSE": [
        "tenso", "tensa", "tension", "urgente",
        "agresivo", "agresiva", "ansioso", "ansiosa", "ansiedad",
        "nervioso", "nerviosa", "frenetico", "frenetica",
        "acelerado", "acelerada", "angustioso", "angustiosa",
        "tense", "aggressive", "anxious",
    ],
}

# Energy: deliberately excludes instrument names ("bajo", "piano")
# and words that clearly belong only to MOOD.
_ENERGY: dict[str, list[str]] = {
    "LOW": [
        "suave", "leve", "ligero", "ligera", "debil", "pausado", "pausada",
        "intimo", "intima", "delicado", "delicada", "sutil", "apacible",
        "flojo", "floja", "bajito", "bajita", "piano pianissimo",
        "soft", "quiet", "gentle", "low energy",
    ],
    "MED": [
        "moderado", "moderada", "medio", "media",
        "equilibrado", "equilibrada", "normal", "regular",
        "balanceado", "balanceada", "mediano", "mediana",
        "moderate", "medium", "mid",
    ],
    "HIGH": [
        "fuerte", "potente", "poderoso", "poderosa",
        "explosivo", "explosiva", "rapido", "rapida", "veloz",
        "energetico", "energetica", "frenetico", "frenetica",
        "maximo", "maxima", "brutal", "forte",
        "powerful", "energetic", "loud", "fast",
    ],
}

# Instrument: only clear, unambiguous nouns.
_INSTRUMENT: dict[str, list[str]] = {
    "PIANO": ["piano", "teclado", "teclas", "keys", "keyboard", "pianoforte"],
    "BASS":  ["bajo", "bass", "bajista", "contrabajo", "bassline"],
    "GUITAR": ["guitarra", "guitar", "guitarrista"],
}

_DIMS: dict[str, dict[str, list[str]]] = {
    "genre":      _GENRE,
    "mood":       _MOOD,
    "energy":     _ENERGY,
    "instrument": _INSTRUMENT,
}

_DEFAULTS: dict[str, str] = {
    "genre":      "POP",
    "mood":       "HAPPY",
    "energy":     "MED",
    "instrument": "GUITAR",
}

_PHRASE_WEIGHT = 1.5   # multi-word phrases score higher
_WORD_WEIGHT   = 1.0


# ── Public API ─────────────────────────────────────────────────────────────────

@dataclass
class ParseResult:
    genre:      str
    mood:       str
    energy:     str
    instrument: str
    confidence: float                       # 0.0 – 1.0
    detected:   dict[str, bool] = field(default_factory=dict)


def parse_prompt(text: str) -> ParseResult:
    """
    Parse a free-text musical description and return structured parameters.

    confidence == 1.0  → all 4 dimensions detected
    confidence == 0.0  → nothing musical found, all defaults used
    """
    if not text or not text.strip():
        return ParseResult(
            genre="POP", mood="HAPPY", energy="MED", instrument="GUITAR",
            confidence=0.0,
            detected={"genre": False, "mood": False, "energy": False, "instrument": False},
        )

    norm  = _normalize(text)
    words = _to_words(norm)
    neg   = _negation_mask(words)

    results: dict[str, str]  = {}
    detected: dict[str, bool] = {}

    for dim, label_kws in _DIMS.items():
        scores: dict[str, float] = {lbl: 0.0 for lbl in label_kws}

        for label, keywords in label_kws.items():
            for kw in keywords:
                kw_norm = _normalize(kw)

                if " " in kw_norm:
                    # ── Multi-word phrase match ────────────────────────────
                    kw_words = kw_norm.split()
                    klen     = len(kw_words)
                    for i in range(len(words) - klen + 1):
                        if words[i : i + klen] == kw_words:
                            weight = -_PHRASE_WEIGHT if neg[i] else _PHRASE_WEIGHT
                            scores[label] += weight
                else:
                    # ── Single-word match ──────────────────────────────────
                    for i, w in enumerate(words):
                        if w == kw_norm:
                            weight = -_WORD_WEIGHT if neg[i] else _WORD_WEIGHT
                            scores[label] += weight

        best = max(scores, key=lambda l: scores[l])
        if scores[best] > 0:
            results[dim]  = best
            detected[dim] = True
        else:
            results[dim]  = _DEFAULTS[dim]
            detected[dim] = False

    confidence = sum(1 for v in detected.values() if v) / len(_DIMS)

    return ParseResult(
        genre      = results["genre"],
        mood       = results["mood"],
        energy     = results["energy"],
        instrument = results["instrument"],
        confidence = confidence,
        detected   = detected,
    )
