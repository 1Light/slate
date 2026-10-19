#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod          # noqa: E402
from app.qloo import Qloo                      # noqa: E402
from app.resolve import Film, resolve_all      # noqa: E402
from app.structure import analyse              # noqa: E402

RULE = "=" * 70


def load_lineup(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    films = [
        Film(title=f["title"], year=f["year"],
             director=f.get("director", ""), origin=f.get("origin", ""),
             aliases=f.get("aliases", []))
        for f in data["films"]
    ]
    return (data.get("name", path.stem), films,
            data.get("entity_type", "urn:entity:movie"), data.get("note", ""))


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/analyse.py data/lineups/<file>.json")
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Not found: {path}")
        return 2

    name, films, entity_type, note = load_lineup(path)
    print(f"\n{name}  ({len(films)} films)")
    if note:
        print(f"{note}")
    print(RULE)

    qloo = Qloo()

    print("\nRESOLVING")
    resolved, failed = resolve_all(qloo, films, entity_type)
    for title, r in resolved.items():
        pop = "" if r.popularity is None else f"  pop {r.popularity:.3f}"
        print(f"  {r.label:5s} {title:28.28s} -> {r.qloo_name:28.28s} ({r.qloo_year}){pop}")
    print(f"  resolved {len(resolved)}/{len(films)}")
    if failed:
        print(f"  FAILED: {', '.join(failed)}")
    needs_check = [t for t, r in resolved.items() if not r.confident]
    if needs_check:
        print(f"  CHECK BY HAND: {', '.join(needs_check)}")
        print("  A wrong match poisons that film's entire row.")

    if len(resolved) < 4:
        print("\nToo few films resolved to analyse.")
        return 1

    print("\nBUILDING MATRIX")
    m = matrix_mod.build(qloo, resolved, entity_type)
    print(f"  usable films: {len(m.films)}")
    if m.ghosts:
        print(f"  NO INSIGHTS DATA (excluded): {', '.join(m.ghosts)}")
        print("  Resolved in search but returned by no anchor. Excluded rather")
        print("  than given a placeholder rank, which would make them look like")
        print("  the most distinctive films in the programme.")

    a = analyse(m)
    h = a.headline
    c = a.completeness

    print("\n" + RULE)
    print(f"  {h['films']} films  ->  {h['clusters']} audience clusters"
          f"  ->  {h['bridges']} bridge{'' if h['bridges'] == 1 else 's'}")
    print(f"  {h['duplicate_slots']} of {h['films']} slots duplicate an audience already covered")
    print(RULE)

    print("\nCLUSTERS")
    for i, g in enumerate(a.clusters):
        flag = "   <- redundant" if len(g) >= 3 else ""
        print(f"  {i}: {len(g)} film(s){flag}")
        for t in g:
            print(f"       {t}")

    print("\nTIGHTEST PAIRS   (strongest redundancy)")
    for x, y, d, c in a.tightest_pairs:
        print(f"  {d:5.2f}  [cluster {c}]  {x}  <->  {y}")

    print("\nBRIDGES   (the route between audience groups)")
    if not a.bridges:
        print("  None. No film holds a top-3 betweenness position at every")
        print("  sparsification level while connecting different clusters.")
        print("  This programme has no stable route between its audience groups:")
        print("  someone who comes for one cluster has no path into the others.")
    for b in a.bridges:
        pop = "" if b["popularity"] is None else f", popularity {b['popularity']:.3f}"
        print(f"  {b['film']}  (betweenness {b['betweenness']:.3f}{pop})")
        print(f"     connects clusters {b['connects']} via:")
        for v in b["via"]:
            print(f"       - {v} (cluster {a.member[v]})")

    print("\nISOLATED   (sparser neighbourhood than its own neighbours have)")
    if not a.isolated:
        print("  None. No film holds a top-3 LOF position at every k tested.")
        print("  Every film in this slate sits in a neighbourhood about as")
        print("  dense as its neighbours'. Nothing serves an audience alone.")
    for item in a.isolated:
        pop = "" if item["popularity"] is None else f"pop {item['popularity']:.3f}, "
        by_k = " ".join(f"k{k}:{r}" for k, r in sorted(item["by_k"].items()))
        print(f"  LOF {item['lof']:4.2f}  {item['film']}  ({pop}{item['kind']})")
        print(f"            in a cluster of {item['cluster_size']}   rank {by_k}")

    if a.popularity_confound is None:
        print("  Popularity unknown for some films; the confound was not tested.")
    else:
        verdict = ("popularity explains part of this"
                   if a.popularity_confound >= 0.30
                   else "popularity does NOT explain isolation here")
        print(f"  Popularity vs isolation in this slate: r = "
              f"{a.popularity_confound:+.2f}  ({verdict}).")
        print("  Measured per slate rather than assumed. A film is only called")
        print("  'broad appeal' where this slate's own correlation supports it.")

    cc = a.cut_check
    if cc.get("best") is not None:
        lo, hi = cc["plateau"]
        print(f"\nCUTOFF: chose {cc['chosen']} x n for this slate")
        print(f"  Silhouette peaks at {cc['best']:+.3f} across the plateau "
              f"{lo}-{hi}; {cc['chosen']} is its midpoint.")
        if not cc["default_is_optimal"]:
            print(f"  (A fixed {cc['default']} would have scored "
                  f"{cc['default_silhouette']:+.3f} here, outside the plateau.)")

    print(f"\nDATA COMPLETENESS: {c['fraction']:.0%} of the matrix filled")
    if c["incomplete"]:
        shown = c["incomplete"][:6]
        more = len(c["incomplete"]) - len(shown)
        tail = f" (+{more} more)" if more > 0 else ""
        print(f"  Incomplete rows for: {', '.join(shown)}{tail}")
        print("  Lower-popularity films drop out of some anchors' results.")
        print("  Clusters are directionally sound; confidence is uneven.")
        worst = min(c["per_film"].items(), key=lambda kv: kv[1])
        print(f"  Least covered: {worst[0]} at {worst[1]:.0%}")
    else:
        print("  Every film returned by every anchor. Complete matrix.")

    stats = qloo.stats()
    print(f"\nAPI: {stats['live_calls']} live calls, {stats['cache_hits']} cache hits\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())