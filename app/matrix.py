from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .qloo import Qloo, id_of
from .resolve import Resolved


def censored_fill(returned: int, candidates: int) -> float:
    return (returned + 1 + candidates) / 2


@dataclass
class Matrix:
    films: list[str]
    ranks: dict[str, dict[str, float]]
    resolved: dict[str, Resolved]
    ghosts: list[str] = field(default_factory=list)
    partial: list[str] = field(default_factory=list)
    imputed: dict[str, set[str]] = field(default_factory=dict)

    def distance(self, a: str, b: str) -> float:
        vals = [v for v in (self.ranks.get(a, {}).get(b),
                            self.ranks.get(b, {}).get(a)) if v is not None]
        return sum(vals) / len(vals) if vals else float(len(self.films))

    def observed(self, anchor: str, other: str) -> bool:
        return (self.ranks.get(anchor, {}).get(other) is not None
                and other not in self.imputed.get(anchor, ()))

    def confidence(self, a: str, b: str) -> float:
        return sum((self.observed(a, b), self.observed(b, a))) / 2

    def pairs(self):
        for a, b in combinations(self.films, 2):
            yield a, b, self.distance(a, b)

    def popularity(self, title: str) -> float | None:
        r = self.resolved.get(title)
        return r.popularity if r else None


def build(qloo: Qloo, resolved: dict[str, Resolved],
          entity_type: str = "urn:entity:movie") -> Matrix:
    titles = list(resolved.keys())
    ids = {t: resolved[t].entity_id for t in titles}
    by_id = {v.casefold(): k for k, v in ids.items()}

    returned: dict[str, list[str]] = {}
    times_returned: dict[str, int] = {t: 0 for t in titles}

    for anchor in titles:
        others = [t for t in titles if t != anchor]
        results = qloo.rank_within(ids[anchor], [ids[t] for t in others], entity_type)

        ordered: list[str] = []
        for entity in results:
            rid = id_of(entity)
            if not rid:
                continue
            title = by_id.get(rid.casefold())
            if title and title != anchor and title not in ordered:
                ordered.append(title)

        returned[anchor] = ordered
        for t in ordered:
            times_returned[t] += 1

    ghosts = [t for t in titles if times_returned[t] == 0]
    usable = [t for t in titles if t not in ghosts]
    candidates = len(usable) - 1

    ranks: dict[str, dict[str, float]] = {}
    imputed: dict[str, set[str]] = {}

    for anchor in usable:
        ordered = [t for t in returned[anchor] if t in usable]
        row: dict[str, float] = {t: i + 1 for i, t in enumerate(ordered)}
        absent = [t for t in usable if t != anchor and t not in row]

        if absent:
            fill = censored_fill(len(ordered), candidates)
            for t in absent:
                row[t] = fill

        ranks[anchor] = row
        imputed[anchor] = set(absent)

    partial = sorted({t for anchor in usable for t in imputed[anchor]})

    return Matrix(films=usable, ranks=ranks, resolved=resolved,
                  ghosts=ghosts, partial=partial, imputed=imputed)
