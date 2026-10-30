from dataclasses import replace

import pytest

from app import audience


POOL = ["p1", "p2", "p3", "p4", "p5", "p6", "n1", "n2"]
RANKINGS = {"popular": POOL, "niche": ["n1", "n2"]}


def references(popular=1000.0, niche=1.0):
    return [
        audience.Reference("popular", "movie", "popular-id", popular),
        audience.Reference("niche", "artist", "niche-id", niche),
    ]


@pytest.mark.parametrize("cap, method", [(200_000, "exhaustive"), (0, "greedy")])
def test_balanced_selection_ignores_support_counts(monkeypatch, cap, method):
    monkeypatch.setattr(audience, "EXHAUSTIVE_CAP", cap)
    results = [audience.select(POOL, references(a, b), RANKINGS, 4,
                               audience.BALANCED)
               for a, b in [(1, 1), (1000, 1), (1, 1000)]]
    assert all(r["how"] == method for r in results)
    assert all(r["chosen"] == results[0]["chosen"] for r in results)
    assert all(r["score"] == 2.0 for r in results)
    assert "p1" in results[0]["chosen"]
    assert "n1" in results[0]["chosen"]


@pytest.mark.parametrize("cap", [200_000, 0])
def test_demand_led_selection_still_uses_support_counts(monkeypatch, cap):
    monkeypatch.setattr(audience, "EXHAUSTIVE_CAP", cap)
    popular = audience.select(POOL, references(1000, 1), RANKINGS, 4,
                               audience.DEMAND_LED)
    niche = audience.select(POOL, references(1, 1000), RANKINGS, 4,
                             audience.DEMAND_LED)
    assert popular["chosen"] == ["p1", "p2", "p3", "p4"]
    assert set(niche["chosen"]) == {"p1", "p2", "n1", "n2"}


@pytest.mark.parametrize("cap", [200_000, 0])
@pytest.mark.parametrize("mode", [audience.BALANCED, audience.DEMAND_LED])
def test_weighting_respects_locked_candidates(monkeypatch, cap, mode):
    monkeypatch.setattr(audience, "EXHAUSTIVE_CAP", cap)
    result = audience.select(POOL, references(), RANKINGS, 4, mode,
                              locked=["p6"])
    assert "p6" in result["chosen"]
    assert len(result["chosen"]) == len(set(result["chosen"])) == 4


def test_all_locked_balanced_score_gives_each_reference_equal_weight():
    result = audience.select(POOL, references(), RANKINGS, 4,
                              audience.BALANCED,
                              locked=["p1", "p2", "n1", "n2"])
    assert result["how"] == "all locked"
    assert result["score"] == 2.0


def test_support_counts_are_preserved_as_audience_evidence():
    refs = references()
    before = [replace(r) for r in refs]
    result = audience.select(POOL, refs, RANKINGS, 4, audience.BALANCED)
    assert refs == before
    assert {r["reference"]: r["weight"] for r in result["served"]} == {
        "popular": 1000.0, "niche": 1.0,
    }


def test_balanced_credits_the_best_match_while_demand_led_adds_matches():
    refs = references(1000, 1)
    utility = audience.utilities(RANKINGS, POOL)
    first = ["p1", "n1"]
    extra = first + ["p2"]
    assert audience.score(first, refs, utility, audience.BALANCED) == 2.0
    assert audience.score(extra, refs, utility, audience.BALANCED) == 2.0
    assert (audience.score(extra, refs, utility, audience.DEMAND_LED)
            > audience.score(first, refs, utility, audience.DEMAND_LED))


@pytest.mark.parametrize("cap", [200_000, 0])
def test_balanced_choices_do_not_change_when_support_moves_between_tastes(monkeypatch, cap):
    monkeypatch.setattr(audience, "EXHAUSTIVE_CAP", cap)
    preferred = ["p1", "p2", "p3", "p4", "n1"]
    refs = [audience.Reference(t, "movie", t, 1.0) for t in preferred]
    rankings = {t: [t] for t in preferred}
    original = audience.select(POOL, refs, rankings, 4, audience.BALANCED)
    weighted = [replace(r, weight=1000.0 if r.title == "n1" else 1.0)
                for r in refs]
    changed = audience.select(POOL, weighted, rankings, 4, audience.BALANCED)
    assert original["chosen"] == changed["chosen"]
    assert original["score"] == changed["score"] == 4.0
