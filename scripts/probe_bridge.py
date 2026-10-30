                      
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod                                    
from app.qloo import Qloo                                               
from app.resolve import Film, resolve_all                               
from app.structure import (KNN_VALUES, _betweenness, _knn,              
                           analyse)

RNG = random.Random(7)
SHUFFLES = 4000


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else None


def main() -> int:
    qloo = Qloo()
    pooled = []

    for path in sorted(Path("data/lineups").glob("*.json")):
        if path.stem.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        films = [Film(title=f["title"], year=f["year"],
                      director=f.get("director", ""),
                      aliases=f.get("aliases", []))
                 for f in data["films"]]
        et = data.get("entity_type", "urn:entity:movie")
        try:
            resolved, _ = resolve_all(qloo, films, et)
            m = matrix_mod.build(qloo, resolved, et)
            a = analyse(m)
        except Exception as exc:                                          
            print(f"\n{data.get('name', path.stem)}: skipped ({type(exc).__name__})")
            continue

        names = m.films
        bc = {f: 0.0 for f in names}
        for k in KNN_VALUES:
            s = _betweenness(names, _knn(m, k))
            for f in names:
                bc[f] += s[f] / len(KNN_VALUES)

        pops = {f: m.popularity(f) for f in names}
        prom = {f: -sum(m.ranks[g][f] for g in names if g != f) / (len(names) - 1)
                for f in names}

        have = [f for f in names if pops[f] is not None]
        r_ext = spearman([bc[f] for f in have], [pops[f] for f in have]) if len(have) > 3 else None
        r_int = spearman([bc[f] for f in names], [prom[f] for f in names])

        print(f"\n{data.get('name', path.stem)}  ({len(names)} films)")
        print(f"  betweenness vs Qloo popularity   rho = "
              f"{'n/a' if r_ext is None else f'{r_ext:+.2f}'}"
              f"   ({len(have)}/{len(names)} films have a popularity value)")
        print(f"  betweenness vs matrix prominence rho = "
              f"{'n/a' if r_int is None else f'{r_int:+.2f}'}")

        top = sorted(names, key=lambda f: -bc[f])[:3]
        print("  highest betweenness:")
        for f in top:
            p = pops[f]
            mark = "  <- reported as a bridge" if f in {b["film"] for b in a.bridges} else ""
            print(f"      {bc[f]:6.3f}  {f:<26.26s} pop "
                  f"{'n/a' if p is None else f'{p:.3f}'}{mark}")

        if a.bridges and have:
            loudest = max(have, key=lambda f: pops[f])
            keep = [f for f in names if f != loudest]
            bc2 = {f: 0.0 for f in keep}
            for k in KNN_VALUES:
                sub = {f: [g for g in _knn(m, k)[f] if g != loudest] for f in keep}
                s = _betweenness(keep, sub)
                for f in keep:
                    bc2[f] += s[f] / len(KNN_VALUES)
            still = sorted(keep, key=lambda f: -bc2[f])[0]
            print(f"  drop the most popular film ({loudest}): "
                  f"highest betweenness becomes {still}")

        for f in have:
            pooled.append((path.stem, bc[f], pops[f]))

    if len(pooled) > 8:
        groups = {}
        for slug, b, p in pooled:
            groups.setdefault(slug, []).append((b, p))
        obs = spearman([b for _, b, _ in pooled], [p for _, _, p in pooled])
        worse = 0
        for _ in range(SHUFFLES):
            xs, ys = [], []
            for rows in groups.values():
                ps = [p for _, p in rows]
                RNG.shuffle(ps)
                xs.extend(b for b, _ in rows)
                ys.extend(ps)
            r = spearman(xs, ys)
            if r is not None and abs(r) >= abs(obs):
                worse += 1
        print("\n" + "=" * 62)
        print(f"POOLED  {len(pooled)} films across {len(groups)} lineups")
        print(f"  observed rho = {obs:+.2f}")
        print(f"  {worse / SHUFFLES:.0%} of {SHUFFLES} within-lineup shuffles "
              f"reached |rho| that large")
        print("  (a diagnostic, not a significance test: betweenness scores "
              "within\n   a lineup are not independent of one another)")

        print()
        if abs(obs) < 0.3:
            print("READ: betweenness is not tracking popularity. The bridge")
            print("finding stands, and the claim that the connector happens to")
            print("be popular is a fact about one film, not about the measure.")
        elif abs(obs) < 0.6:
            print("READ: some association. Keep the feature, drop any claim")
            print("that the connector is independent of fame, and say the")
            print("correlation out loud rather than waiting to be asked.")
        else:
            print("READ: betweenness is largely restating popularity. Reframe")
            print("the bridge as 'the broadly appealing film that also spans")
            print("groups', or take it out of the headline entirely.")
    return 0


if __name__ == "__main__":
    sys.exit(main())