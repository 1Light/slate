from __future__ import annotations

from app.matrix import Matrix
from app.resolve import Film, Resolved

def _slate(groups: dict[str, int], popularity: float = 0.9) -> Matrix:
    films = [f"{letter}{i}" for letter, n in groups.items() for i in range(n)]
    resolved = {
        t: Resolved(film=Film(title=t, year=2020), entity_id=f"id-{t}",
                    qloo_name=t, qloo_year=2020, popularity=popularity, score=10)
        for t in films
    }
    ranks = {}
    for a in films:
        same = [x for x in films if x != a and x[0] == a[0]]
        other = [x for x in films if x[0] != a[0]]
        ranks[a] = {t: i + 1 for i, t in enumerate(same + other)}
    return Matrix(films=films, ranks=ranks, resolved=resolved)


class _FakeQloo:

    def __init__(self, order: list[str], truncate: dict[str, int]):
        self.order = order
        self.truncate = truncate

    def rank_within(self, anchor_id, candidate_ids, entity_type="urn:entity:movie"):
        anchor = anchor_id.removeprefix("id-")
        ranked = sorted(
            (c.removeprefix("id-") for c in candidate_ids),
            key=lambda t: abs(self.order.index(t) - self.order.index(anchor)),
        )
        keep = self.truncate.get(anchor, len(ranked))
        return [{"entity_id": f"id-{t}"} for t in ranked[:keep]]


def _truncated_matrix(n=10, short=("T0", "T1", "T2"), keep=3):
    from app.matrix import build
    titles = [f"T{i}" for i in range(n)]
    resolved = {
        t: Resolved(film=Film(title=t, year=2020), entity_id=f"id-{t}",
                    qloo_name=t, qloo_year=2020, popularity=0.5 + 0.01 * i,
                    score=10)
        for i, t in enumerate(titles)
    }
    qloo = _FakeQloo(titles, {t: keep for t in short})
    return build(qloo, resolved)
