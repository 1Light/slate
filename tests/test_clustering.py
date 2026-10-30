from __future__ import annotations

from pathlib import Path
import pytest
from app.structure import _quantile
from app.structure import analyse
from .helpers import _slate


def test_obvious_groups_separate():
    a = analyse(_slate({"A": 5, "B": 5}))
    assert a.headline["clusters"] == 2
    assert {len(g) for g in a.clusters} == {5}


def test_popularity_threshold_is_relative_to_the_slate():
    berlinale = [0.750, 0.824, 0.702, 0.972, 0.972, 0.946, 0.993, 0.887,
                 0.860, 0.830, 0.894, 0.887, 0.961, 0.889, 0.796, 0.979,
                 0.848, 0.728, 0.942, 0.694]
    cut = _quantile(berlinale, 0.75)
    assert 0.93 < cut < 0.97
    assert 0.993 >= cut
    assert 0.824 < cut


def test_quantile_handles_short_lists():
    assert _quantile([], 0.75) == 0.0
    assert _quantile([0.5], 0.75) == 0.5
    assert _quantile([0.0, 1.0], 0.5) == 0.5


def test_tiny_slate_is_refused():
    with pytest.raises(ValueError):
        analyse(_slate({"A": 2}))


def test_bridge_rule_is_strict():
    a = analyse(_slate({"A": 6, "B": 6}))
    assert a.headline["bridges"] <= 1


def test_lof_separates_a_sparse_pair_from_a_true_loner():
    from app.structure import _lof
    films = [f"A{i}" for i in range(6)] + ["P0", "P1", "LONER"]
    pos = {f: i for i, f in enumerate(films[:6])}
    pos.update({"P0": 20, "P1": 21, "LONER": 60})

    class M:
        def __init__(self, films):
            self.films = films

        def distance(self, a, b):
            return abs(pos[a] - pos[b])

    scores = _lof(M(films), films, 3)
    assert scores["LONER"] > scores["P0"], "the loner must outrank the pair"
    assert scores["LONER"] > scores["P1"]


def test_broad_appeal_needs_the_slate_to_support_it():
    m = _slate({"A": 6, "B": 6})
    for i, f in enumerate(m.films):
        m.resolved[f].popularity = 0.99 - 0.02 * i
    a = analyse(m)
    if a.popularity_confound is not None and a.popularity_confound < 0.30:
        assert all(i["kind"] != "broad appeal" for i in a.isolated)


def test_two_clean_groups_are_found_as_two():
    a = analyse(_slate({"A": 6, "B": 6}))
    assert len(a.clusters) == 2
    assert a.cut_check["chosen"] == 2


def test_a_shredded_partition_is_not_chosen():
    a = analyse(_slate({"A": 6, "B": 6}))
    alone = sum(1 for g in a.clusters if len(g) == 1)
    assert alone <= len(a.films_in_order()) * 0.25 if hasattr(a, "films_in_order") \
        else alone <= 3


def test_fewest_groups_wins_a_tie():
    a = analyse(_slate({"A": 6, "B": 6}))
    cc = a.cut_check
    if cc.get("within_noise"):
        assert cc["chosen"] == min(cc["within_noise"])


def test_groups_survive_losing_a_film():
    a = analyse(_slate({"A": 6, "B": 6}))
    st = a.stability
    assert st, "stability should be computed for a slate this size"
    assert st["ari"] is not None and st["ari"] > 0.6, st["ari"]
    for c in st["clusters"]:
        if c["jaccard"] is not None:
            assert c["jaccard"] >= 0.6, c


def test_redundant_pairs_cover_every_cluster():
    from app.structure import _redundant_pairs
    m = _slate({"A": 6, "B": 6})
    a = analyse(m)
    pairs = _redundant_pairs(m, a.clusters)
    covered = {c for _, _, _, c in pairs}
    expected = {i for i, g in enumerate(a.clusters) if len(g) > 1}
    assert covered == expected, "every non-singleton cluster needs a pair"


def test_redundant_pairs_are_sorted_cheapest_first():
    from app.structure import _redundant_pairs
    m = _slate({"A": 6, "B": 6})
    a = analyse(m)
    d = [p[2] for p in _redundant_pairs(m, a.clusters)]
    assert d == sorted(d)


def test_singleton_clusters_contribute_no_pair():
    from app.structure import _redundant_pairs
    m = _slate({"A": 5, "B": 5})
    a = analyse(m)
    singles = {i for i, g in enumerate(a.clusters) if len(g) == 1}
    got = {c for _, _, _, c in _redundant_pairs(m, a.clusters)}
    assert not (got & singles)


def test_a_pair_is_judged_against_what_a_pair_scores_by_chance():
    a = analyse(_slate({"A": 6, "B": 6}))
    st = a.stability
    assert st
    for c in st["clusters"]:
        if c["jaccard"] is None:
            continue
        assert c["chance"] is not None, c
        assert c["lift"] == round(c["jaccard"] - c["chance"], 2), c


def test_chance_is_higher_for_smaller_groups():
    from app.structure import _chance_hold
    m = _slate({"A": 5, "B": 5})
    chance = _chance_hold(m, [2, 2, 3, 3], rounds=6)
    assert chance.get(2) is not None and chance.get(3) is not None
    assert chance[2] >= chance[3] - 0.15


def test_the_same_slate_gives_the_same_answer():
    m = _slate({"A": 6, "B": 6})
    first = analyse(m)
    for _ in range(3):
        again = analyse(_slate({"A": 6, "B": 6}))
        assert [sorted(g) for g in again.clusters] == [sorted(g) for g in first.clusters]
        assert [b["film"] for b in again.bridges] == [b["film"] for b in first.bridges]
        assert [i["film"] for i in again.isolated] == [i["film"] for i in first.isolated]


def test_ties_are_broken_by_name_not_by_iteration_order():
    src = (Path(__file__).resolve().parent.parent / "app" / "structure.py").read_text()
    knn = src[src.index("def _knn("):src.index("def _betweenness(")]
    assert "nearest[:k]" in knn
    assert "round(matrix.distance(a, b), 12), b)" in knn
    agg = src[src.index("def _agglomerate("):src.index("def _cut_to(")]
    assert "min(clusters[i] + clusters[j])" in agg
    bet = src[src.index("def _betweenness("):src.index("def _completeness(")]
    assert "sorted(adj[v])" in bet and "sorted(pred[w])" in bet


def test_a_lineup_that_does_not_separate_is_one_group():
    src = (Path(__file__).resolve().parent.parent / "app" / "structure.py").read_text()
    assert "WEAK_SEPARATION = 0.3" in src
    block = src[src.index("pick = _choose_k(matrix, films, merges)"):src.index("clusters = _cut_to(films, merges, groups)")]
    assert "groups = 1 if weak" in block
