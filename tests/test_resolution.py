from __future__ import annotations

from app.resolve import Film
from app.resolve import score_candidate


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
