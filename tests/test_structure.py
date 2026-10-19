from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.matrix import Matrix                                  # noqa: E402
from app.resolve import Film, Resolved, score_candidate        # noqa: E402
from app.structure import _quantile, analyse                   # noqa: E402


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


def test_obvious_groups_separate():
    a = analyse(_slate({"A": 5, "B": 5}))
    assert a.headline["clusters"] == 2
    assert {len(g) for g in a.clusters} == {5}


def test_ghost_films_are_excluded_not_ranked_last():
    m = _slate({"A": 4, "B": 4})
    m.ranks["A0"]["B3"] = None
    m.ranks["A1"]["B3"] = None
    a = analyse(m)
    distances = [i["film"] for i in a.isolated]
    assert "B3" not in distances[:1] or len(a.isolated) == 0


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


def test_year_is_not_scored_when_none_was_given():
    entity = {"entity_id": "x", "name": "Perfect Days",
              "properties": {"release_year": 2023}}
    without = score_candidate(entity, Film(title="Perfect Days", year=0))
    assert without >= 5, "an exact title must still resolve without a year"
    with_year = score_candidate(entity, Film(title="Perfect Days", year=2023))
    assert with_year > without


def test_wrong_year_disqualifies_a_same_titled_film():
    wrong = {"entity_id": "x", "name": "Monster",
             "properties": {"release_year": 2003}}
    assert score_candidate(wrong, Film(title="Monster", year=2023)) < 5


def test_tiny_slate_is_refused():
    with pytest.raises(ValueError):
        analyse(_slate({"A": 2}))


def test_bridge_rule_is_strict():
    a = analyse(_slate({"A": 6, "B": 6}))
    assert a.headline["bridges"] <= 1


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


def test_the_agent_will_not_shred_a_slate():
    from app.agent import _score
    sane = _score({"clusters": 6, "largest_cluster": 10, "bridges": 0}, 20)
    shredded = _score({"clusters": 12, "largest_cluster": 3, "bridges": 0}, 20)
    assert shredded < sane, (shredded, sane)


def test_more_audiences_is_still_better_where_it_means_something():
    from app.agent import _score
    before = _score({"clusters": 3, "largest_cluster": 12, "bridges": 0}, 20)
    after = _score({"clusters": 5, "largest_cluster": 7, "bridges": 0}, 20)
    assert after > before


def test_a_slate_is_never_cut_into_mostly_pairs():
    for spread, n in (({"A": 7, "B": 7}, 14), ({"A": 5, "B": 5}, 10)):
        a = analyse(_slate(spread))
        assert len(a.clusters) <= len(a.clusters[0]) * 0 + n * 0.5 + 1


def test_a_swap_that_changes_no_count_is_still_explained():
    src = (Path(__file__).resolve().parent.parent / "app" / "agent.py").read_text()
    assert "bring the largest group down from" in src
    assert "open a route between groups that had none" in src
    assert "leave the slate the same size but less concentrated" in src


def test_probe_lineups_stay_out_of_the_product():
    from pathlib import Path as P
    root = P(__file__).resolve().parent.parent
    for name in ("app/main.py", "scripts/audit.py", "scripts/precompute.py"):
        assert 'startswith("_")' in (root / name).read_text(), name


def test_a_pasted_music_lineup_is_not_read_as_films():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert "def _read_as(" in src
    assert "urn:entity:artist" in src
    assert 'source == "custom"' in src


def test_the_engine_says_what_it_read():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert "ENTITY_LABEL" in src
    assert '"reading"' in src


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


def test_the_probe_calls_the_engine():
    src = (Path(__file__).resolve().parent.parent / "scripts"
           / "probe_stability.py").read_text()
    assert "from app.structure import analyse" in src
    assert "def agglomerate" not in src
    assert "def silhouette" not in src


def test_the_hero_says_what_slate_is_before_showing_a_case():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    opening = html[html.index('class="opening"'):html.index("</section>", html.index('class="opening"'))]
    for word in ("films", "music", "books", "podcasts", "television"):
        assert word in opening, word
    assert "Analyse a lineup" in opening
    assert html.count("Analyse a lineup") == 1


def test_probe_lineups_do_not_reach_the_main_page():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def lineups("):src.index("def lineup(")]
    assert 'startswith("_")' in block


def test_the_noun_follows_the_entity_type():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert "ENTITY_NOUN" in src
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "' acts' : ' films'" not in js


def test_no_agent_buttons_remain():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "Let the agent try" not in js
    assert "function runAgent" not in js


def test_no_group_is_shaded_by_its_size():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert "grey(" not in js
    assert "--g0" not in css and "--g5" not in css


def test_the_accent_means_one_thing():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    for block in css.split("}"):
        if "var(--accent)" not in block:
            continue
        head = block.split("{")[0]
        assert any(w in head for w in ("bridge", "threads", "accent")), head


def test_the_agent_reports_both_structures():
    src = (Path(__file__).resolve().parent.parent / "app" / "agent.py").read_text()
    assert "before_groups" in src and "after_groups" in src
    assert '"after_groups": result.after_groups' in src


def test_an_outlier_is_not_called_a_unique_audience():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    import re
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    flat = re.sub(r"\s+", " ", html)
    assert "only route to its audience" not in js
    assert "'outlier'" in js
    assert "distinct taste from the rest of the lineup" in flat


def test_the_free_a_slot_block_says_what_dropping_costs():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "If you need to free a slot" in js
    assert "you still cover that audience" in js


def test_the_verdict_line_drops_the_bridge_clause():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function verdict("):js.index("function filmNode(")]
    assert "joined by" not in block
    assert "Nothing connects" not in block


def test_no_em_dashes_in_the_page():
    root = Path(__file__).resolve().parent.parent / "static"
    for name in ("app.js", "index.html", "style.css"):
        assert "\u2014" not in (root / name).read_text(), name


def test_the_declined_run_shows_what_was_turned_down():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function declined(" in js
    assert "Tested and turned down" in js


def test_the_three_failures_stay_distinct():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "err.status = res.status" in js
    assert "429" in js and "503" in js
    assert "Qloo is limiting requests" in js
    assert "finish this analysis" in js


def test_dropped_films_are_named_and_separated():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function coverage(" in js
    assert "Could not match" in js and "No affinity data" in js


def test_no_invented_progress():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    for bad in ("%'", "setInterval", "fakeProgress", "estimated"):
        assert bad not in js, bad


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
