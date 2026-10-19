from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _cache_dir() -> Path:
    configured = os.getenv("SLATE_CACHE_DIR", "").strip()
    return Path(configured) if configured else PROJECT_ROOT / "data" / "cache"


def _base_url() -> str:
    configured = os.getenv("QLOO_BASE_URL", "").strip()
    return (configured or "https://hackathon.api.qloo.com").rstrip("/")


BASE_URL = _base_url()
CACHE_DIR = _cache_dir()
TIMEOUT = 25
PAUSE = 0.12
MAX_RETRIES = 3


class QlooError(RuntimeError):
    pass


class Qloo:
    def __init__(self, api_key: str | None = None, use_cache: bool = True):
        self.api_key = (api_key or os.getenv("QLOO_API_KEY", "")).strip()
        if not self.api_key:
            raise QlooError(
                "QLOO_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self.base_url = _base_url()
        self.cache_dir = _cache_dir()
        self.use_cache = use_cache
        self.session = requests.Session()
        self.calls_made = 0
        self.cache_hits = 0
        self.cache_dir.mkdir(parents=True, exist_ok=True)


    def _cache_path(self, path: str, params: dict[str, Any]) -> Path:
        canonical = json.dumps({"path": path, "params": params}, sort_keys=True)
        digest = hashlib.sha256(canonical.encode()).hexdigest()[:24]
        stem = path.strip("/").replace("/", "_") or "root"
        return self.cache_dir / f"{stem}_{digest}.json"

    def _read_cache(self, path: Path) -> dict[str, Any] | None:
        if not self.use_cache or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _write_cache(self, path: Path, payload: dict[str, Any]) -> None:
        if not self.use_cache:
            return
        try:
            path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass


    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {k: v for k, v in params.items() if v is not None}
        cache_file = self._cache_path(path, params)

        cached = self._read_cache(cache_file)
        if cached is not None:
            self.cache_hits += 1
            return cached

        headers = {"X-Api-Key": self.api_key, "Accept": "application/json"}
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                r = self.session.get(f"{self.base_url}{path}", headers=headers,
                                     params=params, timeout=TIMEOUT)
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(1.5 * (attempt + 1))
                continue

            self.calls_made += 1

            if r.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
                last_error = "429 rate limited"
                continue
            if r.status_code >= 500:
                time.sleep(1.5 * (attempt + 1))
                last_error = f"{r.status_code} server error"
                continue
            if r.status_code == 401:
                raise QlooError(
                    "401 from Qloo. Hackathon keys only work against "
                    "https://hackathon.api.qloo.com and must be sent in the "
                    "X-Api-Key header."
                )
            if not r.ok:
                raise QlooError(f"HTTP {r.status_code} on {path}: {r.text[:200]}")

            try:
                payload = r.json()
            except ValueError as exc:
                raise QlooError(f"Non-JSON response from {path}") from exc

            self._write_cache(cache_file, payload)
            time.sleep(PAUSE)
            return payload

        raise QlooError(f"{path} failed after {MAX_RETRIES} attempts: {last_error}")


    def search(self, query: str, types: str = "urn:entity:movie", take: int = 5) -> list[dict]:
        payload = self._get("/search", {"query": query, "types": types, "take": take})
        return entities_of(payload)

    def entity(self, entity_id: str) -> dict | None:
        found = entities_of(self._get("/entities", {"entity_ids": entity_id}))
        return found[0] if found else None

    def rank_within(self, anchor_id: str, candidate_ids: list[str],
                    filter_type: str = "urn:entity:movie",
                    explain: bool = False) -> list[dict]:
        if not candidate_ids:
            return []
        params = {
            "filter.type": filter_type,
            "signal.interests.entities": anchor_id,
            "filter.results.entities": ",".join(candidate_ids),
            "take": min(len(candidate_ids), 50),
        }
        if explain:
            params["feature.explainability"] = "true"
        return entities_of(self._get("/v2/insights", params))

    def neighbours(self, signal_ids: list[str], filter_type: str = "urn:entity:movie",
                   take: int = 20, exclude: list[str] | None = None,
                   popularity_max: float | None = None) -> list[dict]:
        if not signal_ids:
            return []
        params = {
            "filter.type": filter_type,
            "signal.interests.entities": ",".join(signal_ids),
            "take": min(take, 50),
        }
        if exclude:
            params["filter.exclude.entities"] = ",".join(exclude)
        if popularity_max is not None:
            params["filter.popularity.max"] = popularity_max
        return entities_of(self._get("/v2/insights", params))

    def stats(self) -> dict[str, int]:
        return {"live_calls": self.calls_made, "cache_hits": self.cache_hits}


def entities_of(payload: Any) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    if isinstance(results, dict) and isinstance(results.get("entities"), list):
        return [x for x in results["entities"] if isinstance(x, dict)]
    if isinstance(results, list):
        return [x for x in results if isinstance(x, dict)]
    if isinstance(payload.get("entities"), list):
        return [x for x in payload["entities"] if isinstance(x, dict)]
    return []


def name_of(entity: dict) -> str:
    for key in ("name", "title"):
        value = entity.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    props = entity.get("properties")
    if isinstance(props, dict):
        value = props.get("name") or props.get("title")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "<unnamed>"


def id_of(entity: dict) -> str | None:
    for key in ("entity_id", "id"):
        value = entity.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    return None


def year_of(entity: dict) -> int | None:
    props = entity.get("properties")
    if isinstance(props, dict):
        for key in ("release_year", "release_date"):
            value = props.get(key)
            if value:
                try:
                    return int(str(value)[:4])
                except ValueError:
                    pass
    return None


def popularity_of(entity: dict) -> float | None:
    value = entity.get("popularity")
    if isinstance(value, (int, float)):
        return float(value)
    props = entity.get("properties")
    if isinstance(props, dict) and isinstance(props.get("popularity"), (int, float)):
        return float(props["popularity"])
    return None
