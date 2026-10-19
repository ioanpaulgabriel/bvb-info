"""Romanian number parsing.

BVB renders numbers in Romanian locale: '.' groups thousands and ',' is the
decimal separator (e.g. ``1.090.322,25`` -> ``1090322.25``).
"""

from __future__ import annotations

import math
import re

# Matches a pure Romanian thousands-grouped integer, e.g. '598.847.469'.
_THOUSANDS_GROUPED = re.compile(r"\d{1,3}(\.\d{3})+$")


def ro_float(value: object) -> float | None:
    """Parse Romanian strings without reinterpreting numeric inputs."""
    if value is None or isinstance(value, bool):
        return None

    if not isinstance(value, str):
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return result if math.isfinite(result) else None

    s = value.strip()
    if not s or s in ("-", "—", "N/A", "n/a"):
        return None

    s = (
        s.replace("\xa0", " ")
        .replace(" lei", "")
        .replace(" RON", "")
        .strip()
        .replace(" ", "")
    )

    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s and _THOUSANDS_GROUPED.fullmatch(s):
        s = s.replace(".", "")

    try:
        result = float(s)
    except (ValueError, OverflowError):
        return None

    return result if math.isfinite(result) else None


def ro_pct(value: object) -> float | None:
    """Convert a Romanian percentage string to a float value in percent.

    Strips '%', sign markers and trend arrows before parsing.

    >>> ro_pct("+0,52%")
    0.52
    >>> ro_pct("-") is None
    True
    """
    if value is None:
        return None
    s = str(value).replace("%", "").replace("+", "").replace("▲", "").replace("▼", "").strip()
    return ro_float(s)
