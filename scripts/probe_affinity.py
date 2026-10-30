                      
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.build import ENTITY_LABEL, _films_from_lines               
from app.qloo import Qloo, id_of, name_of                           
from app.resolve import resolve_film                                

FILMS = "urn:entity:movie"

REFERENCES = [
    ("Arrival", FILMS),
    ("Dune", FILMS),
    ("Severance", "urn:entity:tv_show"),
    ("The Leftovers", "urn:entity:tv_show"),
    ("Radiohead", "urn:entity:artist"),
    ("Aphex Twin", "urn:entity:artist"),
    ("Exhalation", "urn:entity:book"),
    ("Klara and the Sun", "urn:entity:book"),
    ("99% Invisible", "urn:entity:podcast"),
    ("Radiolab", "urn:entity:podcast"),
]

POOL = ["Ex Machina", "Moon", "Primer", "Upstream Color", "Solaris",
        "Stalker", "The Fountain", "Melancholia", "High Life", "Aniara",
        "Coherence", "The Vast of Night", "Gattaca", "Children of Men",
        "Her", "Eternal Sunshine of the Spotless Mind"]


def main() -> int:
    qloo = Qloo()

    print(f"resolving the pool of {len(POOL)} films")
    pool = {}
    for film in _films_from_lines(POOL):
        got = resolve_film(qloo, film, FILMS)
        if got:
            pool[got.entity_id] = film.title
    print(f"  {len(pool)} of {len(POOL)} resolved\n")
    if len(pool) < 4:
        print("too few to continue")
        return 1

    ids = list(pool)
    worked, empty = [], []

    for title, kind in REFERENCES:
        film = _films_from_lines([title])[0]
        anchor = resolve_film(qloo, film, kind)
        label = ENTITY_LABEL[kind]
        if not anchor:
            print(f"  {title:<24} {label:<16} did not resolve")
            empty.append(title)
            continue

        rows = qloo.rank_within(anchor.entity_id, ids, FILMS)
        back = [pool.get(id_of(r)) or name_of(r) for r in rows]
        share = f"{len(rows)}/{len(ids)}"
        if not rows:
            empty.append(f"{title} ({label})")
            print(f"  {title:<24} {label:<16} nothing came back")
            continue

        worked.append(title)
        top = ", ".join(str(b) for b in back[:3])
        print(f"  {title:<24} {label:<16} {share:>6}   {top}")

    print("\n" + "=" * 72)
    if not empty:
        print("Every reference returned a ranking over the film pool,")
        print("including the ones that are not films. Cross-domain")
        print("affinity works and the selector has evidence to score on.")
    else:
        print("These returned nothing, so they cannot contribute:")
        for item in empty:
            print(f"  {item}")
        print()
        print("If the cross-domain ones are among them, references of that")
        print("kind cannot inform a film selection and the design must say")
        print("so rather than silently ignoring them.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
