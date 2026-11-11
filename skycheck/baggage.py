"""Heurística para detectar si una tarifa incluye equipaje de mano (carry-on).

Ojo: "artículo personal" / "mochila" / "bolso de mano chico" NO es equipaje de
mano; buscamos la valija de cabina (carry-on, ~10 kg).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

_NEGATIVE = [
    r"sin equipaje de mano",
    r"no incluye equipaje de mano",
    r"equipaje de mano no incluido",
    r"equipaje de mano (con|por) cargo",
    r"equipaje de mano: ?no",
    r"carry[- ]?on (bags? )?(is )?not included",
    r"no carry[- ]?on",
    r"carry[- ]?on (bag )?fee",
    r"carry[- ]?on bags? for a fee",
    r"basic economy",
    r"tarifa basic\b",
    r"solo (un )?articulo personal",
    r"only (a )?personal item",
    r"personal item only",
]

_POSITIVE = [
    r"incluye equipaje de mano",
    r"equipaje de mano incluido",
    r"con equipaje de mano",
    r"equipaje de mano: ?(si|1|incluido)",
    r"carry[- ]?on (bag )?included",
    r"includes? (a )?carry[- ]?on",
    r"1 (free )?carry[- ]?on",
    r"free carry[- ]?on",
]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower())


def detect_carry_on(text: str) -> Optional[bool]:
    t = _normalize(text or "")
    if any(re.search(p, t) for p in _NEGATIVE):
        return False
    if any(re.search(p, t) for p in _POSITIVE):
        return True
    return None
