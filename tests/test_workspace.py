from __future__ import annotations

from pathlib import Path


def test_preset_lineups_are_served_from_a_file():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert "_precomputed(" in src
    block = src[src.index("def lineup("):src.index("@app.post")]
    assert "ready is not None" in block


def test_a_lineup_can_be_put_back():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "Use this version" in js, "versions are how a lineup goes back"


def test_an_edit_moves_the_rows_rather_than_redrawing():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "function settleInto(" in js
    at = js.index("function settleInto(")
    block = js[at:js.index("\nfunction ", at + 10)]
    assert "getBoundingClientRect" in block
    assert "if (!before.size || reduced) return" in block
    work = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "settleInto(figure, before," in work


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


def test_saving_a_version_says_when_it_fails():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("saveBtn.onclick")
    block = js[at:js.index("end.append(", at)]
    assert "catch (e)" in block, "a silent failure looks like lost work"
    assert "drawVersions()" in block


def test_the_free_a_slot_block_stays_in_the_figure():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "'.spend'" not in js, "it is the thing a programmer acts on"


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


def test_every_control_belongs_to_the_page():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    bare = js.count("el('button', null")
    assert bare <= 1, f"{bare} buttons fall back to the browser's own styling"


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


def test_the_app_names_what_it_borrows():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "const BORROWED = {" in js
    assert "work.js needs" in js, "it must fail loudly, not silently"
    assert "function el(" not in js, "one definition of el, not two"
    head = js[:js.index("const stage")]
    for name in ("chapter", "withTitles", "nameList", "letterFor",
                 "settleInto", "failure", "el"):
        assert name in head, name


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
    at = js.index("function spaceRow(w)")
    block = js[at:js.index("\nfunction ", at + 10)]
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


