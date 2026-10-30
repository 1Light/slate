from __future__ import annotations

from pathlib import Path


def test_the_accent_means_one_thing():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    for block in css.split("}"):
        if "var(--accent)" not in block:
            continue
        head = block.split("{")[0]
        assert any(w in head for w in ("bridge", "threads", "accent")), head


def test_the_outlier_has_its_own_colour():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert "--alone:" in css and "--alone-on:" in css
    assert ".film.alone { border-left-color: var(--alone-on); }" in css


def test_every_heading_has_a_size():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    for sel in (".views h2", ".checked h2", ".group-head h2"):
        assert sel in css, sel
    assert ".desk-rail-head {" in css and ".said-head {" in css


def test_the_spacing_is_a_scale():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    for token in ("--s1:", "--s2:", "--s3:", "--s4:"):
        assert token in css, token


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


def test_the_cards_hold_still_for_reduced_motion():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index("@media (prefers-reduced-motion: reduce) {", css.index(".stage i")):]
    assert ".stage i { animation: none" in block


def test_group_letters_look_the_same_everywhere():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    head = css[:css.index("{", css.index(".column-letter"))]
    for sel in (".column-letter", ".spend-letter", ".stage span u"):
        assert sel in head, sel
    block = css[css.index(".column-letter"):css.index("}", css.index(".column-letter"))]
    assert "background: var(--panel-bright)" in block
    assert "color: var(--panel)" in block


def test_an_empty_legend_leaves_no_rule_behind():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".legend:empty { display: none; }" in css


def test_the_figure_has_no_gap_above_it():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".work-figure .chapter { padding-top: 0; border-top: 0; }" in css
    assert ".out .chapter, .work-body > .chapter { padding-top: 0;" in css


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


def test_nothing_hides_the_focus_ring():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert "outline: none" not in css, (
        "a keyboard user needs to see where they are")
    assert ":focus-visible { outline:" in css


def test_the_app_works_below_a_desk():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    app = css[css.index("body.workbench"):]
    for width in ("1040px", "880px", "620px"):
        assert f"max-width: {width}" in app, width
    phone = app[app.index("max-width: 620px"):]
    assert "overflow-x: auto" in phone, "a wide figure scrolls rather than crushes"
    assert "flex-direction: column" in phone, "rows stack"
    assert "padding: 0.65rem 1.1rem" in phone, "targets grow to a thumb"


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


def test_a_field_is_the_width_of_what_goes_in_it():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    block = css[css.index('.work-form input[type="text"] {'):]
    block = block[:block.index("}")]
    assert "flex: 0 1" in block, "a short title in a full-width box looks wrong"
    assert "min-width: 14rem" in block


def test_the_ask_controls_are_sized_to_their_content():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".work-form .narrow { width: 5rem; }" in css
    assert ".compare-box {" in css
    box = css[css.index(".compare-box {"):]
    box = box[:box.index("}")]
    assert "max-width: 34rem" in box


def test_an_empty_band_leaves_no_trace():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".spend:empty { display: none; }" in css
    assert ".links:empty { display: none; }" in css


def test_the_hero_action_outweighs_the_header_one():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".opening-actions .solid { font-size: 1rem;" in css
    assert ".deskbar-end .solid { font-size: 0.8125rem;" in css


def test_the_group_header_is_legible_on_the_panel():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    for sel in (".column-what { font-size: 0.875rem; color: var(--panel-muted)",
                ".taste-head { font-size: 0.75rem; color: var(--panel-muted)"):
        assert sel in css, sel
    at = css.index(".stage span em {")
    assert "var(--panel-muted)" in css[at:css.index("}", at)], "the animations too"


def test_both_path_tabs_look_like_buttons():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    track = css[css.index(".deskbar-paths {"):]
    track = track[:track.index("}")]
    assert "background: var(--raised)" in track, "a recessed track"
    assert "border: 0.5px solid var(--rule-2)" in track

    half = css[css.index(".door-path {"):]
    half = half[:half.index("}")]
    assert "font-size: 0.90625rem" in half, "big enough to read as a control"
    assert "padding: 0.55rem 1.5rem" in half

    on = css[css.index(".door-path.on {"):]
    on = on[:on.index("}")]
    assert "background: var(--card)" in on and "box-shadow" in on


def test_a_refusal_has_room_and_the_right_nouns():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()
    assert ".audience-entry .work-note {" in css
    note = css[css.index(".audience-entry .work-note {"):]
    note = note[:note.index("}")]
    assert "margin-top" in note, "it was jammed against the button"

    api = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    said = api[api.index("Nothing in that names"):]
    said = said[:said.index("by name")]
    assert "album" not in said, "the field says artists, not albums"
    assert "programme" not in said, "the field says TV shows"
    assert "artist" in said and "TV show" in said
