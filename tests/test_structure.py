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
    for target in ("#festivals", "#views", "#checked", "#yours"):
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


def test_the_panel_appears_under_sundance_and_under_your_own_slate():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "panel(hook, { slug: item.slug }" in js
    assert "panel(hook, { films }" in js


def test_the_panel_can_be_reset():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "Reset to the real lineup" in js


def test_the_panel_shows_nothing_until_asked():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function panel("):js.index("async function viewTabs(")]
    tail = block[block.rindex("  drawChips();"):]
    assert "run();" not in tail


def test_the_panel_does_not_repeat_the_slot_advice():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function panel("):js.index("async function viewTabs(")]
    assert "spend.remove()" in block


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
                    "return", "typeof", "Math", "Number", "String", "Object"):
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
    for section in ("opening", "group-head", "views", "checked", "invite"):
        assert f'class="{section} band' in html or f'class="{section}' in html


def test_every_heading_has_a_size():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    for sel in (".views h2", ".checked h2", ".invite h2", ".group-head h2"):
        assert sel in css, sel
    block = css[css.index(".panel-box h3"):css.index(".panel-box .lede")]
    assert "font-size: 1.5rem" in block


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


def test_the_fewer_slots_block_waits_to_be_used():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function panel("):js.index("async function viewTabs(")]
    assert "fewer.hidden = true" in block
    assert "fewer.hidden = false" in block


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
    for label in ("Distance", "Pair", "Agreement", "Rated both"):
        assert f"'{label}'" in pairs, label
    assert "rated both`" not in pairs
    stab = js[js.index("function stabilityTable("):js.index("function bridgeTable(")]
    for label in ("Group", "Held", "By chance", "The gap"):
        assert f"'{label}'" in stab, label


def test_the_closest_and_furthest_pairs_are_separated():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "band('Closest by Slate')" in js
    assert "band('Furthest by Slate')" in js


def test_stacked_tables_are_labelled():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function titled(" in js
    block = js[js.index("async function tests()"):js.index("function ariTable(")]
    assert "titled('Adjusted Rand index, by lineup'" in block
    assert "titled('Each group on its own" in block


def test_the_try_it_box_is_a_centred_card():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    assert 'class="invite-card"' in html
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index(".invite-card {"):css.index("}", css.index(".invite-card {"))]
    assert "margin: var(--s3) auto 0" in block
    assert "border-radius" in block


def test_groups_are_lettered_and_the_pairs_say_which():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "const letterFor" in js
    assert "columnHead(c.films.length, i, d.noun, d.nouns)" in js
    block = js[js.index("const spendBand"):js.index("const settle")]
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
                 "Hence, based on the results shown",
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
    assert "is a bridge. It links" in block
    assert "is an outlier. It is weakly tied" in block
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
    assert "reaches two different crowds at once" in flat
    assert "distinct taste from the rest of the lineup" in flat


def test_the_cards_hold_still_for_reduced_motion():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index("@media (prefers-reduced-motion: reduce) {", css.index(".stage i")):]
    assert ".stage i { animation: none" in block


def test_an_edit_moves_the_rows_rather_than_redrawing():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function settleInto(" in js
    block = js[js.index("function settleInto("):js.index("function panel(")]
    assert "getBoundingClientRect" in block
    assert "if (!before.size || reduced) return" in block


def test_the_hero_does_not_list_the_page():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    assert "signpost" not in html


def test_the_agent_is_visible_without_interaction():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    assert 'id="agent"' in html
    assert "Finding nothing is an\n    allowed answer" in html or "allowed answer" in html
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


def test_the_signpost_sits_in_the_hero():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index(".signpost {"):css.index("}", css.index(".signpost {"))]
    assert "text-align: center" not in block
    assert "var(--faint)" in block


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


def test_what_you_removed_is_not_what_slate_dropped():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function panel("):js.index("async function viewTabs(")]
    assert "Slate dropped:" in block
    assert "putBack" in block
    assert "d.by_you" in js


def test_the_waiting_message_changes():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("async function runOwn("):]
    assert "Looking up your titles" in block
    assert "takes a little longer" in block


def test_the_agent_runs_from_the_panel():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function panel("):js.index("async function viewTabs(")]
    assert "Swap a film to reach more audiences" in block
    assert "Suggest a swap" in block
    assert "body.swap = true" in block


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


def test_a_film_you_added_is_marked_as_added():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function filmNode("):js.index("const LETTERS")]
    assert "fresh.has(f.title)" in block
    assert "'added'" in block
    board = js[js.index("function board("):js.index("function settleInto(")]
    assert "const fresh = new Set(d.added" in board


def test_a_film_can_carry_more_than_one_tag():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function filmNode("):js.index("const LETTERS")]
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


def test_the_change_line_does_not_say_still():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    block = src[src.index("def _diff("):src.index("def _reaches(")]
    assert "Still " not in block


def test_the_keep_control_counts_the_lineup():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("const drawSizes ="):js.index("const run =")]
    assert "state.films.filter" in block
    assert "drawSizes(d.films.length)" not in js


def test_additions_are_marked_not_listed():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function panel("):js.index("async function viewTabs(")]
    assert "`Added: " not in block
