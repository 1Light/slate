#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod            # noqa: E402
from app.qloo import Qloo                       # noqa: E402
from app.resolve import Film, resolve_all       # noqa: E402
from app.structure import _corr, analyse        # noqa: E402

FILM = {
    "resolution": 1.00,
    "completeness": (0.73, 1.00),
    "silhouette": (0.392, 0.431),
}


def main() -> int:
    slug = sys.argv[1] if len(sys.argv) > 1 else "_probe-coachella2024"
    path = Path("data/lineups") / f"{slug}.json"
    if not path.exists():
        print(f"no such lineup: {path}")
        return 2

    data = json.loads(path.read_text(encoding="utf-8"))
    et = data.get("entity_type", "urn:entity:movie")
    items = [Film(title=f["title"], year=f.get("year", 0),
                  director=f.get("director", ""), aliases=f.get("aliases", []))
             for f in data["films"]]

    print(f"{data.get('name', slug)}")
    print(f"entity type: {et}")
    print("=" * 66)

    qloo = Qloo()

    resolved, unresolved = resolve_all(qloo, items, et)
    rate = len(resolved) / len(items)
    print(f"\n1. RESOLUTION   {len(resolved)}/{len(items)} = {rate:.0%}"
          f"   (film: {FILM['resolution']:.0%})")
    for u in unresolved:
        print(f"      missed: {u}")
    if rate < 0.9:
        print("   -> too low. The matrix would be built from a different set "
              "than the one asked about.")

    if len(resolved) < 4:
        print("\nNothing further can be measured.")
        return 1

    m = matrix_mod.build(qloo, resolved, et)
    a = analyse(m)
    frac = a.completeness["fraction"]
    print(f"\n2. MATRIX       {frac:.0%} observed"
          f"   (film: {FILM['completeness'][0]:.0%}-{FILM['completeness'][1]:.0%})")
    print(f"   ghosts: {m.ghosts or 'none'}")

    given = []
    for f in m.films:
        row = [v for v in m.ranks[f].values() if v is not None]
        given.append(sum(row) / len(row))
    spread = max(given) - min(given)
    ok_rows = spread < 1e-9
    print(f"   rows comparable after the censoring fix: "
          f"{'yes' if ok_rows else f'NO, spread {spread:.2f}'}")

    cc = a.cut_check
    print("\n3. CLUSTERING")
    if cc.get("best") is None:
        print("   no cutoff produced 2..n-1 groups. The method has nothing to say.")
        ok_cut = False
    else:
        lo, hi = cc["plateau"]
        width = round((hi - lo) / 0.05) + 1
        ok_cut = cc["best"] > 0.15 and width >= 2
        print(f"   {len(a.clusters)} groups at {cc['chosen']} x n")
        print(f"   silhouette {cc['best']:+.3f} across a plateau {lo}-{hi} "
              f"({width} steps)"
              f"   (film: {FILM['silhouette'][0]:+.3f} to {FILM['silhouette'][1]:+.3f})")
        if not ok_cut:
            print("   -> weak. Either the groups are not separated, or the "
                  "cutoff sits on a knife edge.")

    print("\n4. STRUCTURE")
    print(f"   isolated: {[i['film'] for i in a.isolated] or 'none'}")
    print(f"   bridges:  {[b['film'] for b in a.bridges] or 'none'}")
    r = _corr([a.centrality[f] for f in m.films],
              [a.isolation[f] for f in m.films])
    print(f"   LOF vs mean distance r = {'n/a' if r is None else f'{r:+.2f}'}"
          "   (film: +0.60 to +0.85)")
    if r is not None and abs(r) > 0.95:
        print("   -> LOF has collapsed back into the Borda score. It is adding "
              "nothing here.")

    print("   tightest pairs:")
    for t in a.tightest_pairs[:3]:
        print(f"      {t[2]:5.2f}  {t[0]}  <->  {t[1]}")

    from app.structure import _agglomerate, _cut_to, _silhouette      # noqa: E402
    merges = _agglomerate(m)
    n = len(m.films)
    fine = []
    for i in range(5, 96):
        mult = round(i * 0.01, 2)
        groups = _cut_to(m.films, merges, max(2, round(mult * n)))
        fine.append((mult, len(groups), _silhouette(m, groups)))
    scored = [f for f in fine if f[2] is not None]
    peak = max(s for _, _, s in scored)
    band = [mu for mu, _, s in scored if peak - s <= 1e-9]
    print(f"\n   fine sweep: peak {peak:+.3f} holds from {min(band)} to "
          f"{max(band)} ({len(band)} steps of 0.01)")
    ok_fine = len(band) >= 5
    print(f"   cutoff can move {'±' + format((max(band) - min(band)) / 2, '.2f')}"
          f" before the answer changes: {'robust' if ok_fine else 'FRAGILE'}")

    print("\n" + "=" * 66)
    fails = []
    if rate < 0.9:
        fails.append("resolution")
    if not ok_rows:
        fails.append("row comparability")
    if not ok_fine:
        fails.append("clustering")
    if r is not None and abs(r) > 0.95:
        fails.append("isolation")

    if fails:
        print(f"FAILS: {', '.join(fails)}")
        print("The method does not transfer as-is. Staying with one domain is "
              "the honest call.")
        return 1

    print("PASSES. The entity type behaves like film on every check that")
    print("matters. A second domain is defensible on the data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())