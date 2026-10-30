                      
from __future__ import annotations

import statistics as stats
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod                        
from app.build import _load_lineup, _films_from_lines               
from app.qloo import Qloo, id_of                            
from app.resolve import resolve_all                         


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--slug":
        name, _note, films, entity_type = _load_lineup(args[1])
    elif args:
        films = _films_from_lines(args)
        name, entity_type = "your lineup", "urn:entity:movie"
    else:
        print(__doc__)
        return 2

    qloo = Qloo()
    resolved, missed = resolve_all(qloo, films, entity_type)
    if missed:
        print(f"not found: {', '.join(missed)}")
    titles = list(resolved)
    print(f"{name}: {len(titles)} titles\n")

    ids = {t: resolved[t].entity_id for t in titles}
    answered = {}
    for anchor in titles:
        others = [t for t in titles if t != anchor]
        rows = qloo.rank_within(ids[anchor], [ids[t] for t in others],
                                entity_type)
        got = {id_of(e).casefold() for e in rows if id_of(e)}
        back = sum(1 for t in others if ids[t].casefold() in got)
        answered[anchor] = (back, len(others))

    m = matrix_mod.build(qloo, resolved, entity_type)
    far = {t: stats.mean(m.distance(t, o) for o in m.films if o != t)
           for t in m.films}

    print(f"  {'title':<34} {'mean dist':>9}  {'Qloo answered':>14}")
    for t in sorted(far, key=lambda x: -far[x]):
        back, asked = answered.get(t, (0, 0))
        share = f"{back}/{asked}"
        flag = "  <- mostly filled" if asked and back < asked * 0.4 else ""
        print(f"  {t[:34]:<34} {far[t]:9.2f}  {share:>14}{flag}")

    thin = [t for t, (b, a) in answered.items() if a and b < a * 0.4]
    print("\n" + "=" * 66)
    if not thin:
        print("Every title got a real answer for most of its row, so the")
        print("distances reflect Qloo's rankings rather than filled gaps.")
    else:
        print("These titles had most of their row filled rather than ranked:")
        for t in thin:
            print(f"   {t}")
        print()
        print("Their distance is partly Slate's midpoint, not Qloo placing")
        print("them far. If they are the ones dominating the split, the")
        print("separation may be an artefact of missing answers.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
