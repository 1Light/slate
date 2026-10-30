from __future__ import annotations

from pathlib import Path


def test_probe_lineups_stay_out_of_the_product():
    from pathlib import Path as P
    root = P(__file__).resolve().parent.parent
    for name in ("app/main.py", "scripts/audit.py", "scripts/precompute.py"):
        assert 'startswith("_")' in (root / name).read_text(), name


def test_the_probe_calls_the_engine():
    src = (Path(__file__).resolve().parent.parent / "scripts"
           / "probe_stability.py").read_text()
    assert "from app.structure import analyse" in src
    assert "def agglomerate" not in src
    assert "def silhouette" not in src


def test_probe_lineups_do_not_reach_the_main_page():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def lineups("):src.index("SERVED =")]
    assert 'startswith("_")' in block


def test_validation_does_not_recompute_what_is_already_stored():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def validation("):]
    block = block[:block.index("@app.get")]
    assert '"bridge" not in out' in block
    assert '"lineup_ari" not in out' in block


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
    for label in ("Distance", "Pair", "Audience overlap", "Rated both"):
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


def test_the_conclusion_comes_after_the_evidence():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("async function tests()"):js.index("function ariTable(")]
    assert "const below = (art, text, cls)" in block
    assert "art.after" in block
    for line in ("These checks support a relationship between Slate’s",
                 "On these ${ml.pairs} pairs, Slate’s distance had a stronger",
                 "Across these four lineups, the groups remained largely",
                 "Hence a bridge is not the most popular"):
        at = block.index(line)
        before = block[:at]
        assert before.rstrip().endswith("'") or "below(art" in before[-400:], line


def test_the_control_figure_letters_its_groups():
    src = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = src[src.index("function controlFigure("):src.index("function mlTables(")]
    assert ".forEach((c, i) =>" in block


def test_the_evidence_explains_what_a_group_is():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "Does a group mean a fixed audience?" in js
    assert "there is no universal grouping to belong to" in js
    assert "not a universally fixed " in js


def test_the_probe_checks_for_clashes_too():
    src = (Path(__file__).resolve().parent.parent / "scripts"
           / "probe_candidates.py").read_text()
    assert "already in an example" in src


def test_findings_sit_beside_their_evidence():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index(".work-split {"):css.index("}", css.index(".work-split {"))]
    assert "grid-template-columns: minmax(0, 1fr) 21rem" in block
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert js.count("el('div', 'work-split") >= 4, "every ask uses it"
    assert "'work-split ranked'" in js, "four columns need a wider card"
    assert "function distanceCard(rows)" in js


def test_the_pair_table_shows_what_separates_them():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "'Audience overlap'" in js
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
    assert "ratings for the less-rated film in each pair" in block
    assert "−0.596" in block
    assert "shared audience, not fame" not in block
    probe = (Path(__file__).resolve().parent.parent / "scripts"
             / "probe_overlap.py").read_text()
    assert 'm["overlap_rho"]' in probe
    assert 'm["closest"]' in probe, "the probe writes the pairs it shows"


def test_the_group_result_leads_the_second_test():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    at = js.index("test(2, 'Do the groups match")
    block = js[at:js.index("test('2b'", at)]
    assert "v.groups" in block
    assert "pooled into one pile" in block
    assert "g.shuffles" in block
    assert "same number of films in each group" in block
    assert "None produced a gap as large as Slate’s." in block
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
    assert "Slate chooses the minimum number of " in js
    assert "groups that achieves a near-optimal division." in js
    assert "further scores either the same or worse." not in js
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


def test_the_baselines_are_measured_against_agreement():
    import json
    root = Path(__file__).resolve().parent.parent
    src = (root / "scripts" / "probe_overlap.py").read_text()
    assert 'm["baselines"]' not in src, "it would overwrite the right ones"

    v = json.loads((root / "data" / "validation.json").read_text())
    rows = {b["name"]: b["rho"] for b in v["movielens"].get("baselines", [])}
    if not rows:
        return
    assert abs(rows["Slate distance"] - (-0.498)) < 0.01, rows
    assert abs(rows["Years apart"]) < 0.3, (
        "release year near Slate means these are overlap figures")


def test_the_probe_lineup_stays_off_the_page():
    root = Path(__file__).resolve().parent.parent
    assert not (root / "data" / "lineups" / "bridge-probe.json").exists()
    assert (root / "data" / "lineups" / "_probe-bridge.json").exists()
    for name in ("probe_groups.py", "probe_bridge_audience.py"):
        src = (root / "scripts" / name).read_text()
        assert '"_probe-bridge"' in src, name
        assert '"bridge-probe"' not in src, name


def test_an_unsure_name_is_decided_by_evidence():
    from app.extract import Found
    from app.references import resolve
    import app.references as mod

    class Got:
        def __init__(self, name, eid, score):
            self.qloo_name, self.entity_id = name, eid
            self.score, self.qloo_year = score, None

    world = {
        ("Under the Skin", "urn:entity:movie"): Got("Under the Skin", "m1", 6),
        ("Dune", "urn:entity:movie"): Got("Dune", "m2", 6),
        ("Dune", "urn:entity:tv_show"): Got("Dune", "t2", 6),
        ("Radiohead", "urn:entity:artist"): Got("Radiohead", "a1", 6),
        ("Radiohead", "urn:entity:book"): Got("Radio Head", "b1", 5),
    }
    was = mod.resolve_film
    try:
        mod.resolve_film = lambda q, f, k: world.get((f.title, k))

        one = resolve(None, [Found("Under the Skin", None, True, "x", 1, "")])
        assert one.references[0].entity_type == "urn:entity:movie"

        tie = resolve(None, [Found("Dune", None, True, "x", 1, "")])
        assert not tie.references
        assert "about equally" in tie.unresolved[0].why
        assert "matched" in tie.unresolved[0].why

        won = resolve(None, [Found("Radiohead", None, True, "x", 1, "")])
        assert won.references[0].entity_type == "urn:entity:artist"

        none = resolve(None, [Found("Nnnqx", None, True, "x", 1, "")])
        assert "not found" in none.unresolved[0].why
    finally:
        mod.resolve_film = was


def test_an_audience_workspace_keeps_its_evidence():
    import json as _json, tempfile
    import app.store as store
    was = store._SQLITE
    try:
        store._SQLITE = Path(tempfile.mkdtemp()) / "a.db"
        made = store.create("me", "Season", ["A", "B", "C", "D"],
                            "urn:entity:movie", slots=4,
                            audience={"mode": "balanced",
                                      "references": [{"title": "Arrival"}],
                                      "served": []})
        got = store.read("me", made["id"])
        assert got["audience"]["mode"] == "balanced"
        assert got["audience"]["references"][0]["title"] == "Arrival"

        plain = store.create("me", "Plain", ["A", "B", "C", "D"],
                             "urn:entity:movie")
        assert store.read("me", plain["id"])["audience"] is None, (
            "the analyse path carries no audience")
    finally:
        store._SQLITE = was
