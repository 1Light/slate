#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod
from app import structure as S
from app.qloo import Qloo
from app.resolve import Film, resolve_all


def shape_at(matrix, groups: int, bridge_top: int) -> dict:
    old = S.BRIDGE_TOP_N
    S.BRIDGE_TOP_N = bridge_top
    try:
        a = S.analyse(matrix, groups=groups, stability=False)
        return {
            "clusters": len(a.clusters),
            "largest": max(len(g) for g in a.clusters),
            "bridges": [b["film"] for b in a.bridges],
            "isolated": [i["film"] for i in a.isolated],
        }
    finally:
        S.BRIDGE_TOP_N = old


def main() -> int:
    qloo = Qloo()
    for path in sorted(Path("data/lineups").glob("*.json")):
        if path.stem.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        et = data.get("entity_type", "urn:entity:movie")
        films = [Film(title=f["title"], year=f.get("year", 0),
                      director=f.get("director", ""),
                      aliases=f.get("aliases", []))
                 for f in data["films"]]
        try:
            resolved, _ = resolve_all(qloo, films, et)
            m = matrix_mod.build(qloo, resolved, et)
            a = S.analyse(m, stability=False)
        except Exception as exc:                            # noqa: BLE001
            print(f"\n{path.stem}: skipped ({type(exc).__name__})")
            continue

        n = len(m.films)
        chosen = len(a.clusters)
        print("\n" + "=" * 70)
        print(f"{data.get('name', path.stem)}   n={n}   silhouette picks k={chosen}")
        print("=" * 70)

        print("\n  forced number of groups:")
        print(f"      {'k':>3}  {'largest':>8}  bridges")
        for k in range(2, min(n, 9)):
            r = shape_at(m, k, S.BRIDGE_TOP_N)
            mark = " <- chosen" if k == chosen else ""
            print(f"      {k:>3}  {r['largest']:>8}  "
                  f"{', '.join(r['bridges']) or 'none'}{mark}")

        print("\n  bridge rule strictness, at the chosen k:")
        for top in (2, 3, 5):
            r = shape_at(m, chosen, top)
            print(f"      top-{top}: {', '.join(r['bridges']) or 'none'}")

    print("\nA bridge that appears only at top-5, or a group that only exists")
    print("at one k, is a property of the setting rather than of the slate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
