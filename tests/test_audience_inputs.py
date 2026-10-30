from __future__ import annotations

from pathlib import Path
from app.resolve import score_candidate


def test_both_csv_contracts_read_the_demo_files():
    from app.ingest import read_preferences, read_survey, sniff
    folder = Path(__file__).resolve().parent.parent / "data" / "examples"
    survey = (folder / "taste_survey.csv").read_text(encoding="utf-8")
    counted = (folder / "audience_preferences.csv").read_text(encoding="utf-8")

    got = read_survey(survey, "taste_survey.csv")
    assert len(got.answers) >= 12 and not got.skipped
    assert len({a.question for a in got.answers}) >= 4, "several questions"

    got = read_preferences(counted, "audience_preferences.csv")
    assert len(got.counted) >= 10 and not got.skipped
    assert any(c.disliked > c.liked for c in got.counted), (
        "something divisive, or the modes cannot differ")

    assert sniff(survey) == "survey_csv"
    assert sniff(counted) == "preference_csv"
    assert sniff("a,b\n1,2\n") is None, "do not guess a contract"


def test_a_malformed_count_is_an_error_not_a_zero():
    from app.ingest import BadSource, read_preferences
    for text, expect in (
            ("name,liked_count,disliked_count\nArrival,lots,2\n", "Row 2"),
            ("name,liked_count,disliked_count\nArrival,-5,2\n", "Row 2"),
            ("name,liked_count,disliked_count\nArrival,,2\n", "Row 2"),
            ("name,liked_count,disliked_count\nArrival,0,9\n", "positive")):
        try:
            read_preferences(text)
            raise AssertionError(f"accepted: {text!r}")
        except BadSource as e:
            assert expect in str(e), (expect, str(e))


def test_the_model_cannot_invent_a_name():
    from app.extract import _clean
    said = [{"name": "Arrival", "kind": "film", "liked": True},
            {"name": "Ex Machina", "kind": "film", "liked": True}]
    kept = _clean(said, within="I loved Arrival most of all")
    assert [k.name for k in kept] == ["Arrival"]


def test_the_prompt_forbids_inventing_an_audience():
    src = (Path(__file__).resolve().parent.parent / "app" / "extract.py").read_text()
    assert "Young professionals who travel a lot" in src, (
        "demographics alone must yield nothing")
    assert '"unsure"' in src, "guessing to fill a field is worse than unsure"
    assert "Prefer the question over your own recognition" in src


def test_only_the_content_of_the_model_reply_is_read():
    from app.extract import _parse
    assert len(_parse('{"found": [{"name": "Arrival"}]}')) == 1
    src = (Path(__file__).resolve().parent.parent / "app" / "extract.py").read_text()
    assert '["message"]["content"]' in src
    call = src.split("def _call(")[1].split("def _parse(")[0]
    assert "reasoning" not in call, "deepseek-flash returns it beside content"


def test_an_exact_name_outranks_one_that_only_normalises():
    from app.build import _films_from_lines
    from app.resolve import score_candidate
    want = _films_from_lines(["Radiohead"])[0]
    real = score_candidate({"name": "Radiohead"}, want)
    fuzzy = score_candidate({"name": "Radio Head"}, want)
    assert real > fuzzy, (real, fuzzy)
    assert score_candidate({"name": "radiohead"}, want) == real


def test_a_disliked_name_never_becomes_an_interest():
    from app.extract import KINDS, Found
    from app.references import resolve
    import app.references as mod

    class Got:
        qloo_name, entity_id, qloo_year = "Tenet", "m9", None

    was = mod.resolve_film
    try:
        mod.resolve_film = lambda q, f, k: Got()
        got = resolve(None, [Found("Tenet", KINDS["film"], False,
                                   "Tenet did nothing for me", 3, "")])
        assert not got.references, "a dislike is not an interest"
        assert got.negative_only and got.negative_only[0].name == "Tenet"
        assert got.negative_only[0].quotes, "but the evidence is kept"
    finally:
        mod.resolve_film = was


def test_two_names_for_one_entity_merge_without_double_counting():
    from app.extract import KINDS, Found
    from app.references import resolve
    import app.references as mod

    class Got:
        def __init__(self, name):
            self.qloo_name, self.entity_id, self.qloo_year = name, "a1", None

    was = mod.resolve_film
    try:
        mod.resolve_film = lambda q, f, k: Got(f.title)
        got = resolve(None, [
            Found("Radiohead", KINDS["artist"], True, "Radiohead", 1, ""),
            Found("Thom Yorke", KINDS["artist"], True, "Thom Yorke", 2, "")])
        assert len(got.references) == 1, "one entity, one reference"
        assert got.references[0].weight == 2.0
        assert len(got.references[0].sources) == 2, "both quotes kept"
    finally:
        mod.resolve_film = was


def test_the_csv_examples_are_served_but_nothing_else_is():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("AUDIENCE_SAMPLES = ("):src.index('@app.get("/api/examples/{slug}")')]
    assert "taste_survey.csv" in block and "audience_preferences.csv" in block
    assert "if name not in AUDIENCE_SAMPLES:" in block, (
        "a path must not be requestable by name")


def test_the_aggregated_path_asks_the_model_for_kinds():
                                                                   
                                                                      
                                                      
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def audience_read("):src.index("def audience_build(")]
    assert "kinds_for(" in block
    assert "proposed.get(c.name)" in block

    extract = (Path(__file__).resolve().parent.parent / "app" / "extract.py").read_text()
    assert "def kinds_for(" in extract
    assert '"unsure"' in extract, "it may still decline"
    types = extract[extract.index("TYPES = "):extract.index("def kinds_for(")]
    assert "Copy each name back exactly" in types
    assert "could be several kinds" in types


def test_every_bad_row_is_named_at_once():
    from app.ingest import BadSource, PREFERENCES, read
    many = ("name,liked_count,disliked_count\n"
            "Arrival,186,14\n"
            "Aftersun,118\n"
            "Her,bad,3\n"
            ",90,3\n"
            "Moon,70,-5\n")
    try:
        read(PREFERENCES, many, "many.csv")
        raise AssertionError("should have refused")
    except BadSource as exc:
        said = str(exc)
        assert "4 rows" in said
        assert "3, 4, 5 and 6" in said, said
        assert "whole numbers" in said

    one = ("name,liked_count,disliked_count\n"
           "Arrival,186,14\nAftersun,118\nHer,90,3\nMoon,70,5\n")
    try:
        read(PREFERENCES, one, "one.csv")
        raise AssertionError("should have refused")
    except BadSource as exc:
        assert str(exc).startswith("Row 3 of one.csv"), str(exc)
