                      
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audience import (BALANCED, DEMAND_LED, Reference,              
                          select)
from app.build import _films_from_lines                                 
from app.qloo import Qloo, id_of                                        
from app.resolve import resolve_film                                    

FILMS = "urn:entity:movie"

AUDIENCE = [
    ("Arrival", FILMS, 186),
    ("Interstellar", FILMS, 164),
    ("Severance", "urn:entity:tv_show", 152),
    ("Radiohead", "urn:entity:artist", 141),
    ("Blade Runner 2049", FILMS, 128),
    ("The Leftovers", "urn:entity:tv_show", 97),
    ("Aphex Twin", "urn:entity:artist", 74),
    ("Exhalation", "urn:entity:book", 68),
    ("99% Invisible", "urn:entity:podcast", 58),
]

CONTROL = [
    ("Mad Max: Fury Road", FILMS, 150),
    ("Top Gun: Maverick", FILMS, 140),
    ("John Wick", FILMS, 120),
    ("The Rock", "urn:entity:artist", 90),
]

POOL = ["Ex Machina", "Moon", "Primer", "Upstream Color", "Solaris",
        "Stalker", "The Fountain", "Melancholia", "High Life", "Aniara",
        "Coherence", "The Vast of Night", "Gattaca", "Children of Men",
        "Her", "Eternal Sunshine of the Spotless Mind"]

SLOTS = 8


def gather(qloo, names, pool_ids, by_id):
    refs, rankings = [], {}
    for title, kind, weight in names:
        film = _films_from_lines([title])[0]
        got = resolve_film(qloo, film, kind)
        if not got:
            print(f"  {title}: did not resolve, left out")
            continue
        rows = qloo.rank_within(got.entity_id, pool_ids, FILMS)
        order = [by_id[id_of(r)] for r in rows if id_of(r) in by_id]
        if not order:
            print(f"  {title}: no ranking came back, left out")
            continue
        refs.append(Reference(title, kind, got.entity_id, float(weight)))
        rankings[title] = order
    return refs, rankings


def main() -> int:
    qloo = Qloo()

    print(f"resolving {len(POOL)} candidates")
    by_id, pool = {}, []
    for film in _films_from_lines(POOL):
        got = resolve_film(qloo, film, FILMS)
        if got:
            by_id[got.entity_id] = film.title
            pool.append(film.title)
    pool_ids = list(by_id)
    print(f"  {len(pool)} resolved\n")

    print("asking Qloo about the demo audience")
    refs, rankings = gather(qloo, AUDIENCE, pool_ids, by_id)
    print(f"  {len(refs)} references with rankings\n")

    picked = {}
    for mode in (DEMAND_LED, BALANCED):
        got = select(pool, refs, rankings, SLOTS, mode)
        picked[mode] = set(got["chosen"])
        print(f"{mode} ({got['how']}), score {got['score']}, "
              f"weakest {got['weakest']}")
        for title in got["chosen"]:
            print(f"    {title}")
        print("    served:")
        for row in got["served"]:
            print(f"      {row['reference']:<20} {row['best']:.2f} "
                  f"by {row['by']}")
        print()

    same = picked[DEMAND_LED] & picked[BALANCED]
    print(f"the two modes agree on {len(same)} of {SLOTS}")
    only_d = picked[DEMAND_LED] - picked[BALANCED]
    only_b = picked[BALANCED] - picked[DEMAND_LED]
    if only_d or only_b:
        print(f"  only Demand-led: {', '.join(sorted(only_d)) or 'none'}")
        print(f"  only Balanced:   {', '.join(sorted(only_b)) or 'none'}")

    print("\nasking Qloo about a different audience, same pool")
    other, other_rank = gather(qloo, CONTROL, pool_ids, by_id)
    if not other:
        print("  none resolved, cannot run the control")
        return 1
    got = select(pool, other, other_rank, SLOTS, BALANCED)
    print(f"  {', '.join(got['chosen'])}")

    shared = picked[BALANCED] & set(got["chosen"])
    print("\n" + "=" * 68)
    print(f"The two audiences share {len(shared)} of {SLOTS} films.")
    if len(shared) == SLOTS:
        print("IDENTICAL. The audience is not changing the selection, so")
        print("something is wrong: check the rankings actually differ.")
    else:
        print("The audience changes the selection, which is the whole")
        print("claim. Neither result is validated against real behaviour.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
