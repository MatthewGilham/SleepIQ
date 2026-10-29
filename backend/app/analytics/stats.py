"""Pure A01 statistics (P6/P21): calendar rolling means and paired Pearson correlation."""

import math
from math import fsum

# P21: a rolling mean is shown only when enough nights in its calendar window were observed.
ROLLING_MINIMUM = {7: 4, 30: 15}
MINIMUM_PAIRS = 3


def rolling_mean(values: list[float | None], window: int) -> tuple[list[float | None], list[int]]:
    """Trailing calendar-window means; one list position per calendar day.

    Each output covers its own day and the `window - 1` days before it. Missing days are
    skipped, never treated as zero; below the P21 minimum the mean is unavailable (None).
    Counts are always returned so coverage stays visible.
    """
    minimum = ROLLING_MINIMUM[window]
    means: list[float | None] = []
    counts: list[int] = []
    for i in range(len(values)):
        observed = [v for v in values[max(0, i - window + 1) : i + 1] if v is not None]
        counts.append(len(observed))
        means.append(fsum(observed) / len(observed) if len(observed) >= minimum else None)
    return means, counts


def pearson(xs: list[float], ys: list[float]) -> tuple[float | None, str | None]:
    """Pearson r for already-paired observations, or (None, reason) when undefined (P6)."""
    if len(xs) != len(ys):
        raise ValueError("Paired series must have equal length")
    if len(xs) < MINIMUM_PAIRS:
        return None, f"Unavailable: fewer than {MINIMUM_PAIRS} paired nights"
    # Exact equality, not a variance tolerance: identical readings are constant by definition.
    if len(set(xs)) == 1 or len(set(ys)) == 1:
        return None, "Unavailable: a metric has no variation across the paired nights"
    mx, my = fsum(xs) / len(xs), fsum(ys) / len(ys)
    sxy = fsum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = fsum((x - mx) ** 2 for x in xs)
    syy = fsum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None, "Unavailable: a metric has no variation across the paired nights"
    return max(-1.0, min(1.0, sxy / math.sqrt(sxx * syy))), None
