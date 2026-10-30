from __future__ import annotations

import asyncio
import copy
import json

import pytest

from app import main


def _get(path):
    async def run():
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        await main.app({
            "type": "http", "asgi": {"version": "3.0"},
            "http_version": "1.1", "method": "GET", "scheme": "http",
            "path": path, "raw_path": path.encode(), "query_string": b"",
            "root_path": "", "headers": [],
            "client": ("127.0.0.1", 1234), "server": ("test", 80),
        }, receive, send)
        start = next(m for m in messages if m["type"] == "http.response.start")
        body = b"".join(m.get("body", b"") for m in messages
                        if m["type"] == "http.response.body")
        assert start["status"] == 200
        assert dict(start["headers"])[b"content-type"].startswith(b"application/json")
        return json.loads(body)

    return asyncio.run(run())


@pytest.mark.parametrize("field", ["popularity", "bridge_popularity", "top_popularity"])
def test_json_responses_remove_individual_scores_at_every_depth(field):
    payload = {field: 0.9, "films": [{field: 0.8, "title": "Example"}],
               "nested": {"rows": [{field: None, "distance": 2.5}]}}
    before = copy.deepcopy(payload)
    response = main.JSONResponse(payload, status_code=202, headers={"X-Test": "kept"})
    assert json.loads(response.body) == {
        "films": [{"title": "Example"}], "nested": {"rows": [{"distance": 2.5}]}}
    assert payload == before
    assert response.status_code == 202
    assert response.headers["X-Test"] == "kept"
    assert int(response.headers["content-length"]) == len(response.body)


def test_cached_lineup_filters_default_dict_response_without_changing_cache(monkeypatch):
    payload = {"films": [{"title": "Example", "popularity": 0.9, "distance": 1.5}],
               "bridges": [{"title": "Bridge", "popularity": 0.8}],
               "popularity_confound": 0.08, "clusters": [{"films": ["Example"]}]}
    before = copy.deepcopy(payload)
    monkeypatch.setattr(main, "_served", {"example": payload})
    result = _get("/api/lineups/example")
    assert result == {
        "films": [{"title": "Example", "distance": 1.5}],
        "bridges": [{"title": "Bridge"}], "popularity_confound": 0.08,
        "clusters": [{"films": ["Example"]}]}
    assert payload == before


def test_fresh_lineup_filters_default_dict_response(monkeypatch):
    monkeypatch.setattr(main, "_served", {})
    monkeypatch.setattr(main, "_load_lineup", lambda slug: ("Example", "", [], "movie"))
    payload = {"films": [{"title": "Example", "popularity": 0.9, "distance": 1.5}]}
    monkeypatch.setattr(main, "_pipeline", lambda *args: (None, None, None, None, payload))
    assert _get("/api/lineups/example") == {
        "films": [{"title": "Example", "distance": 1.5}]}
    assert payload["films"][0]["popularity"] == 0.9


def test_cached_comparison_filters_explicit_json_response(tmp_path, monkeypatch):
    lineups = tmp_path / "lineups"
    lineups.mkdir()
    cached = tmp_path / "precomputed.json"
    payload = [{"name": "Example", "bridge_popularity": 0.9, "clusters": 3}]
    cached.write_text(json.dumps(payload))
    monkeypatch.setattr(main, "LINEUPS", lineups)
    assert _get("/api/compare") == [{"name": "Example", "clusters": 3}]
    assert json.loads(cached.read_text()) == payload


def test_fresh_comparison_filters_explicit_json_response(tmp_path, monkeypatch):
    lineups = tmp_path / "lineups"
    lineups.mkdir()
    (lineups / "example.json").write_text("{}")
    monkeypatch.setattr(main, "LINEUPS", lineups)
    monkeypatch.setattr(main, "_load_lineup", lambda slug: ("Example", "", [], "movie"))
    monkeypatch.setattr(main, "_pipeline", lambda *args: ({},))
    monkeypatch.setattr(main, "_compare_row", lambda *args: {
        "name": "Example", "bridge_popularity": 0.9, "clusters": 3})
    assert _get("/api/compare") == [{"name": "Example", "clusters": 3}]


def test_validation_preserves_distances_and_summary_evidence(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    payload = {
        "bridge": {"rows": [{"top_popularity": 0.9, "rho": 0.08}],
                   "caught": {"top_popularity": 0.7, "title": "Example"},
                   "pooled_rho": 0.08, "films": 62},
        "movielens": {"closest": [{"a": "A", "b": "B", "distance": 1.5,
                                    "phi": 0.35, "n": 100}],
                      "overlap_popularity_rho": 0.251,
                      "baselines": [{"name": "Popularity gap", "rho": 0.06}]},
        "groups": {"inside_mean": 0.3478, "between_mean": 0.2401, "p": 0.0001},
        "lineup_ari": [{"name": "Example", "ari": 0.97}],
    }
    cached = data / "validation.json"
    cached.write_text(json.dumps(payload))
    monkeypatch.setattr(main, "ROOT", tmp_path)
    result = _get("/api/validation")
    expected = copy.deepcopy(payload)
    del expected["bridge"]["rows"][0]["top_popularity"]
    del expected["bridge"]["caught"]["top_popularity"]
    assert result == expected
    assert json.loads(cached.read_text()) == payload


def test_health_response_still_works():
    assert _get("/health") == {"ok": True}
