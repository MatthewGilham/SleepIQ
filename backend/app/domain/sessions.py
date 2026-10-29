"""Pure sleep-session construction (DATA_PIPELINE D1-D4, P3). Works on UTC epoch seconds.

A session window runs from the first asleep segment's start to the last asleep segment's end;
leading/trailing Awake is trimmed, interior Awake counts as awake time and gaps count as neither.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from itertools import pairwise

from app.domain.config import DeriveConfig

ASLEEP = frozenset({"Core", "Deep", "REM"})


@dataclass(frozen=True)
class StageRow:
    id: int
    source: str
    start: int
    end: int
    start_offset: int
    end_offset: int
    stage: str
    qty: float | None = None


@dataclass(frozen=True)
class Candidate:
    source: str
    start: int
    end: int
    start_offset: int
    end_offset: int
    wake_date: date
    core: int
    deep: int
    rem: int
    awake: int
    overlap_seconds: int
    qty_mismatches: int

    @property
    def asleep(self) -> int:
        return self.core + self.deep + self.rem


@dataclass(frozen=True)
class Night:
    selected: Candidate
    candidate_count: int
    flags: tuple[str, ...]


def local_date(instant: int, offset_minutes: int) -> date:
    return datetime.fromtimestamp(instant + offset_minutes * 60, UTC).date()


def local_minute(instant: int, offset_minutes: int) -> float:
    """Wall-clock minutes after local midnight (float)."""
    return ((instant + offset_minutes * 60) % 86400) / 60


def _resolve(chain: list[StageRow]) -> tuple[list[tuple[int, int, StageRow]], int]:
    """Non-overlapping segments; overlapping rows resolve to the latest start (then lowest id)."""
    bounds = sorted({value for row in chain for value in (row.start, row.end)})
    segments: list[tuple[int, int, StageRow]] = []
    overlap = 0
    for a, b in pairwise(bounds):
        covering = [row for row in chain if row.start <= a and row.end >= b]
        if not covering:
            continue
        winner = max(covering, key=lambda row: (row.start, -row.id))
        if len(covering) > 1:
            overlap += b - a
        if segments and segments[-1][2] is winner and segments[-1][1] == a:
            segments[-1] = (segments[-1][0], b, winner)
        else:
            segments.append((a, b, winner))
    return segments, overlap


def _candidate(chain: list[StageRow]) -> Candidate | None:
    segments, overlap = _resolve(chain)
    asleep_at = [i for i, (_, _, row) in enumerate(segments) if row.stage in ASLEEP]
    if not asleep_at:
        return None
    kept = segments[asleep_at[0] : asleep_at[-1] + 1]
    totals = dict.fromkeys(("Core", "Deep", "REM", "Awake"), 0)
    for a, b, row in kept:
        totals[row.stage] += b - a
    first, last = kept[0][2], kept[-1][2]
    return Candidate(
        source=first.source,
        start=kept[0][0],
        end=kept[-1][1],
        start_offset=first.start_offset,
        end_offset=last.end_offset,
        wake_date=local_date(kept[-1][1], last.end_offset),
        core=totals["Core"],
        deep=totals["Deep"],
        rem=totals["REM"],
        awake=totals["Awake"],
        overlap_seconds=overlap,
        qty_mismatches=0,
    )


def build_candidates(rows: list[StageRow], cfg: DeriveConfig) -> list[Candidate]:
    by_source: dict[str, list[StageRow]] = defaultdict(list)
    for row in rows:
        by_source[row.source].append(row)
    result: list[Candidate] = []
    for source in sorted(by_source):
        ordered = sorted(by_source[source], key=lambda row: (row.start, row.end, row.id))
        chains: list[list[StageRow]] = []
        chain_end = 0
        for row in ordered:
            if chains and row.start - chain_end <= cfg.gap_seconds:
                chains[-1].append(row)
                chain_end = max(chain_end, row.end)
            else:
                chains.append([row])
                chain_end = row.end
        for chain in chains:
            candidate = _candidate(chain)
            if candidate is None:
                continue
            mismatches = sum(
                row.qty is not None
                and abs(row.qty * 3600 - (row.end - row.start)) > cfg.qty_tolerance_seconds
                for row in chain
            )
            result.append(_with_mismatches(candidate, mismatches))
    return result


def _with_mismatches(candidate: Candidate, mismatches: int) -> Candidate:
    return Candidate(**{**candidate.__dict__, "qty_mismatches": mismatches})


def select_nights(candidates: list[Candidate], cfg: DeriveConfig) -> dict[date, Night]:
    """One main session per source-local wake date (P3); blocks under the minimum are naps."""
    by_date: dict[date, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.asleep >= cfg.min_night_asleep_seconds:
            by_date[candidate.wake_date].append(candidate)
    nights: dict[date, Night] = {}
    for day, group in by_date.items():
        preferred = [c for c in group if cfg.preferred_source in c.source.lower()]
        pool = preferred or group
        ranked = sorted(pool, key=lambda c: (-c.asleep, c.start, c.source))
        winner = ranked[0]
        flags: list[str] = []
        if not preferred:
            flags.append("non_preferred_source")
        if len(pool) > 1:
            flags.append("multiple_candidates")
        if len(ranked) > 1 and ranked[1].asleep == winner.asleep:
            flags.append("tie")
        if len(pool) < len(group):
            flags.append("other_source_ignored")
        if winner.overlap_seconds:
            flags.append("overlapping_stages")
        if winner.qty_mismatches:
            flags.append("qty_mismatch")
        nights[day] = Night(winner, len(group), tuple(flags))
    return nights
