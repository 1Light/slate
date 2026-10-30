from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import comb

EXHAUSTIVE_CAP = 200_000

BALANCED = "balanced"
DEMAND_LED = "demand_led"
MODES = (BALANCED, DEMAND_LED)


@dataclass
class Reference:

    title: str
    entity_type: str
    entity_id: str
    weight: float = 1.0
    disliked: int = 0
    sources: list[dict] = field(default_factory=list)


def utility(rank: int, pool: int) -> float:
    if pool <= 1:
        return 1.0
    return max(0.0, min(1.0, 1.0 - (rank - 1) / (pool - 1)))


def utilities(rankings: dict[str, list[str]], pool: list[str]) -> dict:
    n = len(pool)
    out: dict[str, dict[str, float]] = {}
    for ref, order in rankings.items():
        seen = {title: utility(i, n) for i, title in enumerate(order, 1)}
        out[ref] = {t: seen.get(t, 0.0) for t in pool}
    return out


def score(chosen: list[str], refs: list[Reference], u: dict,
          mode: str) -> float:
    if mode == DEMAND_LED:
        return sum(r.weight * u[r.title][c]
                   for r in refs for c in chosen if c in u[r.title])
    return sum(max((u[r.title][c] for c in chosen
                    if c in u[r.title]), default=0.0)
               for r in refs)


def _greedy(pool: list[str], refs: list[Reference], u: dict, mode: str,
            slots: int, locked: list[str]) -> list[str]:
    chosen = list(locked)
    left = [c for c in pool if c not in set(chosen)]
    while len(chosen) < slots and left:
        best, gain = None, None
        for c in left:
            got = score(chosen + [c], refs, u, mode)
            if gain is None or got > gain + 1e-12:
                best, gain = c, got
        chosen.append(best)
        left.remove(best)
    return chosen


def select(pool: list[str], refs: list[Reference], rankings: dict,
           slots: int, mode: str = BALANCED,
           locked: list[str] | None = None) -> dict:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    locked = list(locked or [])
    pool = list(dict.fromkeys(pool))

    unknown = [t for t in locked if t not in pool]
    if unknown:
        raise ValueError(f"locked titles are not candidates: {unknown}")
    if len(locked) > slots:
        raise ValueError(f"{len(locked)} locked but only {slots} slots")
    if len(pool) < slots:
        raise ValueError(f"{len(pool)} candidates cannot fill {slots} slots")
    if not refs:
        raise ValueError("no audience references to select for")

    u = utilities(rankings, pool)
    free = [c for c in pool if c not in set(locked)]
    want = slots - len(locked)

    if want == 0:
        chosen, how = list(locked), "all locked"
    elif comb(len(free), want) <= EXHAUSTIVE_CAP:
        best, top = None, None
        for picked in combinations(free, want):
            full = locked + list(picked)
            got = score(full, refs, u, mode)
            if top is None or got > top + 1e-12:
                best, top = full, got
        chosen, how = best, "exhaustive"
    else:
        chosen = _greedy(pool, refs, u, mode, slots, locked)
        how = "greedy"

    served = sorted(
        ({"reference": r.title,
          "weight": r.weight,
          "best": max((u[r.title][c] for c in chosen if c in u[r.title]),
                      default=0.0),
          "by": max((c for c in chosen if c in u[r.title]),
                    key=lambda c: u[r.title][c], default=None)}
         for r in refs),
        key=lambda row: -row["best"])

    return {
        "chosen": chosen,
        "locked": locked,
        "mode": mode,
        "score": round(score(chosen, refs, u, mode), 4),
        "how": how,
        "served": served,
        "weakest": round(min((row["best"] for row in served), default=0.0), 4),
    }
