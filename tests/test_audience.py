from __future__ import annotations

from pathlib import Path


def test_more_audiences_is_still_better_where_it_means_something():
    from app.agent import _score
    before = _score({"clusters": 3, "largest_cluster": 12, "bridges": 0}, 20)
    after = _score({"clusters": 5, "largest_cluster": 7, "bridges": 0}, 20)
    assert after > before


def test_an_outlier_is_not_called_a_unique_audience():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    import re
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    flat = re.sub(r"\s+", " ", html)
    assert "only route to its audience" not in js
    assert "'outlier'" in js
    assert "distinct taste from the rest of the lineup" in flat


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


def test_the_two_audience_modes_genuinely_differ():
    from app.audience import BALANCED, DEMAND_LED, Reference, select
    pool = [f"c{i}" for i in range(8)]
    straight = pool
    reversed_ = pool[::-1]
    rank = {"A": straight, "B": straight, "C": straight, "D": reversed_}
    refs = [Reference("A", "m", "1", 3.0), Reference("B", "m", "2", 3.0),
            Reference("C", "m", "3", 3.0), Reference("D", "m", "4", 1.0)]

    deep = select(pool, refs, rank, 3, DEMAND_LED)
    wide = select(pool, refs, rank, 3, BALANCED)
    assert deep["chosen"] != wide["chosen"]
    assert wide["weakest"] > deep["weakest"], (deep, wide)
    assert any(r["reference"] == "D" and r["best"] == 1.0
               for r in wide["served"])


def test_locks_are_part_of_the_selection():
    from app.audience import BALANCED, Reference, select
    pool = [f"c{i}" for i in range(8)]
    refs = [Reference("A", "m", "1"), Reference("B", "m", "2")]
    rank = {"A": pool, "B": pool[::-1]}

    got = select(pool, refs, rank, 3, BALANCED, locked=["c5"])
    assert "c5" in got["chosen"]
    assert len(got["chosen"]) == 3

    full = select(pool, refs, rank, 2, BALANCED, locked=["c3", "c4"])
    assert full["how"] == "all locked", "do not pretend Slate chose these"
    assert sorted(full["chosen"]) == ["c3", "c4"]


def test_an_impossible_audience_request_is_refused():
    from app.audience import BALANCED, Reference, select
    pool = ["a", "b", "c"]
    refs = [Reference("A", "m", "1")]
    rank = {"A": pool}
    for why, kw in (("more locks than slots", dict(slots=1, locked=["a", "b"])),
                    ("lock outside the pool", dict(slots=2, locked=["zz"])),
                    ("pool too small", dict(slots=9)),
                    ("unknown mode", dict(slots=2, mode="sideways"))):
        try:
            select(pool, refs, rank, **kw)
            raise AssertionError(f"{why} was not refused")
        except ValueError:
            pass
    try:
        select(pool, [], rank, 2)
        raise AssertionError("no references was not refused")
    except ValueError:
        pass


def test_a_missing_candidate_is_not_a_zero_affinity_one():
    from app.audience import utilities
    pool = ["a", "b", "c", "d"]
    u = utilities({"R": ["a", "b"]}, pool)
    assert u["R"]["a"] == 1.0
    assert u["R"]["c"] == 0.0 and u["R"]["d"] == 0.0
    assert set(u["R"]) == set(pool), "every candidate must have a utility"


def test_the_audience_selector_never_scores_dislikes():
    src = (Path(__file__).resolve().parent.parent / "app" / "audience.py").read_text()
    body = src[src.index("def score("):src.index("def _greedy(")]
    assert "disliked" not in body
    assert "disliked: int = 0" in src, "but it is still recorded"


