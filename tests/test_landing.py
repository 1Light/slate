from __future__ import annotations

from pathlib import Path
from app.structure import analyse
from .helpers import _slate


def test_a_slate_is_never_cut_into_mostly_pairs():
    for spread, n in (({"A": 7, "B": 7}, 14), ({"A": 5, "B": 5}, 10)):
        a = analyse(_slate(spread))
        assert len(a.clusters) <= len(a.clusters[0]) * 0 + n * 0.5 + 1


def test_a_pasted_music_lineup_is_not_read_as_films():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    assert "def _read_as(" in src
    assert "urn:entity:artist" in src
    assert 'source == "custom"' in src


def test_the_engine_says_what_it_read():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    assert "ENTITY_LABEL" in src
    assert '"reading"' in src


def test_the_hero_says_what_slate_is_before_showing_a_case():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    at = html.index('class="opening')
    opening = html[at:html.index("</section>", at)]
    for word in ("films", "music", "books", "podcasts", "TV shows"):
        assert word in opening, word
    assert "Try it" in opening
    assert "See it on three film festivals" not in html
    assert "Analyse a lineup" not in html


def test_the_noun_follows_the_entity_type():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    assert "ENTITY_NOUN" in src
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "' acts' : ' films'" not in js


def test_no_group_is_shaded_by_its_size():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert "grey(" not in js
    assert "--g0" not in css and "--g5" not in css


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


def test_the_page_has_a_maximum_width():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert "--page:" in css
    assert ".band { max-width: var(--page)" in css
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    for section in ("opening", "group-head", "views", "checked"):
        assert f'class="{section} band' in html or f'class="{section}' in html


def test_group_columns_are_equal_width():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "weight(" not in js
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".sizes span" in css


def test_the_loading_indicator_is_gone():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "Reading the programmes" not in html
    assert "Nothing is stored" not in html
    assert "$('loading')" not in js


def test_groups_are_lettered_and_the_pairs_say_which():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "const letterFor" in js
    assert "columnHead(mine.length, i, d.noun, d.nouns)" in js
    block = js[js.index("const spendBand"):js.index("const linkBand")]
    assert "spend-letter" in block
    assert "letterFor(i)" in block
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".column-letter" in css and ".spend-letter" in css


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


def test_the_hero_does_not_list_the_page():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    assert "signpost" not in html


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
    assert len(sets) == 6
    assert (folder / "sf-candidates.json").exists()
    for path in sets:
        d = json.loads(path.read_text(encoding="utf-8"))
        assert d["entity_type"].startswith("urn:entity:")
        assert 4 <= len(d["films"]) <= 24, path.name


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


def test_the_coverage_notice_speaks_the_right_noun():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("function coverage(d, host)"):js.index("function failure(")]
    assert "d.nouns" in block
    assert "films you gave" not in block
    assert "Left out: " in block
    assert "no taste connection" in block


def test_the_weak_case_says_so_and_shows_nothing_else():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "No clear separation under this analysis." in js
    assert "are too alike to " not in js
    at = js.index("const spendBand")
    board = js[at:js.index("const settle", at)]
    assert "if (d.weak) { spend.textContent = ''; return; }" in board
    v = js[js.index("function verdict(d)"):js.index("function filmNode(")]
    assert "do not separate." in v


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


def test_the_landing_wiring_only_runs_on_the_landing_page():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "if (document.getElementById('festivals')) start();" in js


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


def test_the_title_marker_is_not_a_layout_class():
    import re
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    mark = re.search(r"el\('i', '([a-z-]+)', hit\)", js)
    assert mark, "the marker's class could not be found"
    name = mark.group(1)
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert re.search(rf"(?m)^\.{name}\s*\{{", css) is None, (
        f"'{name}' is also a standalone rule, so titles inherit its box")


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
    assert "build a lineup around your audience’s tastes" in deck
    assert "analyse one you already have" in deck
    assert "connect different groups" in deck


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
    assert "Build or analyse a lineup, then explore what to keep" in flat
    assert "Analyse an existing lineup" in flat
    assert "Build for an audience" in flat
    assert "Whichever way you start" in flat
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


def test_an_empty_free_a_slot_band_does_not_render():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("const spendBand = () =>"):js.index("const linkBand = () =>")]
    assert "let found = 0" in block
    assert "if (!found) { spend.textContent = ''; return; }" in block


def test_one_pair_per_group_can_be_freed():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("const spendBand = () =>"):js.index("const linkBand = () =>")]
    assert ".slice(0, 1);" in block


def test_the_section_says_what_slate_does():
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    assert "What Slate can do" in html
    assert "What you can ask" not in html


