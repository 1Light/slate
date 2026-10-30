from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .qloo import Qloo, id_of, name_of, popularity_of, year_of


@dataclass
class Film:
    title: str
    year: int
    director: str = ""
    origin: str = ""
    aliases: list[str] = field(default_factory=list)

    @property
    def all_titles(self) -> list[str]:
        return [self.title] + self.aliases


@dataclass
class Resolved:
    film: Film
    entity_id: str
    qloo_name: str
    qloo_year: int | None
    popularity: float | None
    score: int

    @property
    def confident(self) -> bool:
        return self.score >= 10

    @property
    def label(self) -> str:
        return "ok" if self.confident else "check"


def normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def score_candidate(entity: dict, film: Film) -> int:
    score = 0
    raw = (name_of(entity) or "").strip().casefold()
    candidate = normalise(name_of(entity))
    titles = [normalise(t) for t in film.all_titles]

    if candidate in titles:
        score += 5
        if any(raw == t.strip().casefold() for t in film.all_titles):
            score += 1
    elif any(t and (t in candidate or candidate in t) for t in titles):
        score += 2

    if film.year:
        y = year_of(entity)
        if y is not None:
            gap = abs(y - film.year)
            score += 5 if gap == 0 else (2 if gap == 1 else -6)

    return score


def resolve_film(qloo: Qloo, film: Film, entity_type: str = "urn:entity:movie") -> Resolved | None:
    good_enough = 10 if film.year else 5

    candidates: list[dict] = []
    for query in film.all_titles:
        candidates.extend(qloo.search(query, types=entity_type))
        if any(score_candidate(c, film) >= good_enough for c in candidates):
            break

    if not candidates:
        return None

    best = max(candidates, key=lambda c: score_candidate(c, film))
    score = score_candidate(best, film)
    entity_id = id_of(best)

    if not entity_id or score < 5:
        return None

    return Resolved(
        film=film,
        entity_id=entity_id,
        qloo_name=name_of(best),
        qloo_year=year_of(best),
        popularity=popularity_of(best),
        score=score,
    )


def resolve_all(qloo: Qloo, films: list[Film],
                entity_type: str = "urn:entity:movie") -> tuple[dict[str, Resolved], list[str]]:
    resolved: dict[str, Resolved] = {}
    failed: list[str] = []
    seen_ids: set[str] = set()

    for film in films:
        result = resolve_film(qloo, film, entity_type)
        if result is None:
            failed.append(film.title)
            continue
        key = result.entity_id.casefold()
        if key in seen_ids:
            failed.append(f"{film.title} (duplicate of an already-resolved entity)")
            continue
        seen_ids.add(key)
        resolved[film.title] = result

    return resolved, failed
