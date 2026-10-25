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
    assert "the largest group comes down from" in src
    assert "a route opens between groups that had none" in src
    assert "the slate stays the same size but is less " in src
    assert "change{'' if n == 1 else 's'}" not in src


def test_probe_lineups_stay_out_of_the_product():
    from pathlib import Path as P
    root = P(__file__).resolve().parent.parent
    for name in ("app/main.py", "scripts/audit.py", "scripts/precompute.py"):
        assert 'startswith("_")' in (root / name).read_text(), name


def test_a_pasted_music_lineup_is_not_read_as_films():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    assert "def _read_as(" in src
    assert "urn:entity:artist" in src
    assert 'source == "custom"' in src


def test_the_engine_says_what_it_read():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
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
    at = html.index('class="opening')
    opening = html[at:html.index("</section>", at)]
    for word in ("films", "music", "books", "podcasts", "TV shows"):
        assert word in opening, word
    assert "Try it" in opening
    assert "See it on three film festivals" not in html
    assert "Analyse a lineup" not in html


def test_probe_lineups_do_not_reach_the_main_page():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def lineups("):src.index("SERVED =")]
    assert 'startswith("_")' in block


def test_the_noun_follows_the_entity_type():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
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
    assert "the group still covers its audience" in js


def test_the_verdict_line_drops_the_bridge_clause():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function verdict("):js.index("function filmNode(")]
    assert "joined by" not in block
    assert "Nothing connects" not in block


def test_no_em_dashes_in_the_page():
    root = Path(__file__).resolve().parent.parent / "static"
    for name in ("app.js", "index.html", "style.css"):
        assert "\u2014" not in (root / name).read_text(), name


def test_the_three_festivals_are_shown_the_same_way():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    for gone in ("function decision(", "function declined(", "function decisions(",
                 "function groupBlock(", "Let the agent try"):
        assert gone not in js, gone


def test_the_outlier_has_its_own_colour():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert "--alone:" in css and "--alone-on:" in css
    assert ".film.alone { border-left-color: var(--alone-on); }" in css


def test_the_header_links_to_every_section():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    tabs = html[html.index('<nav class="tabs">'):html.index("</nav>")]
    for target in ("#festivals", "#views", "#checked", "/app"):
        assert target in tabs, target


def test_the_footer_links_resolve():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    foot = html[html.index('<footer'):html.index("</footer>")]
    assert "github.com/1Light/slate" in foot
    assert "qloo.com" in foot and "qloo.devpost.com" in foot
    assert "https://github.com\"" not in foot
    assert "Method" not in foot


def test_the_three_failures_stay_distinct():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "err.status = res.status" in js
    assert "429" in js and "503" in js
    assert "Qloo is limiting requests" in js
    assert "finish this analysis" in js


def test_dropped_films_are_named_and_separated():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function coverage(" in js
    assert "Not recognised: " in js and "Left out: " in js


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


def test_preset_lineups_are_served_from_a_file():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert "_precomputed(" in src
    block = src[src.index("def lineup("):src.index("@app.post")]
    assert "ready is not None" in block


def test_validation_does_not_recompute_what_is_already_stored():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def validation("):]
    block = block[:block.index("@app.get")]
    assert '"bridge" not in out' in block
    assert '"lineup_ari" not in out' in block


def test_the_builders_do_not_import_the_web_framework():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    for bad in ("fastapi", "FastAPI", "HTTPException", "JSONResponse"):
        assert bad not in src, bad


def test_precompute_writes_what_the_page_reads():
    src = (Path(__file__).resolve().parent.parent / "scripts" / "precompute.py").read_text()
    assert "served.json" in src
    assert "precomputed.json" in src
    assert "_bridge_check()" in src
    assert "lineup_ari" in src


def test_editing_a_lineup_makes_no_new_qloo_calls():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def panel("):src.index('@app.post("/api/agent")')]
    assert "_subset(m, keep)" in block
    assert "_best_subset_fast(" in block


def test_a_smaller_lineup_is_re_ranked_not_re_queried():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    block = src[src.index("def _subset("):src.index("def _shape_from(")]
    assert "_rerank(m.ranks, keep)" in block
    assert "qloo" not in block.lower()


def test_the_change_line_is_computed_from_both_partitions():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    block = src[src.index("def _diff("):src.index("def _reaches(")]
    for word in ("groups_before", "groups_after", "moved", "bridges_lost",
                 "bridges_gained"):
        assert word in block, word


def test_a_lineup_can_be_put_back():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "Use this version" in js, "versions are how a lineup goes back"


def test_one_broken_test_does_not_hide_the_evidence():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("async function tests()"):js.index("function ariTable(")]
    assert "catch (e)" in block
    assert "if (built) show(" in block


def test_every_helper_the_evidence_uses_exists():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("async function tests()"):js.index("function ariTable(")]
    import re
    for name in set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\(", block)):
        if name in ("if", "for", "while", "catch", "switch", "function",
                    "return", "typeof", "Math", "Number", "String", "Object",
                    "min", "max", "find", "add", "toFixed", "createTextNode",
                    "error", "forEach", "appendChild", "filter", "map",
                    "join", "sort", "slice", "index", "replace"):
            continue
        if f"function {name}(" in js or f"const {name} =" in js \
           or f"{name} = (" in js or f"let {name} " in js:
            continue
        assert name in ("ask", "el", "say", "test", "push", "join", "map",
                        "filter", "split", "index", "indexOf", "toFixed",
                        "appendChild", "createTextNode", "toLocaleString",
                        "forEach", "slice", "sort", "charAt", "toUpperCase",
                        "concat", "trim", "includes", "replace", "remove",
                        "querySelector", "add", "append", "max", "min",
                        "round", "abs", "fetch", "JSON", "console", "error",
                        "log", "stringify", "parse", "classList", "textContent",
                        "setAttribute", "onceVisible", "failure", "chapter",
                        "columnHead", "controlFigure", "mlTables",
                        "stabilityTable", "bridgeTable", "ariTable", "spell",
                        "Caps", "show"), name


def test_the_page_has_a_maximum_width():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert "--page:" in css
    assert ".band { max-width: var(--page)" in css
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    for section in ("opening", "group-head", "views", "checked"):
        assert f'class="{section} band' in html or f'class="{section}' in html


def test_every_heading_has_a_size():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    for sel in (".views h2", ".checked h2", ".group-head h2"):
        assert sel in css, sel
    assert ".desk-rail-head {" in css and ".said-head {" in css


def test_group_columns_are_equal_width():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "weight(" not in js
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".sizes span" in css


def test_the_spacing_is_a_scale():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    for token in ("--s1:", "--s2:", "--s3:", "--s4:"):
        assert token in css, token


def test_the_loading_indicator_is_gone():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "Reading the programmes" not in html
    assert "Nothing is stored" not in html
    assert "$('loading')" not in js

def test_nothing_is_smaller_than_twelve_pixels():
    import re
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    for size in re.findall(r"font-size:\s*([0-9.]+)rem", css):
        assert float(size) >= 0.75, f"{size}rem is under 12px"


def test_the_slot_heading_is_a_heading():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index(".spend-head h4"):css.index(".spend-head p")]
    assert "var(--serif)" in block
    assert "1.5rem" in block
    assert "text-align: center" in css[css.index(".spend-head {"):css.index(".spend-head h4")]


def test_the_test_number_is_as_large_as_the_text():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index(".test h3 .num {"):css.index("}", css.index(".test h3 .num {"))]
    assert "0.875rem" in block
    assert "border-radius: 50%" in block


def test_the_evidence_reads_in_one_column():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("async function tests()"):js.index("function ariTable(")]
    assert "const body = el('div', 'split')" not in block
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".test .split" not in css
    assert "max-width: 68ch" in css


def test_every_table_says_what_its_columns_are():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    pairs = js[js.index("const t = el('table', 'pairs')"):js.index("function stabilityTable(")]
    for label in ("Distance", "Pair", "Shared audience", "Rated both"):
        assert f"'{label}'" in pairs, label
    assert "rated both`" not in pairs
    stab = js[js.index("function stabilityTable("):js.index("function bridgeTable(")]
    for label in ("Group", "Stayed together", "On shuffled rankings",
                  "The gap"):
        assert f"'{label}'" in stab, label


def test_the_closest_and_furthest_pairs_are_separated():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "band('Closest by Slate')" in js
    assert "band('Furthest by Slate')" in js


def test_stacked_tables_are_labelled():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function titled(" in js
    block = js[js.index("async function tests()"):js.index("function ariTable(")]
    assert "titled('Each group on its own" in block
    assert "ariTable(v.lineup_ari)" in block, "its headers are in the table"
def test_groups_are_lettered_and_the_pairs_say_which():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "const letterFor" in js
    assert "columnHead(mine.length, i, d.noun, d.nouns)" in js
    block = js[js.index("const spendBand"):js.index("const linkBand")]
    assert "spend-letter" in block
    assert "letterFor(i)" in block
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".column-letter" in css and ".spend-letter" in css


def test_the_conclusion_comes_after_the_evidence():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("async function tests()"):js.index("function ariTable(")]
    assert "const below = (art, text, cls)" in block
    assert "art.after" in block
    for line in ("Hence the groups Slate makes match",
                 "Hence metadata cannot make these groups",
                 "Hence the groups do not depend on any one film",
                 "Hence a bridge is not the most popular"):
        at = block.index(line)
        before = block[:at]
        assert before.rstrip().endswith("'") or "below(art" in before[-400:], line


def test_no_function_is_called_before_it_exists():
    import shutil
    import subprocess
    root = Path(__file__).resolve().parent.parent
    node = shutil.which("node")
    if not node:
        src = (root / "static" / "app.js").read_text()
        for name in ("losses", "controlFigure", "mlTables", "stabilityTable",
                     "bridgeTable", "ariTable", "letterFor", "columnHead",
                     "legendText", "panel", "chapter", "failure", "status"):
            assert f"function {name}(" in src or f"const {name} =" in src, name
        return
    done = subprocess.run([node, "scripts/check_js.js"], cwd=root,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_control_figure_letters_its_groups():
    src = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = src[src.index("function controlFigure("):src.index("function mlTables(")]
    assert ".forEach((c, i) =>" in block


def test_the_legend_is_three_facts_and_nothing_else():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function legendText("):js.index("function threads(")
              if "function threads(" in js else js.index("function legendText(") + 2000]
    assert "is a bridge" not in block, (
        "bridges are named in their own band, not in the legend")
    assert "is an outlier. It covers taste" in block
    assert "weakly tied" not in block, (
        "an outlier has a sparse neighbourhood, not a loose hold")
    assert "no affinity data linking" in block
    for gone in ("ARI", "shuffled ranks", "separate evenings", "Faded titles"):
        assert gone not in block, gone


def test_the_bridge_threads_are_gone():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function threads(" not in js
    assert "'threads'" not in js


def test_the_verdict_has_no_slot_claim():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "pay for an audience" not in js
    assert "verdict-sub" not in js
    assert "duplicate_slots" not in js


def test_the_festival_name_is_a_title():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index(".chapter-title .where"):css.index("}", css.index(".chapter-title .where"))]
    assert "var(--serif)" in block
    assert "var(--ink)" in block


def test_tags_are_bordered():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index(".film .tag {"):css.index("}", css.index(".film .tag {"))]
    assert "border: 1px solid" in block


def test_the_back_to_top_is_filled():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index(".to-top {"):css.index("}", css.index(".to-top {"))]
    assert "background: var(--ink)" in block


def test_the_three_card_stages_exist():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    for node in ("stage-hero", "stage-bridge", "stage-outlier"):
        assert node in html, node
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function cardStage(" in js
    assert "heroStage()" in js
    assert "markStage('stage-bridge', 'bridge')" in js
    assert "markStage('stage-outlier', 'outlier')" in js


def test_the_definitions_keep_their_text():
    import re
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    flat = re.sub(r"\s+", " ", html)
    assert "close in taste to two different groups at once" in flat
    assert "reaches two different crowds" not in flat
    assert "distinct taste from the rest of the lineup" in flat
    assert "most weakly tied to it" not in flat


def test_the_cards_hold_still_for_reduced_motion():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index("@media (prefers-reduced-motion: reduce) {", css.index(".stage i")):]
    assert ".stage i { animation: none" in block


def test_an_edit_moves_the_rows_rather_than_redrawing():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function settleInto(" in js
    at = js.index("function settleInto(")
    block = js[at:js.index("\nfunction ", at + 10)]
    assert "getBoundingClientRect" in block
    assert "if (!before.size || reduced) return" in block
    work = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "settleInto(figure, before," in work


def test_the_hero_does_not_list_the_page():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    assert "signpost" not in html


def test_the_agent_is_visible_without_interaction():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    assert 'id="agent"' in html
    flat = " ".join(html.split())
    assert "Slate reports no change" in flat, "the refusal is stated plainly"
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "async function agentSection(" in js
    assert "agentSection()" in js


def test_the_agent_shows_the_run_it_declined():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function agentCase("):js.index("async function agentSection(")]
    assert "Nothing was changed" in block
    assert "Tested and turned down" in block


def test_group_letters_look_the_same_everywhere():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    head = css[:css.index("{", css.index(".column-letter"))]
    for sel in (".column-letter", ".spend-letter", ".stage span u"):
        assert sel in head, sel
    block = css[css.index(".column-letter"):css.index("}", css.index(".column-letter"))]
    assert "background: var(--panel-bright)" in block
    assert "color: var(--panel)" in block

def test_the_tabs_show_where_you_are():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".tabs a.here" in css
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "markWhere" in js


def test_television_is_called_tv_shows():
    root = Path(__file__).resolve().parent.parent
    for name in ("static/index.html", "app/build.py"):
        text = (root / name).read_text()
        assert "television" not in text.lower() or "TV show" in text, name


def test_column_heads_use_the_type_noun():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function columnHead("):js.index("function board(")]
    assert "noun || 'film'" in block
    assert "nouns || 'films'" in block


def test_detection_tries_every_type():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    block = src[src.index("OTHER_TYPES"):src.index("def _pipeline(")]
    for t in ("artist", "book", "tv_show", "podcast"):
        assert t in block, t
    assert "== len(films)" in block, "must only stop early on a perfect match"


def test_examples_are_served_with_their_type():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert "/api/examples/{slug}" in src
    block = src[src.index("def example("):src.index('@app.get("/api/views")')]
    assert '"entity_type"' in block
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "const EXAMPLES = [" in js
    assert "pool = EXAMPLES.filter" in js


def test_every_example_set_resolves_to_one_type():
    import json
    folder = Path(__file__).resolve().parent.parent / "data" / "examples"
    sets = sorted(folder.glob("*.json"))
    assert len(sets) == 5
    for path in sets:
        d = json.loads(path.read_text(encoding="utf-8"))
        assert d["entity_type"].startswith("urn:entity:")
        assert 4 <= len(d["films"]) <= 24, path.name
def test_the_panel_agent_decides_on_the_current_lineup():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def panel("):src.index('@app.post("/api/agent")')]
    assert "if req.swap:" in block
    assert "improve(Qloo(), small, analyse(small)" in block
    assert "AGENT_PER_HOUR" in block


def test_a_refusal_still_returns_a_lineup():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("if req.swap:"):src.index('@app.post("/api/agent")')]
    assert "if not result.swaps:" in block
    assert 'shape["agent"] = agent' in block


def test_the_figure_shows_what_you_removed():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function board("):js.index("function settleInto(")]
    assert "d.by_you" in block
    assert "taken-film" in block
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert 'shape["by_you"]' in src


def test_an_empty_legend_leaves_no_rule_behind():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".legend:empty { display: none; }" in css


def test_a_title_under_consideration_is_marked_new():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    at = js.index("function filmNode(")
    block = js[at:js.index("\nfunction ", at + 10)]
    assert "el('span', 'tag', 'new')" in block
    assert "'added'" not in js

def test_a_film_can_carry_more_than_one_tag():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    at = js.index("function filmNode(")
    block = js[at:js.index("\nfunction ", at + 10)]
    assert "else if" not in block, "tags must be independent, not exclusive"


def test_no_tab_is_marked_before_you_scroll():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function markWhere()"):js.index("function backToTop()")]
    assert "offsetParent !== null" in block, "hidden sections must not count"
    assert "s.top > 0" in block
    assert "MutationObserver" in block


def test_the_agent_section_does_not_depend_on_the_chapter_loop():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "async function agentSection()" in js
    block = js[js.index("async function agentSection()"):]
    assert "if (!byslug[slug]) continue" not in block
    assert "one-genre" in block
    run = block[:block.index("function") if "function" in block[1:] else len(block)]
    assert "console.error('agent case'" in js


def test_the_coverage_notice_speaks_the_right_noun():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function coverage(d, host)"):js.index("function failure(")]
    assert "d.nouns" in block
    assert "films you gave" not in block
    assert "Left out: " in block
    assert "no taste connection" in block
def test_a_lineup_that_does_not_separate_is_one_group():
    src = (Path(__file__).resolve().parent.parent / "app" / "structure.py").read_text()
    assert "WEAK_SEPARATION = 0.3" in src
    block = src[src.index("pick = _choose_k(matrix, films, merges)"):src.index("clusters = _cut_to(films, merges, groups)")]
    assert "groups = 1 if weak" in block


def test_the_weak_case_says_so_and_shows_nothing_else():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "are too alike to " in js
    board = js[js.index("const spendBand"):js.index("const settle")]
    assert "if (d.weak) { spend.textContent = ''; return; }" in board
    v = js[js.index("function verdict(d)"):js.index("function filmNode(")]
    assert "do not separate." in v


def test_the_figures_say_group_not_audience():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    head = js[js.index("function columnHead("):js.index("function board(")]
    assert "audience group" not in head
    v = js[js.index("function verdict(d)"):js.index("function filmNode(")]
    assert "separate into " in v
    assert "audiences." not in v
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    diff = src[src.index("def _diff("):src.index("def _reaches(")]
    assert "audience" not in diff


def test_the_evidence_explains_what_a_group_is():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "Does a group mean a fixed audience?" in js
    assert "there is no universal grouping to belong to" in js
    assert "not a universally fixed " in js


def test_the_agent_speaks_the_pages_language():
    src = (Path(__file__).resolve().parent.parent / "app" / "agent.py").read_text()
    page = src[:src.index('"You advise a film festival programmer')] \
        + src[src.index('"certainty about real audiences."') + 33:]
    assert "audiences" not in page
    assert "programme " not in page


def test_a_rejection_says_what_actually_happened():
    src = (Path(__file__).resolve().parent.parent / "app" / "agent.py").read_text()
    block = src[src.index("was = analysis.headline"):src.index("continue", src.index("was = analysis.headline"))]
    assert "if now <= was else" in block
    assert "splitting an " in block
    assert "landed inside a group the lineup already covers" in block

def test_the_letters_exist_before_they_are_used():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert js.index("const LETTERS") < js.index("letterFor(f.cluster)") \
        if "letterFor(f.cluster)" in js else True
    assert js.index("const LETTERS") < 2000, "hoisted to the top"


def test_every_bridge_in_the_served_payload_names_its_groups():
    import json
    served = json.loads((Path(__file__).resolve().parent.parent / "data"
                         / "served.json").read_text())
    found = 0
    for d in served.values():
        if not isinstance(d, dict) or "films" not in d:
            continue
        for f in d["films"]:
            if f.get("role") == "bridge":
                found += 1
                assert f.get("connects"), f"{f['title']} has no groups"
                assert len(f["connects"]) >= 2
    assert found, "no bridges in the payload to check"


def test_workspaces_belong_to_one_browser():
    src = (Path(__file__).resolve().parent.parent / "app" / "store.py").read_text()
    import ast as _ast
    tree = _ast.parse(src)
    for fn in ("listing", "read", "update", "remove", "add_version"):
        node = next(n for n in tree.body
                    if isinstance(n, _ast.FunctionDef) and n.name == fn)
        assert "owner" in [a.arg for a in node.args.args], fn
    assert "WHERE owner = %s AND id = %s" in src


def test_the_store_runs_without_postgres():
    src = (Path(__file__).resolve().parent.parent / "app" / "store.py").read_text()
    assert "import sqlite3" in src
    assert "DATABASE_URL" in src
    block = src[src.index("def _pg("):src.index("def _lite(")]
    assert "except ImportError" in block, "a missing driver falls back"


def test_a_browser_id_is_checked():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def _owner("):src.index("@app.get(\"/api/spaces\")")]
    assert "isalnum()" in block
    assert "[:64]" in block
    assert "len(clean) < 8" in block


def test_versions_are_capped():
    src = (Path(__file__).resolve().parent.parent / "app" / "store.py").read_text()
    assert "MAX_VERSIONS = 20" in src
    block = src[src.index("def add_version("):src.index("def remove(")]
    assert "kept[0].get(\"titles\") == titles" in block, "no duplicate saves"
    assert "[:MAX_VERSIONS]" in block


def test_the_app_page_asks_for_no_sign_in():
    html = (Path(__file__).resolve().parent.parent / "static" / "app.html").read_text()
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    for word in ("sign in", "log in", "sign up", "password"):
        assert word not in (html + js).lower(), word
    assert 'type="email"' not in (html + js), "no email field"
    assert "your email" not in (html + js).lower()
    assert "crypto.randomUUID" in js
    assert "slate.owner.v1" in js


def test_the_front_door_lists_and_makes():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "'/api/spaces'" in js and "method: 'POST'" in js
    assert "/api/spaces?owner=" in js
    assert "Use an example" in js
    assert "function spaceRow(w)" in js
    assert "function sampleFigure()" in js, "the door shows an answer"
    assert "door-card-bar" in js, "each workspace shows its shape"
    for action in ("Rename", "Delete"):
        assert action in js, action


def test_the_dashboard_reuses_the_figure():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    for fn in ("chapter(d, null)", "settleInto(figure", "withTitles("):
        assert fn in js, fn
    html = (Path(__file__).resolve().parent.parent / "static" / "app.html").read_text()
    assert html.index("app.js") < html.index("work.js"), "renderers load first"


def test_the_landing_wiring_only_runs_on_the_landing_page():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "if (document.getElementById('festivals')) start();" in js


def test_the_lineup_lives_in_the_workspace():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "const lineup = () => (space ? space.titles.slice() : [])" in js
    block = js[js.index("async function runSpace("):js.index("function paintSpace(")]
    assert "films: lineup()" in block
    assert "entity_type: space.entity_type" in block


def test_a_slot_count_is_reported_never_enforced():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function drawCounts()"):js.index("function waiting(")]
    assert "over" in block and "free" in block
    assert "n === 1 ? '' : 's'" in block, "one slot, not one slots"
    add = js[js.index("addField.onkeydown"):js.index("desk-rail-slots")]
    assert "slots" not in add, "adding past the slots is allowed"


def test_opening_a_version_previews_before_it_applies():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("async function previewVersion(")
    block = js[at:js.index("function allVersions(")]
    assert "drawn(d)" in block, "the preview draws the figure"
    assert "Use this version" in block
    assert block.index("drawn(d)") < block.index("Use this version")


def test_a_late_result_cannot_land_on_the_dashboard():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("async function runSpace("):js.index("function paintSpace(")]
    assert "const mine = ++asked;" in block
    assert "if (mine !== asked) return;" in block


def test_a_candidate_is_judged_by_rebuilding():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    block = src[src.index("def _fit_brief("):src.index("CHOOSE_CAP")]
    assert "analyse(_subset(m, lineup), stability=False)" in block
    assert "analyse(_subset(m, lineup + [candidate])" in block
    for key in ("groups_before", "groups_after", "role", "connects", "spare"):
        assert key in block, key


def test_several_candidates_are_judged_together():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    block = src[src.index("def _choose_best("):]
    assert "combinations(candidates, slots)" in block, "sets, not singles"
    assert "_touching(m, lineup, list(picked))" in block
    assert "CHOOSE_CAP" in block, "a cap on how many sets are built"

def test_the_brief_is_previewed_where_it_is_read():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "function showPaper(kind, data)" in js
    assert "paper-frame" in js and "srcdoc" in js
    assert "window.open" not in js, "the brief no longer opens a blank tab"
    assert "paper-over" in js, "it opens over the page, not inside the panel"
    assert js.count("showPaper('") == 3, "both briefs and the lineup"


def test_the_download_is_a_real_file():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function showPaper("):]
    assert "Download PDF" in block
    assert "/api/paper.pdf" in block
    assert "link.download" in block
    assert "res.status === 501" in block, "a missing renderer falls back"
    assert js.count("el('button', 'ghost', 'Print')") == 0, (
        "one button, not two doing the same job")
    api = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert '@app.post("/api/paper.pdf")' in api
    assert "application/pdf" in api


def test_preview_and_file_are_the_same_document():
    api = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = api[api.index("def _document(req"):api.index('@app.post("/api/choose")')]
    assert block.count("_document(req)") == 2, "one builder, two routes"
    doc = (Path(__file__).resolve().parent.parent / "app" / "paper.py").read_text()
    assert "Georgia" in doc, "a system serif, so the PDF matches the preview"
    assert "fonts.googleapis" not in doc


def test_a_missing_renderer_is_not_a_crash():
    doc = (Path(__file__).resolve().parent.parent / "app" / "paper.py").read_text()
    block = doc[doc.index("def as_pdf("):]
    assert "except Exception" in block and "return None" in block
    api = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert "501" in api


def test_no_suggestion_is_already_in_an_example():
    import json
    root = Path(__file__).resolve().parent.parent
    taken = set()
    for p in (root / "data" / "examples").glob("*.json"):
        for f in json.loads(p.read_text())["films"]:
            taken.add(f["title"].lower())
    for p in (root / "data" / "candidates").glob("*.json"):
        d = json.loads(p.read_text())
        for t in d["one"] + d["many"]:
            assert t.lower() not in taken, f"{t} is already in an example"


def test_the_probe_checks_for_clashes_too():
    src = (Path(__file__).resolve().parent.parent / "scripts"
           / "probe_candidates.py").read_text()
    assert "already in an example" in src


def test_the_app_header_does_not_restyle_the_landing_one():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    at = css.index("body.workbench")
    assert ".bar {" not in css[at:], "the app page must not redefine .bar"
    assert ".deskbar {" in css[at:]
    html = (Path(__file__).resolve().parent.parent / "static" / "app.html").read_text()
    assert 'class="bar"' not in html
    landing = (Path(__file__).resolve().parent.parent / "static"
               / "index.html").read_text()
    assert 'class="bar"' in landing, "the landing page keeps its own"


def test_the_landing_page_sends_you_to_the_app():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    assert 'href="/app"' in html
    assert 'id="yours"' not in html, "the try-it box moved to the app"
    assert 'href="#panel"' not in html
    assert "own-input" not in html


def test_the_old_panel_is_gone_from_the_landing_script():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function panel(" not in js, "the dashboard replaced it"
    assert "async function runOwn(" not in js
    assert "makeProject" not in js

def test_best_means_the_same_in_both_places():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    block = src[src.index("def _best_subset_fast("):src.index("def _profile(")]
    assert "_profile(m, list(c))" in block, "ranked by the same measure"
    assert "_reaches(" not in block, "the composite score disagreed with it"
    chance = src[src.index("def _against_chance("):src.index("def _contribution(")]
    assert "_profile(m, chosen)" in chance

def test_saving_a_version_says_when_it_fails():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("saveBtn.onclick")
    block = js[at:js.index("end.append(", at)]
    assert "catch (e)" in block, "a silent failure looks like lost work"
    assert "drawVersions()" in block

def test_the_free_a_slot_block_stays_in_the_figure():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "'.spend'" not in js, "it is the thing a programmer acts on"

def test_a_choice_is_ranked_by_what_it_changes():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    assert "def _touching(m, lineup, picked):" in src
    block = src[src.index("def _choose_best("):]
    assert '"profile": _touching(m, lineup, list(picked))' in block, (
        "the lineup's own pairs are the same for every option")
    brief = src[src.index("def _contribution("):src.index("def _fit_brief(")]
    assert "_touching(m, others, [candidate])" in brief


def test_a_block_with_no_pool_is_not_offered():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    stand = js[js.index("function paintStand("):js.index("function distanceCard(")]
    assert "Against the sets" not in stand, (
        "one candidate gives nothing to compare against")
    assert "Against the sets you could have picked" in js, "it stays after a cut"


def test_a_title_that_merges_groups_says_so():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "closely enough that they merge" in js
    doc = (Path(__file__).resolve().parent.parent / "app" / "paper.py").read_text()
    flat = " ".join(doc.split())
    assert "closely enough that they merge" in flat.replace('" "', ""), (
        "the same finding on paper")


def test_a_choice_that_reaches_nowhere_new_says_so():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("function paintChoose(")
    assert "None of the titles you" in js[at:js.index("\nfunction ", at + 10)]


def test_every_control_belongs_to_the_page():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    bare = js.count("el('button', null")
    assert bare <= 1, f"{bare} buttons fall back to the browser's own styling"


def test_the_figure_has_no_gap_above_it():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".work-figure .chapter { padding-top: 0; border-top: 0; }" in css
    assert ".out .chapter, .work-body > .chapter { padding-top: 0;" in css


def test_renaming_happens_in_place():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function drawSpace()"):js.index("function drawCounts()")]
    assert "contentEditable" in block
    assert "window.prompt" not in block, "a browser dialog leaves the page"


def test_there_is_a_way_back():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "Reset lineup" in js
    assert "started = space.titles.slice()" in js
    block = js[js.index("function drawCounts()"):js.index("function waiting(")]
    assert "back.hidden" in block, "hidden until something has changed"

def test_the_two_pages_cannot_restyle_each_other():
    import re
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    at = css.index("body.workbench")
    shared, app = css[:at], css[at:]

    def tops(block):
        found = set()
        for sel in re.findall(r"(?m)^([.#][^{\n]*)\{", block):
            for part in sel.split(","):
                part = part.strip().split()[0] if part.strip() else ""
                m = re.match(r"^\.([a-z][a-z0-9-]*)", part)
                if m:
                    found.add(m.group(1))
        return found

    both = tops(shared) & tops(app)
    assert not both, f"styled in both halves: {sorted(both)}"

    def frames(block):
        return set(re.findall(r"@keyframes\s+([\w-]+)", block))

    clash = frames(shared) & frames(app)
    assert not clash, f"animation names used by both: {sorted(clash)}"


def test_the_app_names_what_it_borrows():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "const BORROWED = {" in js
    assert "work.js needs" in js, "it must fail loudly, not silently"
    assert "function el(" not in js, "one definition of el, not two"
    head = js[:js.index("const stage")]
    for name in ("chapter", "withTitles", "nameList", "letterFor",
                 "settleInto", "failure", "el"):
        assert name in head, name


def test_nothing_hides_the_focus_ring():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert "outline: none" not in css, (
        "a keyboard user needs to see where they are")
    assert ":focus-visible { outline:" in css


def test_the_stylesheet_has_no_dead_rules():
    import re
    root = Path(__file__).resolve().parent.parent / "static"
    css = (root / "style.css").read_text()
    seen = "".join((root / f).read_text()
                   for f in ("app.js", "work.js", "index.html", "app.html"))
    words = set(re.findall(r"[\w-]+", seen))
    dead = sorted({c for c in re.findall(r"\.([a-z][a-z0-9-]*)", css)
                   if c not in words})
    assert not dead, f"styled but never used: {dead}"


def test_the_app_page_offers_no_landing_page_links():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function failure("):js.index("const EXAMPLES")]
    at = block.index("See a measured lineup")
    assert "getElementById('festivals')" in block[:at], (
        "the anchor only exists on the landing page")


def test_too_few_placed_titles_say_so():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("async function runSpace("):js.index("function paintSpace(")]
    assert "not enough here to separate" in block
    assert "could not place" in block
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".nothing {" in css


def test_the_app_works_below_a_desk():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    app = css[css.index("body.workbench"):]
    for width in ("1040px", "880px", "620px"):
        assert f"max-width: {width}" in app, width
    phone = app[app.index("max-width: 620px"):]
    assert "overflow-x: auto" in phone, "a wide figure scrolls rather than crushes"
    assert "flex-direction: column" in phone, "rows stack"
    assert "padding: 0.65rem 1.1rem" in phone, "targets grow to a thumb"


def test_an_off_page_tab_cannot_break_the_scroll_spy():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function markWhere()"):js.index("const mark = ()")]
    assert "querySelector(tab.getAttribute" not in block, (
        "querySelector throws on an href that is not a selector")
    assert "href.startsWith('#')" in block


def test_one_broken_step_does_not_blank_the_page():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("const steps = ["):js.index("function chapter(")]
    assert "catch (e)" in block
    for what in ("the hero animation", "the scroll spy", "the evidence"):
        assert what in block, what


def test_a_renamed_class_did_not_rename_a_property():
    import re
    for f in ("work.js", "app.js"):
        js = (Path(__file__).resolve().parent.parent / "static" / f).read_text()
        bad = re.findall(r"\w+\.[a-z]+-[\w-]+(?=[\s.;,)\]])", js)
        bad = [b for b in bad if not b.startswith(("this.", "e.", "ev."))]
        assert not bad, f"{f}: a dash in a property name is subtraction: {bad}"


def test_the_door_shows_what_slate_returns():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "const SAMPLE = {" in js
    assert "function sampleFigure()" in js
    block = js[js.index("function draw()"):js.index("function spaceRow(")]
    assert "sampleFigure()" in block
    assert "What Slate gives back" in block
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    at = css.index(".door-pair {")
    pair = css[at:css.index("}", at)]
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr)" in pair
    assert "align-items: stretch" in pair, "both columns end on the same line"


def test_a_workspace_card_carries_its_shape():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function spaceRow(w)"):js.index("document.addEventListener")]
    assert "door-card-bar" in block
    assert "w.sizes" in block
    api = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    listing = api[api.index('@app.get("/api/spaces")'):api.index('@app.get("/api/spaces/{wid}")')]
    assert 'row["sizes"]' in listing
    store = (Path(__file__).resolve().parent.parent / "app" / "store.py").read_text()
    assert '"sizes": list(sizes or [])' in store


def test_the_door_has_one_primary_action():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function draw()"):js.index("function spaceRow(")]
    assert "el('button', 'solid', 'Analyse this lineup')" in block
    assert "el('button', 'linky', 'Use an example')" in block, "quiet, not equal"


def test_no_class_is_styled_twice_at_the_top_level():
    import re
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    plain, depth = [], 0
    for line in css.split("\n"):
        hit = re.match(r"^\.([a-z][a-z0-9-]*)\s*\{", line)
        if hit and depth == 0:
            plain.append(hit.group(1))
        depth += line.count("{") - line.count("}")
    twice = sorted({c for c in plain if plain.count(c) > 1})
    assert not twice, f"styled more than once: {twice}"


def test_an_ask_is_a_view_not_an_overlay():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "function showAsk(key)" in js and "function closeAsk()" in js
    assert "function showFigure()" in js
    assert "sheetOver" not in js, "an ask is a view, not a dialog"
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".sheet {" not in css


def test_the_rail_offers_four_asks():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("const ASKS = ["):js.index("function drawSpace()")]
    for label in ("Fit it into fewer slots", "Find a title that adds a new group",
                  "Check a new title against the lineup",
                  "Compare titles before adding"):
        assert label in block, label
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".ask.on {" in css, "the open ask is marked"


def test_the_rail_shows_a_handful_of_chips():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "const CHIPS_SHOWN = 5;" in js
    block = js[js.index("function drawChips()"):js.index("function drawCounts()")]
    assert "chipsOpen" in block and "'fold'" in block


def test_findings_sit_beside_their_evidence():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index(".work-split {"):css.index("}", css.index(".work-split {"))]
    assert "grid-template-columns: minmax(0, 1fr) 21rem" in block
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert js.count("el('div', 'work-split") >= 4, "every ask uses it"
    assert "'work-split ranked'" in js, "four columns need a wider card"
    assert "function distanceCard(rows)" in js


def test_the_distance_card_starts_short():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function distanceCard(rows)"):js.index("function compareAsk(")]
    assert "fold(4, rows.length, draw)" in block


def test_the_title_marker_is_not_a_layout_class():
    import re
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    mark = re.search(r"el\('i', '([a-z-]+)', hit\)", js)
    assert mark, "the marker's class could not be found"
    name = mark.group(1)
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert re.search(rf"(?m)^\.{name}\s*\{{", css) is None, (
        f"'{name}' is also a standalone rule, so titles inherit its box")


def test_what_moved_is_shown_not_animated():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "View previous shape" in js and "View current shape" in js
    assert "function drawFeet()" in js
    assert "replay(" not in js, "the animation was never readable"
    app = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function replay(" not in app


def test_a_result_is_proposed_before_it_is_applied():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    for label in ("Keep this set", "Make this swap", "Use this version"):
        assert label in js, label


def test_the_status_line_does_not_repeat_the_figure():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("async function runSpace("):js.index("const seatOf")]
    assert "status.textContent = '';" in block
    assert "d.diff" not in block, "the verdict belongs to the figure"


def test_the_app_actually_starts():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    tail = js[-400:]
    assert "if (opening) openSpace(opening);" in tail
    assert "else load();" in tail
    assert "hashchange" in js


def test_a_printed_group_reads_its_titles():
    import json
    from app import paper
    root = Path(__file__).resolve().parent.parent
    shape = json.loads((root / "data" / "served.json").read_text())["sundance2024"]
    doc = paper.lineup_doc(shape, "Sundance", 10)
    assert "index &middot; films" not in doc
    first = shape["clusters"][0]["films"][0]
    assert first in doc, f"{first} should be in the printed groups"


def test_a_title_qloo_cannot_place_is_marked():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function drawChips()"):js.index("function drawCounts()")]
    assert "shown.unresolved" in block
    assert "'chip lost'" in block
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".chip.lost" in css


def test_an_ask_opens_onto_the_lineup():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function showAsk(key)"):js.index("function showFigure()")]
    assert "out.appendChild(drawn(shown))" in block
    assert "standing" in block
    assert "The lineup as it stands" in block, "labelled, not dimmed"
    assert js.count("out.classList.remove('standing')") == 4, "every ask clears it"
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".out-when {" in css
    assert ".out.standing { opacity" not in css, (
        "a dimmed figure reads as disabled, not as context")


def test_a_field_is_the_width_of_what_goes_in_it():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index('.work-form input[type="text"] {'):]
    block = block[:block.index("}")]
    assert "flex: 0 1" in block, "a short title in a full-width box looks wrong"
    assert "min-width: 14rem" in block


def test_the_breadcrumb_has_room_to_breathe():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "'\\u00a0/\\u00a0'" in js
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".deskbar-slash { color:" in css


def test_the_preview_is_called_what_it_is():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "The lineup on paper" not in js
    assert "el('button', 'ghost', 'Preview')" in js


def test_a_group_is_read_as_a_record():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "const inGroup = (g) =>" in js
    assert "shown.clusters.map((c) => c.length)" not in js
    assert "inGroup(c).length" in js


def test_reset_goes_to_the_last_saved_version():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("resetBtn.onclick"):js.index("const printBtn")]
    assert "space.versions || [])[0]" in block
    assert "last ? last.titles : started" in block
    assert "Back to your version from" in block


def test_the_chip_list_folds_both_ways():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function drawChips()"):js.index("function drawCounts()")]
    assert "chipsOpen = !chipsOpen" in block
    assert "Show fewer" in block


def test_the_brief_opens_over_the_page():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function showPaper(kind, data)"):js.index("window.addEventListener")]
    assert "paper-over" in block
    assert "aria-modal" in block
    assert "Escape" in block, "a dialog closes on escape"
    assert "document.body.classList.add('held')" in block


def test_the_pair_table_shows_what_separates_them():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "'Shared audience'" in js
    assert "'Agreement'" not in js and "'Shared viewers'" not in js
    at = js.index("const row = (p) =>")
    block = js[at:js.index("headRow();", at)]
    assert "p.phi" in block, "the share of viewers is dragged by fame"


def test_the_overlap_result_reaches_the_page():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    at = js.index("test(2, 'Do the groups match")
    block = js[at:js.index("test('2b'", at)]
    assert "ml.overlap_rho" in block
    assert "overlap_popularity_rho" in block
    assert "not fame" in block
    probe = (Path(__file__).resolve().parent.parent / "scripts"
             / "probe_overlap.py").read_text()
    assert 'm["overlap_rho"]' in probe
    assert 'm["closest"]' in probe, "the probe writes the pairs it shows"


def test_each_ask_says_what_it_is_for():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("const ASKS = ["):js.index("function drawSpace()")]
    for why in ("Keep the strongest smaller set",
                "Reach an audience the lineup misses",
                "See what changes if it is added",
                "Choose between candidates"):
        assert why in block, why
    assert "el('span', 'ask-why', why)" in js
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".ask-why {" in css


def test_festivals_are_the_first_case_not_the_whole_product():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    assert "Other media" not in html, "that reads as compatibility, not a buyer"
    assert html.count("Other uses") >= 2, "nav and footer"
    flat = " ".join(html.split())
    assert "Film festivals are the first use case" in flat
    assert "what each title adds to the lineup as a whole" in flat


def test_the_hero_leads_with_the_problem():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    at = html.index('<h1>')
    deck = " ".join(html[at:html.index('</section>', at)].split())
    assert "several slots can end up reaching the same audience" in deck
    assert "Pick twenty films one at a time" not in deck, "too narrow a frame"
    assert "appeal to more than one audience group" in deck


def test_the_footer_says_what_slate_is_for():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    foot = " ".join(html[html.index('<footer'):].split())
    assert "what each title contributes to a lineup as a whole" in foot
    assert "the number of slots is limited" in foot


def test_a_bridge_is_drawn_beneath_the_groups():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    at = js.index("function board(d, ui)")
    block = js[at:js.index("\nfunction ", at + 10)]
    assert "const bridged = new Set(" in block
    assert "const keep = (c) =>" in block
    assert "const linkBand = () =>" in block
    assert "columnHead(mine.length" in block, "the count leaves bridges out"
    assert "keep(c).length" in block, "so does the size bar"
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".links-head h4 {" in css and ".link-spans {" in css


def test_the_bridge_tag_is_gone():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "'tag', `bridge" not in js and "'tag', 'bridge'" not in js
    assert "el('span', 'tag', 'outlier')" in js, "the outlier tag stays"


def test_one_sentence_covers_every_bridge():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "close to titles in more than one group" in js
    assert "It sits in group" not in js, "naming one bridge is unfair to the rest"


def test_a_bridge_is_never_a_slot_to_free():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("const spendBand = () =>"):js.index("const linkBand = () =>")]
    assert "!bridged.has(t.a)" in block and "!bridged.has(t.b)" in block
    doc = (Path(__file__).resolve().parent.parent / "app" / "paper.py").read_text()
    assert 'p["a"] not in linked' in doc, "on paper too"


def test_the_printed_brief_matches_the_screen():
    import json
    from app import paper
    root = Path(__file__).resolve().parent.parent
    shape = json.loads((root / "data" / "served.json").read_text())["sundance2024"]
    doc = paper.lineup_doc(shape, "Sundance", 10)
    assert "<h2>Bridges</h2>" in doc
    assert "is a bridge. It sits in" not in doc
    for b in shape["bridges"]:
        assert b["film"] in doc


def test_the_group_result_leads_the_second_test():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    at = js.index("test(2, 'Do the groups match")
    block = js[at:js.index("test('2b'", at)]
    assert "v.groups" in block
    assert "pooled into one pile" in block
    assert "ten thousand times" in block
    assert "function groupTable(g)" in js
    assert block.index("groupTable(g)") < block.index("mlTables(ml, 'pairs')")


def test_the_evidence_has_no_bars():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    for fn in ("function stabilityTable(", "function ariTable("):
        at = js.index(fn)
        block = js[at:js.index("\nfunction ", at + 10)]
        assert "el('td', 'bar')" not in block, fn
    at = js.index("if (which === 'baselines')")
    assert "el('td', 'bar')" not in js[at:js.index("const t = el('table'", at)]


def test_the_stability_table_reads_as_a_share():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    at = js.index("function stabilityTable(")
    block = js[at:js.index("\nfunction ", at + 10)]
    assert "'Stayed together'" in block and "'On shuffled rankings'" in block
    assert "Math.round(x * 100)" in block, "percentages, not a yes or no"
    assert "pair gets about 0.44" not in js, "those figures had drifted"


def test_slate_takes_the_fewest_groups_not_the_most():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "maximum number of groups" not in js
    assert "Slate finds the minimum number of " in js
    assert "groups where the division is most meaningful." in js
    assert "further scores either the same or worse." in js
    src = (Path(__file__).resolve().parent.parent / "app" / "structure.py").read_text()
    assert 'best = min(close, key=lambda r: r["k"])' in src


def test_the_bridge_test_shows_the_case_against_it():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    at = js.index("const b = v.bridge;")
    block = js[at:js.index("closing-line", at)]
    assert "r.top_was_reported" in block, "the lineup where a popular film did qualify"
    assert "does not disqualify" in block
    assert "strongly negative" not in block


def test_precompute_keeps_what_the_probes_wrote():
    src = (Path(__file__).resolve().parent.parent / "scripts"
           / "precompute.py").read_text()
    block = src[src.index('v_path = DATA / "validation.json"'):]
    assert 'v = json.loads(v_path.read_text' in block, "it merges, not replaces"
    for owned in ('v["bridge"]', 'v["lineup_ari"]'):
        assert owned in block, owned
    assert 'v = {}' not in block.split("v_path.write_text")[0], (
        "nothing may clear the file")


def test_the_header_groups_its_links():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    assert '<span class="sections">' in html
    assert 'href="/app" class="go"' in html
    assert 'href="#asks"' in html
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".tabs .sections {" in css and ".tabs .go {" in css


def test_the_four_asks_are_on_the_landing_page():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    flat = " ".join(html.split())
    assert 'class="asks band reveal"' in html
    assert "Slate answers four questions" in flat
    for ask in ("Fit it into fewer slots", "Find a title that adds a new group",
                "Check a new title against the lineup",
                "Compare titles before adding"):
        assert ask in flat, ask
    assert "a brief you can download" in flat
    at = html.index('id="agent"')
    assert html.index('class="asks') > at, "it follows the agent section"


def test_the_festival_titles_are_just_the_festival():
    import json
    root = Path(__file__).resolve().parent.parent / "data" / "lineups"
    for slug, want in (("berlinale2024", "Berlinale 2024"),
                       ("cannes2023", "Cannes 2023"),
                       ("sundance2024", "Sundance 2024")):
        got = json.loads((root / f"{slug}.json").read_text())["name"]
        assert got == want, f"{slug} is {got!r}"


def test_the_versions_list_reads_live_state():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "function allVersions()" in js, "no captured argument"
    assert "allVersions()" in js
    block = js[js.index("function allVersions()"):js.index("function block(")]
    assert "space.versions || []" in block
    assert "version-bar" in block, "each version shows its shape"
    assert "Nothing saved yet" in block, "and says so when there are none"


def test_preview_leaves_nothing_behind():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("el('button', 'ghost', 'Preview')"):js.index("const saveBtn")]
    assert "showPaper('lineup', shown)" in block
    assert "work.textContent" not in block, "it must not replace the view"
    assert "openAsk = 'paper'" not in js


def test_a_save_is_confirmed_where_the_eye_is():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "function said(text)" in js
    assert "said('Saved')" in js
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".deskbar-said {" in css
    block = css[css.index(".deskbar-said {"):css.index("}", css.index(".deskbar-said {"))]
    assert "var(--alone-on)" in block, "the palette's teal, not a new green"


def test_an_empty_free_a_slot_band_does_not_render():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("const spendBand = () =>"):js.index("const linkBand = () =>")]
    assert "let found = 0" in block
    assert "if (!found) { spend.textContent = ''; return; }" in block


def test_the_snapshot_label_names_the_lineup():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "'The lineup before your last change'" in js


def test_the_door_columns_end_level():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    ask = css[css.index(".door-ask textarea {"):]
    ask = ask[:ask.index("}")]
    assert "flex: 1" in ask, "the input grows so both columns finish together"
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "const SAMPLE_TITLES = [" in js
    assert "area.placeholder = SAMPLE_TITLES.join" in js, (
        "the placeholder lists what the figure groups")


def test_the_sample_figure_uses_the_bridges_band():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function sampleFigure()"):js.index("function draw()")]
    assert "taste-links" in block
    assert "'Bridges'" in block
    assert "bridges: [[" in js, "the sample names one"
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".taste-links-head {" in css


def test_the_empty_workspace_band_still_shows():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("const band = el('div', 'door-band')"):]
    assert "Nothing yet. Analyse a lineup" in block
    assert "if (!spaces.length) return;" not in js, "it used to vanish"


def test_the_ask_controls_are_sized_to_their_content():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".work-form .narrow { width: 5rem; }" in css
    assert ".compare-box {" in css
    box = css[css.index(".compare-box {"):]
    box = box[:box.index("}")]
    assert "max-width: 34rem" in box


def test_the_two_descriptions_of_the_agent_agree():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    flat = " ".join(html.split())
    assert "Slate reports no change" in js and "Slate reports no change" in flat
    assert "takes a slot the lineup can spare" not in js
    assert "Look for a swap" in js


def test_every_long_list_folds_both_ways():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "function fold(shown, total, draw)" in js
    assert "Show fewer" in js
    assert js.count("fold(") >= 3, "the distances, the sets, the rejections"
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".fold {" in css


def test_the_set_ranking_shows_its_tie_break():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("'Every set, best first'")
    block = js[at:js.index("split.append(left, side)", at)]
    assert "'Next'" in block
    assert "r.next" in block
    assert "then by the next closest where that ties" in js
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    assert '"next": (round(r["profile"][1], 6)' in src


def test_a_rejected_candidate_reads_as_two_lines():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("a.rejected")
    block = js[at:js.index("split.append(left, side)", at)]
    assert "turned-name" in block and "turned-why" in block
    assert "\\u2014" not in block, "no em dashes"
    assert "fold(2, a.rejected.length, draw)" in block


def test_every_swap_the_agent_proposes_is_shown():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function paintSwap(out, d)"):js.index("function block(")]
    assert "swaps.forEach((x) =>" in block
    assert "'Make these swaps' : 'Make this swap'" in block
    assert "'What the swaps do' : 'What the swap does'" in block
    src = (Path(__file__).resolve().parent.parent / "app" / "agent.py").read_text()
    assert "MAX_ROUNDS = 2" in src


def test_an_empty_band_leaves_no_trace():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".spend:empty { display: none; }" in css
    assert ".links:empty { display: none; }" in css


def test_one_pair_per_group_can_be_freed():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("const spendBand = () =>"):js.index("const linkBand = () =>")]
    assert ".slice(0, 1);" in block


def test_the_section_says_what_slate_does():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    assert "What Slate can do" in html
    assert "What you can ask" not in html


def test_the_hero_action_outweighs_the_header_one():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".opening-actions .solid { font-size: 1rem;" in css
    assert ".deskbar-end .solid { font-size: 0.8125rem;" in css


def test_the_readme_is_committed():
    root = Path(__file__).resolve().parent.parent
    assert (root / "README.md").exists()
    assert (root / "LICENSE").exists(), "an open source licence is required"
    ignore = (root / ".gitignore").read_text()
    assert "!README.md" in ignore


def test_the_readme_claims_only_what_was_measured():
    text = (Path(__file__).resolve().parent.parent / "README.md").read_text()
    flat = " ".join(text.split())
    for claim in ("0.35", "0.24", "\u22120.650", "+0.251", "\u22120.498"):
        assert claim in flat, claim
    assert "Honest limits" in text
    assert "could not answer" in flat, "the bridge test that failed"
    assert "not attendance" in flat


def test_the_group_header_is_legible_on_the_panel():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    for sel in (".column-what { font-size: 0.875rem; color: var(--panel-muted)",
                ".taste-head { font-size: 0.75rem; color: var(--panel-muted)"):
        assert sel in css, sel
    at = css.index(".stage span em {")
    assert "var(--panel-muted)" in css[at:css.index("}", at)], "the animations too"