def test_the_distance_card_starts_short():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function distanceCard(rows)"):js.index("function compareAsk(")]
    assert "fold(4, rows.length, draw)" in block


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
    assert "saveBtn.classList.add('is-saved')" in js
    assert "'\\u2713 Saved'" in js
    assert "setTimeout(clearSaved, 2000)" in js
    assert "latest.at !== previous.at" in js
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".deskbar-said {" in css
    block = css[css.index(".deskbar-said {"):css.index("}", css.index(".deskbar-said {"))]
    assert "clip-path: inset(50%)" in block
    assert "width: 1px" in block
    assert ".save-version-label, .save-version-confirmation { grid-area: label; }" in css


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


def test_every_long_list_folds_both_ways():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "function fold(shown, total, draw)" in js
    assert "Show fewer" in js
    assert js.count("fold(") >= 3, "the distances, the sets, the rejections"
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".fold {" in css


def test_a_rejected_candidate_reads_as_two_lines():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("a.rejected")
    block = js[at:js.index("split.append(left, side)", at)]
    assert "turned-name" in block and "turned-why" in block
    assert "\\u2014" not in block, "no em dashes"
    assert "fold(2, a.rejected.length, draw)" in block


def test_input_refusals_are_a_sentence_not_a_panel():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "function noted(out, err, fallback)" in js
    assert js.count("noted(out, e,") >= 4, "every ask routes through it"
    block = js[js.index("function noted("):js.index("function said(")]
    assert "404" in block and "409" in block and "422" in block
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".work-note {" in css


def test_the_notes_sit_above_the_figure():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("function paintChoose(out, got)")
    block = js[at:js.index("\nfunction ", at + 10)]
    assert "(got.notes || []).forEach" in block
    assert block.index("got.notes") < block.index("drawn(got.shape)")
    assert "Could not be placed" not in js, "it moved above the figure"


def test_a_mixed_list_is_a_question_not_a_guess():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    assert "class MixedTypes(Exception)" in src
    block = src[src.index("def _read_as("):src.index("def _pipeline(")]
    assert "raise MixedTypes" in block
    assert "if len(by_kind) > 1:" in block

    api = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert api.count("except MixedTypes as mix:") == 2, "panel and spaces"
    assert '"mixed": True' in api

    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "function mixedPanel(info, titles, onPick)" in js
    assert "Slate creates one workspace per kind of title" in js
    assert "err.body = body" in js, "the breakdown must survive the throw"


def test_the_maximum_is_enforced_like_the_minimum():
    api = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert api.count("titles at most.") == 2, "panel and spaces"
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "Twenty-four titles at most." in js


def test_the_header_counts_what_was_analysed():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("function drawCounts()")
    block = js[at:js.index("\nfunction ", at + 10)]
    assert "shown ? shown.films.length" in block
    assert "el('span', over > 0 ? 'over' : null, gap)" in block, (
        "only the warning is red")


def test_the_working_button_does_not_look_disabled():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "make.classList.add('busy')" in js
    assert "make.disabled = true" not in js
    assert "Asking Qloo about" in js
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert "@keyframes working" in css, "breathe drops to 0.2 and would vanish"


def test_the_front_door_shares_a_gutter_with_the_cards():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    door = css[css.index(".door {"):css.index("}", css.index(".door {"))]
    assert "max-width: 72rem" in door
    assert ".door-card-more span {" in css, "the card dots are drawn, not a glyph"
    assert "border-radius: 50%; background: var(--ink)" in css
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "bar.classList.add('bare')" in js
    assert "bar.classList.remove('bare')" in js, "the workspace bar is full"
    assert ".deskbar.bare .deskbar-here" in css
    assert ".deskbar-paths {" in css, "the two paths live in the bar"


def test_only_the_slot_warning_is_red():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".deskbar-counts .over { color: var(--warn); }" in css
    assert ".deskbar-counts.over {" not in css, "it coloured the counts too"
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "counts.classList.toggle('over'" not in js


def test_trailing_punctuation_does_not_echo_back():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    ns = {}
    at = src.index("def _tidy(")
    exec(src[at:src.index("def _year_hint(")], ns)
    assert ns["_tidy"]("Qqzrth Morning Report.") == "Qqzrth Morning Report"
    assert ns["_tidy"]("  Monster, ") == "Monster"
    assert ns["_tidy"]("...") == "..."


def test_a_refusal_on_the_front_door_is_visible():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".door-said.refused {" in css
    assert "color: var(--warn)" in css.split(".door-said.refused {")[1][:120]
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "said.classList.add('refused')" in js


def test_the_mixed_panel_attributes_the_matching():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "`Matched as ${kind.label}" in js
    assert "if (t.year) row.appendChild(el('span', 'year'" in js
    build = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    assert '"year": getattr(got[title]' in build
    assert "adding a year in brackets, like Monster (2023)" in js


def test_the_card_counts_what_qloo_placed():
    store = (Path(__file__).resolve().parent.parent / "app" / "store.py").read_text()
    assert "ADD COLUMN IF NOT EXISTS placed" in store, "postgres"
    assert 'ADD COLUMN {column} {kind}' in store, "sqlite"
    assert '("placed", "INTEGER")' in store
    assert "COLUMNS = (" in store, (
        "columns are named, so a migrated table cannot shift them")
    assert "SELECT {COLUMNS}" in store
    assert "SELECT *" not in store, (
        "SELECT * returns table order, which migrations change")
    assert 'if "titles" in fields and "placed" not in fields' in store, (
        "editing the lineup makes the count stale")

    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "typeof w.placed === 'number'" in js
    assert "w.placed : w.titles.length" in js, "fall back when unknown"
    at = js.index("const fields = {};")
    block = js[at:js.index("}\n", js.index("save(fields)", at))]
    assert "fields.slots" in block and "fields.placed" in block


def test_deleting_is_asked_in_slates_own_voice():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "window.confirm" not in js
    assert "function confirmDelete(name)" in js
    assert "await confirmDelete(w.name)" in js
    block = js[js.index("function confirmDelete("):js.index("function showPaper(")]
    assert "Escape" in block, "a dialog must be dismissable"
    assert "aria-modal" in block
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".ask-acts .solid.warn { background: var(--warn); }" in css


def test_the_front_door_offers_both_paths():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "'Analyse a lineup'" in js and "'Build for an audience'" in js
    assert "Analyse this lineup" in js, "the original action is unchanged"
    assert "function audienceFlow(host)" in js
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".door-path.on {" in css


def test_a_workspace_says_where_it_came_from():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "'Lineup analysis'" in js, "the original path is labelled too"
    assert "Audience \\u00b7 Demand-led" in js
    assert "Audience \\u00b7 Balanced" in js
    assert "deskbar-mode" in js
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".deskbar-mode {" in css


def test_the_two_paths_are_tabs_in_the_bar():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "el('span', 'deskbar-paths')" in js
    assert "if (here) here.appendChild(paths);" in js, "in the bar, not the page"
    assert "el('button', 'door-path on', 'Analyse a lineup')" in js, (
        "Analyse starts active")
    assert "el('button', 'door-path', 'Build for an audience')" in js


def test_one_chip_holds_both_controls():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("const held = new Set(locked());")
    block = js[at:js.index("chipBox.appendChild(chip);", at)]
    assert "LOCK_SHUT" in block and "LOCK_OPEN" in block, "a padlock, not a diamond"
    assert "This title must be included. Click to unlock." in block
    assert "Always include this title in the lineup." in block
    assert "`Remove ${t}`" in block
    assert "chip.onclick" not in block, (
        "the chip body does nothing; a stray click must not delete a title")
    assert "chip.append(hold, name, off);" in block, "one chip, not two"
    assert "Lock any titles Slate must include." in js

    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".chip.held { border-color: var(--ink)" in css
    assert ".chip-x:hover { color: var(--warn); }" in css


def test_the_client_keeps_locks_a_reply_leaves_out():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("async function save(fields)"):]
    block = block[:block.index("\nlet rail")]
    assert "if (!Array.isArray(got.locked))" in block
    assert "was.locked" in block, "a reply without locks must not clear them"
    assert "got.audience = was.audience" in block