def test_the_audience_endpoints_exist_and_refuse_nonsense():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert '@app.post("/api/audience/read")' in src
    assert '@app.post("/api/audience/build")' in src
    read = src[src.index("def audience_read("):src.index("def audience_build(")]
    assert "audience to build for" in read, "invention is refused"
    assert "a film, artist, " in read, "the nouns match the guidance"
    assert "ExtractFailed" in read, "a model outage is not a no-match"

    build = src[src.index("def audience_build("):]
    build = build[:build.index("@app.get")]
    assert "Pick Balanced or Demand-led." in build
    assert "cannot fill" in build, "too few candidates is refused"
    assert "cannot be required" in build, "a lock outside the pool"
    assert "could not relate any of those" in build


def test_the_audience_tab_shows_only_where_there_is_one():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "if (space.audience) {" in js, "no empty tab on the other path"
    block = js[js.index("function audienceTab(body)"):js.index("function fewerAsk(")]
    assert "Closest matches in your selected lineup" in block
    assert "aud-cards" in block, "mode and source as cards"
    assert "Fit" not in block, "a column of identical 1.00s said nothing"

    assert "aggregated" in block, "counts only where they are real"
    assert "represented under several items" in block
    assert "mention' : 'mentions'" in block, (
        "a survey repeats, a description does not")

    assert "Not used" in block
    assert "a.source === 'description' && a.text" in block, (
        "the toggle is only for text")
    for forbidden in ("Rebuild", "Change mode", "contentEditable"):
        assert forbidden not in block, f"the tab is read-only: {forbidden}"


def test_the_audience_flow_replaces_the_lineup_form():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "audienceFlow(" in js
    assert "door-audience" in js, "the flow has its own container"


