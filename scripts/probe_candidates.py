                      
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.build import ENTITY_LABEL, _films_from_lines               
from app.qloo import Qloo                                           
from app.resolve import resolve_all                                 

HERE = Path("data/candidates")


def main() -> int:
    qloo = Qloo()
    bad = 0

    taken = set()
    for path in Path("data/examples").glob("*.json"):
        d = json.loads(path.read_text(encoding="utf-8"))
        for f in d["films"]:
            taken.add(f["title"].lower())

    for kind, label in ENTITY_LABEL.items():
        path = HERE / f"{kind.rsplit(':', 1)[1]}.json"
        if not path.exists():
            print(f"{label:<12} no file")
            bad += 1
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        every = sorted(set(d.get("one", []) + d.get("many", [])))
        films = _films_from_lines(every)
        resolved, missed = resolve_all(qloo, films, kind)
        ok = len(resolved)
        print(f"{label:<12} {ok}/{len(every)} placed")
        for t in missed:
            print(f"               REMOVE  {t}  (not found)")
            bad += 1
        for t in every:
            if t.lower() in taken:
                print(f"               REMOVE  {t}  (already in an example)")
                bad += 1
    print("\nall candidates place" if not bad else f"\n{bad} to fix")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
