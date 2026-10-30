from __future__ import annotations

from app.structure import analyse
from .helpers import _slate, _truncated_matrix


def test_ghost_films_are_excluded_not_ranked_last():
    m = _slate({"A": 4, "B": 4})
    m.ranks["A0"]["B3"] = None
    m.ranks["A1"]["B3"] = None
    a = analyse(m)
    distances = [i["film"] for i in a.isolated]
    assert "B3" not in distances[:1] or len(a.isolated) == 0


def test_truncated_rows_stay_comparable():
    m = _truncated_matrix()
    means = []
    for a in m.films:
        row = [v for v in m.ranks[a].values() if v is not None]
        assert len(row) == len(m.films) - 1, "every candidate needs a value"
        means.append(sum(row) / len(row))
    spread = max(means) - min(means)
    assert spread < 1e-9, f"row means differ by {spread:.2f}; rows not comparable"


def test_truncation_is_not_reported_as_isolation():
    m = _truncated_matrix()
    a = analyse(m)
    flagged = {i["film"] for i in a.isolated}
    assert not (flagged & {"T0", "T1", "T2"}), (
        f"short-row films reported as isolated: {sorted(flagged)}"
    )


def test_completeness_counts_observed_not_filled():
    m = _truncated_matrix()
    a = analyse(m)
    assert a.completeness["fraction"] < 1.0


def test_mean_distance_is_a_borda_count():
    m = _slate({"A": 5, "B": 5})
    n = len(m.films)
    for f in m.films:
        received = [m.ranks[g][f] for g in m.films if g != f]
        predicted = n / 4 + 0.5 * (sum(received) / len(received))
        actual = sum(m.distance(f, g) for g in m.films if g != f) / (n - 1)
        assert abs(predicted - actual) < 1e-9


def test_ranks_are_recomputed_when_the_slate_shrinks():
    from app.structure import _rerank
    ranks = {"a": {"b": 1, "c": 2, "d": 3},
             "b": {"a": 1, "c": 2, "d": 3},
             "c": {"a": 1, "b": 2, "d": 3},
             "d": {"a": 1, "b": 2, "c": 3}}
    out = _rerank(ranks, ["a", "b", "d"])
    assert out["a"] == {"b": 1, "d": 2}
    assert sorted(out) == ["a", "b", "d"]
    for row in out.values():
        assert sorted(row.values()) == list(range(1, len(row) + 1))