def test_the_audience_input_step_is_rebuilt():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function audienceFlow(host)"):js.index("function asTable(")]
    assert "aswitch-half" in block, "a segmented control, not two pills"
    assert "'Analyse audience'" in block
    assert "Name films, artists, books, podcasts or TV shows they enjoy" in block
    assert "They love Arrival and listen to a lot of Radiohead." in block
    assert "Choose a CSV file" in block
    assert "Try a taste survey" in block and "Try audience preferences" in block
    assert "upload.className = 'ahidden'" in block, (
        "the browser's own file button never shows")
    assert "liked_count" in block and "disliked_count" in block, (
        "the columns are the guidance")
    assert "Synthetic demo data" in block

    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    for rule in (".aswitch-half.on {", ".acard.dashed {", ".ahidden {"):
        assert rule in css, rule


def test_the_audience_flow_is_a_modal_of_four_steps():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "const AUDIENCE_STEPS = 4;" in js
    assert "function modalShell(onShut)" in js
    assert "function audienceModal(found)" in js
    assert "audienceModal(found);" in js, "opened once the audience is read"

    shell = js[js.index("function modalShell("):js.index("function audienceModal(")]
    assert "Escape" in shell and "aria-modal" in shell
    assert "flow-bars" in shell, "progress across the whole width"
    assert "`Step ${n} of ${AUDIENCE_STEPS}`" in shell

    at = js.index("function audienceModal(")
    body = js[at:js.index("function flowHead(")]
    assert "flow.back.onclick" in body, "Back moves between steps"
    assert "n === 4 ? 'Build this lineup' : 'Continue'" in body


def test_the_review_step_has_no_confirm_and_no_view_source():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function stepReview("):js.index("function stepCandidates(")]
    assert "View source" not in block
    assert "Confirm audience" not in block
    assert "flow-ref-off" in block
    assert "\\u21ba" in block, "a removed reference can be put back"
    assert "will be used" in block, "the footer counts what remains"


def test_the_candidate_step_blocks_until_it_has_been_analysed():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function stepCandidates("):js.index("function drawPool(")]
    assert "Analyse the candidates first" in block
    assert "flow.blocked(true);" in block
    assert "'Analyse candidates'" in block
    assert "Enter the candidates Slate can choose from" in block
    assert "<select" not in block and "OUTPUTS" not in block, (
        "the type is not chosen from a dropdown")

    pool = js[js.index("function drawPool("):js.index("function missedLine(")]
    assert "All matched candidates are" in pool
    assert "Matched as ${kind.label}" in pool
    assert "`Use these ${kind.titles.length}`" in pool

    api = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert '@app.post("/api/audience/candidates")' in api


def test_the_slot_step_shows_the_real_range():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function stepSlots("):js.index("function stepMode(")]
    assert "Math.min(kept.pool.length, MAX_PICK)" in block, (
        "the ceiling is the pool, or 24, whichever is smaller")
    assert "flow-count" in block and "flow-step-btn" in block
    assert "leaves ${unused} unused" in block
    assert "A lineup can contain 4\\u201324 titles" in block


def test_the_last_step_builds():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function stepMode("):js.index("function asTable(")]
    assert "How should Slate build your lineup?" in block
    assert "equal weight" in block
    assert "Less common tastes get as much consideration" in block
    assert "strongest support" in block
    assert "'Ready'" not in block, "the summary step is gone"
    assert "/api/audience/build" in block


def test_the_workspace_name_stops_at_sixty():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert "const NAME_LIMIT = 60;" in js
    assert "text.slice(0, NAME_LIMIT)" in js
    assert js.index("const NAME_LIMIT") < js.index("title.oninput"), (
        "defined before it is used")


def test_the_mode_label_is_readable():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index(".deskbar-mode {"):]
    block = block[:block.index("}")]
    assert "color: var(--muted)" in block, "faint was quieter than the counts"
    assert "border: 1px" in block


def test_the_describe_tab_fills_its_other_half():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function audienceFlow(host)"):js.index("function asTable(")]
    assert "What Slate reads" in block
    assert "Names, not adjectives" in block
    assert "Any of the five kinds" in block
    assert "Include dislikes" not in block, "nothing meaningful used it"
    assert "reads.hidden = true;" in block and "reads.hidden = false;" in block, (
        "the two panels swap")

    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert "text-mode" not in css, "the grid no longer collapses"
    field = css[css.index(".audience-entry .afield {"):]
    field = field[:field.index("}")]
    assert "min-height: 9rem" in field, "fifteen was far too tall"


def test_an_unused_reference_reads_as_one_sentence():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    review = js[js.index("function stepReview("):js.index("function stepCandidates(")]
    assert "could not confidently match them or they were" not in review, (
        "the server already knows which reason applies")
    assert "names.length === 1 ? 'was' : 'were'" in review
    assert "item.why" in review

    refs = (Path(__file__).resolve().parent.parent / "app" / "references.py").read_text()
    assert 'why="only mentioned negatively' in refs, (
        "the sentence reads: X was only mentioned negatively")


def test_the_audience_table_is_one_surface():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    table = css[css.index(".aud-table {"):]
    table = table[:table.index("}")]
    assert "border: 0.5px solid var(--rule-2)" in table
    assert "border-radius: 9px" in table

    head = css[css.index(".aud-table th {"):]
    head = head[:head.index("}")]
    assert "background: var(--raised)" in head, "a tinted header row"

    assert ".aud-meta { font-size: 0.75rem; color: var(--faint); margin-left" in css, (
        "the kind sits beside the name, not under it")
    quote = css[css.index(".aud-evidence-quote {"):]
    quote = quote[:quote.index("}")]
    assert "border-left: 2px solid" in quote


def test_the_review_columns_line_up():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    cols = css[css.index(".flow-cols {"):]
    cols = cols[:cols.index("}")]
    assert "repeat(3, minmax(0, 1fr))" in cols, (
        "auto-fit sized each column to its longest title, so the crosses "
        "never aligned")

    off = css[css.index(".flow-ref-off {"):]
    off = off[:off.index("}")]
    assert "padding: 0.35rem" in off, "a hit area, not a bare glyph"
    assert "flex: none" in off
    assert ".flow-ref-off:hover { color: var(--warn)" in css
