from __future__ import annotations

from dataclasses import dataclass, field

from .audience import Reference
from .build import ENTITY_LABEL, _films_from_lines
from .resolve import resolve_film

ALL_KINDS = tuple(ENTITY_LABEL)
CLEAR_WIN = 1


@dataclass
class Unresolved:

    name: str
    why: str
    quotes: list[str] = field(default_factory=list)


@dataclass
class Review:

    references: list[Reference] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)
    negative_only: list[Unresolved] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return bool(self.references)


def _pool(found: list) -> dict:
    out: dict[str, dict] = {}
    for item in found:
        key = item.name.casefold()
        row = out.setdefault(key, {
            "name": item.name, "kind": item.kind,
            "liked": 0, "disliked": 0, "sources": [],
        })
        if item.liked:
            row["liked"] += 1
        else:
            row["disliked"] += 1
        if row["kind"] is None and item.kind:
            row["kind"] = item.kind
        row["sources"].append({
            "quote": item.quote,
            "question": item.question,
            "row": item.row,
            "liked": item.liked,
        })
    return out


def resolve(qloo, found: list, counts: dict | None = None) -> Review:
    review = Review()
    counts = counts or {}

    for key, row in _pool(found).items():
        name = row["name"]
        tally = counts.get(key) or counts.get(name) or {}
        liked = tally.get("liked", row["liked"])
        disliked = tally.get("disliked", row["disliked"])
        quotes = [s["quote"] for s in row["sources"] if s["quote"]]

        film = _films_from_lines([name])[0]
        if not row["kind"]:
            got, kind, why = _search_all(qloo, film)
            if not got:
                review.unresolved.append(Unresolved(
                    name=name, why=why, quotes=quotes))
                continue
            row["kind"] = kind
        else:
            got = resolve_film(qloo, film, row["kind"])

        if got and liked <= 0:
            review.negative_only.append(Unresolved(
                name=name,
                why="only mentioned negatively, so it is not an interest",
                quotes=quotes))
            continue
        if not got:
            label = ENTITY_LABEL.get(row["kind"], "titles")
            review.unresolved.append(Unresolved(
                name=name,
                why=f"no match among {label} in Qloo's catalogue",
                quotes=quotes))
            continue

        review.references.append(Reference(
            title=got.qloo_name or name,
            entity_type=row["kind"],
            entity_id=got.entity_id,
            weight=float(liked),
            disliked=disliked,
            sources=row["sources"],
        ))

    merged: dict[str, Reference] = {}
    for ref in review.references:
        was = merged.get(ref.entity_id)
        if was is None:
            merged[ref.entity_id] = ref
            continue
        was.weight += ref.weight
        was.disliked += ref.disliked
        seen = {(s.get("row"), s.get("quote")) for s in was.sources}
        was.sources.extend(s for s in ref.sources
                           if (s.get("row"), s.get("quote")) not in seen)
    review.references = sorted(merged.values(), key=lambda r: -r.weight)
    return review


def _search_all(qloo, film):
    found = []
    for kind in ALL_KINDS:
        got = resolve_film(qloo, film, kind)
        if got:
            found.append((got.score, kind, got))

    if not found:
        return None, None, "not found in Qloo's catalogue"

    found.sort(key=lambda row: -row[0])
    best = found[0]
    if len(found) > 1 and best[0] - found[1][0] < CLEAR_WIN:
        labels = [ENTITY_LABEL[k] for _, k, _ in found[:3]]
        kinds = (" and ".join(labels) if len(labels) < 3
                 else f"{', '.join(labels[:-1])} and {labels[-1]}")
        return None, None, (f"matched {kinds} about equally, and nothing "
                            "in the source settles which")
    return best[2], best[1], ""


def by_kind(refs: list[Reference]) -> dict[str, list[Reference]]:
    out: dict[str, list[Reference]] = {}
    for ref in refs:
        out.setdefault(ref.entity_type, []).append(ref)
    return out