def test_the_card_menu_is_drawn_not_typed():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "for (let i = 0; i < 3; i += 1) more.appendChild(el('span'));" in js
    assert "'door-card-more', '\\u22ee'" not in js, "the glyph's weight varied"
    assert "head.appendChild(more);" in js, "level with the bar"
    assert "head.appendChild(bar);" in js

    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    head = css[css.index(".door-card-head {"):]
    head = head[:head.index("}")]
    assert "align-items: center" in head


def test_a_locked_title_is_marked_wherever_the_figure_draws_it():
    """Bridges are drawn as .link-name, not .film, so a selector tied to
    .film found the group columns and nothing else."""
    here = Path(__file__).resolve().parent.parent
    work = (here / "static" / "work.js").read_text()
    assert "function markLocks(where)" in work, (
        "marking must be callable again when a band rebuilds")
    at = work.index("function markLocks(where)")
    marking = work[at:work.index("\nfunction ", at + 10)]
    assert "where.querySelectorAll('[data-title]')" in marking, (
        "the selector must not be tied to one class")
    assert ".film[data-title]" not in marking
    assert "window.afterLinks" in work, (
        "the links band is rebuilt after the first pass, which wiped the mark")

    assert "window.afterLinks(ui.links)" in (
        ROOT_APP := (here / "static" / "app.js").read_text())

    app = (here / "static" / "app.js").read_text()
    bridge = app[app.index("const name = el('p', 'link-name');"):]
    bridge = bridge[:bridge.index("one.appendChild(name)")]
    assert "name.dataset.title = b.film;" in bridge, (
        "a bridge row must carry its title")

    columns = app[app.index("c.films.slice().sort().forEach"):]
    columns = columns[:columns.index("cols.appendChild(col)")]
    assert "row.dataset.title = t;" in columns