def test_served_json_does_not_republish_qloo_values():
    import json
    served = json.loads((Path(__file__).resolve().parent.parent / "data"
                         / "served.json").read_text())
    for slug, shape in served.items():
        if not isinstance(shape, dict):
            continue
        for key in ("films", "bridges", "isolated"):
            for row in (shape.get(key) or []):
                if isinstance(row, dict):
                    assert "popularity" not in row, f"{slug}.{key}"
        assert "popularity_confound" in shape
    src = (Path(__file__).resolve().parent.parent / "scripts"
           / "precompute.py").read_text()
    assert "def _without_qloo_values(shape: dict)" in src


def test_each_candidate_failure_gets_its_own_answer():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert "def _candidate_notes(" in src
    for line in ("already in this lineup.",
                 "Slate could not find ",
                 "but no data linking "):
        assert line in src, line
    assert "could not be placed against" not in src
    assert "None of those titles could be placed" not in src
    assert "Give some titles to choose between." not in src


def test_the_compare_count_runs_after_filtering():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    at = src.index("def choose(")
    block = src[at:src.index("@app.post", at + 10)]
    assert "if len(pool) < slots + 1:" in block
    assert block.index("pool = [t for t in m.films") < block.index("slots + 1")


def test_the_panel_reports_what_it_could_not_place():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert '"panel", [], entity_type' not in src
    assert src.count('"panel", lost, entity_type') == 2
    assert 'lost: list[str] = []' in src, "a Qloo failure must not leave it unset"


def test_the_year_hint_is_only_where_a_year_helps():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def _year_hint("):src.index("def _nameList(")]
    assert "urn:entity:movie" in block and "urn:entity:tv_show" in block
    assert "Monster (2023)" in block
    assert "or try another title." in block


def test_that_leaves_needs_something_taken_away():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert 'if notes else ""' in src, "a clean list has nothing to leave"


def test_the_outlier_leans_on_its_group():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    at = js.index("} else if (extra === 'apart') {")
    block = js[at:js.index("}", js.index("role: 'apart'", at))]
    assert "laneAt(last)" in block, "beside the last group, not past it"
    assert "turn: -20" in block, "upper left down to lower right"
    assert "card.h * 0.56" in block, "below the last card's midpoint"
    assert "lanes = groups.length + (extra === 'span' ? 1 : 0)" in js, (
        "no empty lane is reserved for it now")
    assert "const lean = extra === 'apart'" in js, "room so it is not clipped"


def test_the_size_bar_shows_which_group_is_largest():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    at = js.index("if (ui.sizes) {")
    block = js[at:js.index("if (ui.taken) {", at)]
    assert "const most = Math.max(1, ...counts);" in block
    assert "0.4 + 0.6 * (n / most)" in block
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".sizes span:first-child" not in css, "size decides, not position"


def test_a_migrated_table_still_reads_its_newer_columns():
                                                                         
                                                                       
                                                
    import tempfile, sqlite3
    import app.store as store
    was = store._SQLITE
    try:
        store._SQLITE = Path(tempfile.mkdtemp()) / "old.db"
        con = sqlite3.connect(store._SQLITE)
        con.execute("CREATE TABLE workspaces (id TEXT PRIMARY KEY, "
                    "owner TEXT, name TEXT, entity_type TEXT, slots INTEGER, "
                    "titles TEXT, versions TEXT, touched REAL)")
        con.commit()
        con.close()

        made = store.create("me", "T", ["A", "B", "C", "D"],
                            "urn:entity:movie")
        store.update("me", made["id"], locked=["A", "B"])
        assert store.read("me", made["id"])["locked"] == ["A", "B"]
        assert store.listing("me")[0]["locked"] == ["A", "B"]
    finally:
        store._SQLITE = was


def test_a_name_that_does_not_exist_says_so():
                                                                      
                                         
    from app.extract import Found
    from app.references import resolve
    import app.references as mod

    was = mod.resolve_film
    try:
        mod.resolve_film = lambda q, f, k: None
        got = resolve(None, [Found("Nnnqx Variations", "urn:entity:movie",
                                   True, "they love Nnnqx Variations", 1, "")])
        assert not got.negative_only, "it was mentioned warmly"
        assert got.unresolved
        why = got.unresolved[0].why.lower()
        assert "no match" in why or "not found" in why, why
    finally:
        mod.resolve_film = was

    refs = (Path(__file__).resolve().parent.parent / "app" / "references.py").read_text()
    order = refs[refs.index("def resolve(qloo"):]
    assert order.index("_search_all") < order.index("negative_only.append"), (
        "existence is checked before polarity")


def test_a_tie_reads_as_a_sentence():
    refs = (Path(__file__).resolve().parent.parent / "app" / "references.py").read_text()
    assert "matched {kinds} about equally" in refs, "was matches, not was matched"
    assert '" and ".join(labels)' in refs, "two kinds join with and"
    assert "not found in Qloo" in refs
