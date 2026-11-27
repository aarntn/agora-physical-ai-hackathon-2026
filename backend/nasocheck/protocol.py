"""Session protocol, phrases and plain-language messages (EN / BM).

Phrase lists are a first draft: oral phrases avoid /m n ng/ so that any nasal
energy is leakage. Review wording with a Malay-speaking speech therapist.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

# Oral phrases: no nasal consonants. "nasal" trials repeat the same phrase
# deliberately through the nose (demo §7).
PHRASES = {
    "ms": ["Papa pakai topi", "Kakak beli kuih", "Adik suka bola biru"],
    "en": ["Buy Bobby a puppy", "Take a cookie", "Pass the cup to Bob"],
}


@dataclass(frozen=True)
class Step:
    type: str
    phrase: str | None


def steps_for(lang: str, pairs: int) -> list[Step]:
    steps = [Step("hum", None)]
    for p in PHRASES[lang][:pairs]:
        steps += [Step("oral", p), Step("nasal", p)]
    return steps


INSTRUCTIONS = {
    "hum": {"en": "Hold the device to the side of your nose, tap, and hum 'mmmm' for two seconds.",
            "ms": "Letakkan alat di tepi hidung, tekan skrin, dan dengung 'mmmm' selama dua saat."},
    "oral": {"en": "Tap, then say clearly: \"{phrase}\".",
             "ms": "Tekan skrin, kemudian sebut dengan jelas: \"{phrase}\"."},
    "nasal": {"en": "Tap, then say it again through your nose: \"{phrase}\".",
              "ms": "Tekan skrin, kemudian sebut sekali lagi melalui hidung: \"{phrase}\"."},
    "done": {"en": "That's all the measurements. Ask me for a summary.",
             "ms": "Semua ukuran sudah selesai. Minta saya buat ringkasan."},
}

# reason code -> plain-language explanation
REASONS = {
    "clipped": {"en": "That was too loud for the microphone. Please speak a little softer.",
                "ms": "Suara terlalu kuat untuk mikrofon. Cuba cakap sedikit perlahan."},
    "too_short": {"en": "I didn't hear enough voice. Please speak for the whole two seconds, a bit louder.",
                  "ms": "Saya tidak dengar suara yang cukup. Sila bercakap sepanjang dua saat, lebih kuat sedikit."},
    "weak_vibration": {"en": "I couldn't feel the vibration. Press the device gently against the side of your nose.",
                       "ms": "Saya tidak dapat rasa getaran. Tekan alat perlahan-lahan ke tepi hidung."},
    "unstable": {"en": "The reading was unsteady, maybe the device moved. Hold it still and try again.",
                 "ms": "Bacaan tidak stabil, mungkin alat bergerak. Pegang dengan tetap dan cuba lagi."},
    "sensor_rate": {"en": "The sensor had a hiccup. Let's try again.",
                    "ms": "Sensor ada masalah kecil. Mari cuba lagi."},
    "no_ratio": {"en": "I couldn't compute a reading. Let's try again.",
                 "ms": "Saya tidak dapat kira bacaan. Mari cuba lagi."},
    "wrong_phrase": {"en": "That wasn't the phrase I asked for. Please say exactly: \"{phrase}\".",
                     "ms": "Itu bukan ayat yang saya minta. Sila sebut tepat: \"{phrase}\"."},
}


def instruction(step: Step | None, lang: str) -> str:
    key = "done" if step is None else step.type
    return INSTRUCTIONS[key][lang].format(phrase=step.phrase if step else "")


def reason_text(code: str, lang: str, phrase: str | None = None) -> str:
    return REASONS[code][lang].format(phrase=phrase or "")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(s.split())


def phrase_matches(heard: str, expected: str, threshold: float = 0.75) -> bool:
    """Tolerant match for ASR output (spelling, punctuation, small slips)."""
    h, e = _norm(heard), _norm(expected)
    if not h:
        return False
    if e in h:
        return True
    # best match over windows of the same word count (ASR may add filler words)
    hw, n = h.split(), len(e.split())
    windows = [" ".join(hw[i:i + n]) for i in range(max(1, len(hw) - n + 1))]
    return max(difflib.SequenceMatcher(None, w, e).ratio() for w in windows) >= threshold
