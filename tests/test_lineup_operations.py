from __future__ import annotations

from pathlib import Path


def test_the_agent_will_not_shred_a_slate():
    from app.agent import _score
    sane = _score({"clusters": 6, "largest_cluster": 10, "bridges": 0}, 20)
    shredded = _score({"clusters": 12, "largest_cluster": 3, "bridges": 0}, 20)
    assert shredded < sane, (shredded, sane)


def test_a_swap_that_changes_no_count_is_still_explained():
    src = (Path(__file__).resolve().parent.parent / "app" / "agent.py").read_text()
    assert "the largest group comes down from" in src
    assert "a route opens between groups that had none" in src
    assert "the slate stays the same size but is less " in src
    assert "change{'' if n == 1 else 's'}" not in src


def test_no_agent_buttons_remain():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "Let the agent try" not in js
    assert "function runAgent" not in js


def test_the_agent_reports_both_structures():
    src = (Path(__file__).resolve().parent.parent / "app" / "agent.py").read_text()
    assert "before_groups" in src and "after_groups" in src
    assert '"after_groups": result.after_groups' in src


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


def test_the_panel_agent_decides_on_the_current_lineup():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def panel("):src.index('@app.post("/api/agent")')]
    assert "if req.swap:" in block
    assert "improve(Qloo(), small, analyse(small)" in block
    assert "AGENT_PER_HOUR" in block


def test_the_agent_section_does_not_depend_on_the_chapter_loop():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    assert "async function agentSection()" in js
    block = js[js.index("async function agentSection()"):]
    assert "if (!byslug[slug]) continue" not in block
    assert "one-genre" in block
    run = block[:block.index("function") if "function" in block[1:] else len(block)]
    assert "console.error('agent case'" in js


def test_the_agent_speaks_the_pages_language():
    src = (Path(__file__).resolve().parent.parent / "app" / "agent.py").read_text()
    page = src[:src.index('"You advise a film festival programmer')] \
        + src[src.index('"certainty about real audiences."') + 33:]
    assert "audiences" not in page
    assert "programme " not in page


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


def test_best_means_the_same_in_both_places():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    block = src[src.index("def _best_subset_fast("):src.index("def _profile(")]
    assert "_profile(m, list(c))" in block, "ranked by the same measure"
    assert "_reaches(" not in block, "the composite score disagreed with it"
    chance = src[src.index("def _against_chance("):src.index("def _contribution(")]
    assert "_profile(m, chosen)" in chance


def test_a_choice_is_ranked_by_what_it_changes():
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    assert "def _touching(m, lineup, picked):" in src
    block = src[src.index("def _choose_best("):]
    assert '"profile": _touching(m, lineup, list(picked))' in block, (
        "the lineup's own pairs are the same for every option")
    brief = src[src.index("def _contribution("):src.index("def _fit_brief(")]
    assert "_touching(m, others, [candidate])" in brief


def test_a_choice_that_reaches_nowhere_new_says_so():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("function paintChoose(")
    assert "None of the titles you" in js[at:js.index("\nfunction ", at + 10)]


def test_the_two_descriptions_of_the_agent_agree():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    html = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()
    flat = " ".join(html.split())
    assert "Slate reports no change" in js and "Slate reports no change" in flat
    assert "takes a slot the lineup can spare" not in js
    assert "Look for a swap" in js


def test_the_set_ranking_shows_its_tie_break():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    at = js.index("'Every set, best first'")
    block = js[at:js.index("split.append(left, side)", at)]
    assert "'Next'" in block
    assert "r.next" in block
    assert "then by the next closest where that ties" in js
    src = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    assert '"next": (round(r["profile"][1], 6)' in src


def test_every_swap_the_agent_proposes_is_shown():
    js = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    block = js[js.index("function paintSwap(out, d)"):js.index("function block(")]
    assert "swaps.forEach((x) =>" in block
    assert "'Make these swaps' : 'Make this swap'" in block
    assert "'What the swaps do' : 'What the swap does'" in block
    src = (Path(__file__).resolve().parent.parent / "app" / "agent.py").read_text()
    assert "MAX_ROUNDS = 2" in src


def test_a_locked_title_cannot_be_dropped_by_an_ask():
    build = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    block = build[build.index("def _best_subset_fast("):]
    block = block[:block.index("\ndef ")]
    assert "locked" in block
    assert "if len(held) >= keep:" in block, "all slots required"
    assert "droppable" in block, "greedy must not drop a held title"

    agent = (Path(__file__).resolve().parent.parent / "app" / "agent.py").read_text()
    block = agent[agent.index("def _most_redundant("):]
    block = block[:block.index("\ndef ")]
    assert "free = [f for f in biggest if f not in held]" in block
    assert "if not free:" in block


def test_fewer_slots_refuses_when_locks_exceed_the_target():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    assert "You have locked" in src
    assert "Unlock some " in src and "increase the slot count" in src
    block = src[src.index("if req.keep is not None"):]
    block = block[:block.index("if req.swap")]
    assert "if len(held) > req.keep:" in block
    assert "None if len(held) == req.keep" in block


def test_a_locked_title_is_never_offered_as_droppable():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("const spendBand ="):js.index("const linkBand =")]
    assert "const held = new Set(d.locked || []);" in block
    assert block.count("!held.has(t.a) && !held.has(t.b)") == 2, (
        "both the group filter and the pair filter")

    work = (Path(__file__).resolve().parent.parent / "static" / "work.js").read_text()
    assert work.count("d.locked = locked();") == 2, "the figure must know"

    build = (Path(__file__).resolve().parent.parent / "app" / "build.py").read_text()
    spare = build[build.index("    spare = None"):]
    spare = spare[:spare.index("    full = lineup")]
    assert "a in held or b in held" in spare, (
        "nothing can be said to replace a locked title")


def test_the_agent_says_when_locks_leave_it_nothing():
    src = (Path(__file__).resolve().parent.parent / "app" / "agent.py").read_text()
    block = src[src.index("out_title = _most_redundant("):]
    block = block[:block.index("steps.append(Step(\n            \"plan\"")]
    assert "Every title in the crowded" in block
    assert "No group is crowded enough to " in block, (
        "the two reasons must be separate")
    assert block.count('Step("stop"') == 2


def test_the_figure_can_find_a_locked_title():
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text()
    block = js[js.index("c.films.slice().sort().forEach"):]
    block = block[:block.index("cols.appendChild(col)")]
    assert "row.dataset.title = t;" in block, (
        "the padlock is inserted by [data-title], which this never set")

    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    tag = css[css.index(".film .tag {"):]
    tag = tag[:tag.index("}")]
    assert "margin: 0.3rem 0 0 0.4rem" in tag, (
        "the badge butted against the year")
