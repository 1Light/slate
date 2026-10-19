#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod
from app.qloo import Qloo
from app.resolve import Film, resolve_all
from app.structure import analyse


def load(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    et = data.get("entity_type", "urn:entity:movie")
    films = [Film(title=f["title"], year=f.get("year", 0),
                  director=f.get("director", ""), aliases=f.get("aliases", []))
             for f in data["films"]]
    return data, et, films


def run(path, warm: bool):
    data, et, films = load(path)
    qloo = Qloo()
    resolved, missed = resolve_all(qloo, films, et)
    if len(resolved) < 6:
        print(f"\n{data.get('name', path.stem)}: only {len(resolved)}/{len(films)} "
              "resolved, too few to measure")
        return None
    m = matrix_mod.build(qloo, resolved, et)
    a = analyse(m)
    return {
        "name": data.get("name", path.stem),
        "entity": et.rsplit(":", 1)[-1],
        "n": len(m.films),
        "missed": missed,
        "k": len(a.clusters),
        "silhouette": a.cut_check.get("best"),
        "stability": a.stability,
        "clusters": a.clusters,
    }


def main() -> int:
    warm = "--warm" in sys.argv
    rows = []
    for path in sorted(Path("data/lineups").glob("*.json")):
        try:
            r = run(path, warm)
        except Exception as exc:                            # noqa: BLE001
            print(f"\n{path.stem}: skipped ({type(exc).__name__})")
            continue
        if r:
            rows.append(r)

    for r in rows:
        st = r["stability"] or {}
        print("\n" + "=" * 70)
        print(f"{r['name']}   [{r['entity']}]  n={r['n']}")
        print("=" * 70)
        if r["missed"]:
            print(f"  not in Qloo: {', '.join(r['missed'][:5])}")
        sil = r["silhouette"]
        print(f"  {r['k']} groups, silhouette "
              f"{'n/a' if sil is None else f'{sil:+.3f}'}")
        if not st:
            print("  slate too small to leave one out")
            continue
        print(f"  ARI under leave-one-out: {st['ari']:+.3f} over {st['runs']} runs")
        print(f"\n  group        held   chance   lift")
        for c, g in zip(st["clusters"], r["clusters"]):
            if c["jaccard"] is None:
                print(f"  {c['size']:>2} items     --       --     --   singleton")
                continue
            print(f"  {c['size']:>2} items   {c['jaccard']:.2f}     "
                  f"{c['chance']:.2f}   {c['lift']:+.2f}   {c['verdict']}")
            print(f"              {', '.join(g[:3])}"
                  f"{' ...' if len(g) > 3 else ''}")

    print("\n" + "=" * 70)
    print("ACROSS ENTITY TYPES")
    print("=" * 70)
    by = {}
    for r in rows:
        by.setdefault(r["entity"], []).append(r)

    def mean(rows_, key):
        vals = [c[key] for r in rows_ for c in (r["stability"] or {}).get("clusters", [])
                if c.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    print(f"  {'type':<9}{'slates':>7}{'ARI':>8}{'held':>8}{'chance':>8}{'lift':>8}")
    for ent, rs in sorted(by.items()):
        aris = [r["stability"]["ari"] for r in rs
                if r["stability"] and r["stability"].get("ari") is not None]
        print(f"  {ent:<9}{len(rs):>7}"
              f"{sum(aris)/len(aris) if aris else 0:>+8.3f}"
              f"{mean(rs, 'jaccard') or 0:>8.2f}"
              f"{mean(rs, 'chance') or 0:>8.2f}"
              f"{mean(rs, 'lift') or 0:>+8.2f}")

    print("\n  Lift is the column that matters. A pair cannot score a high")
    print("  Jaccard under leave-one-out however real it is, so comparing raw")
    print("  numbers ranks slates by how finely they happened to be cut.")
    print("\n  One lineup per type cannot characterise that type. Film has")
    print("  four. Everything else has one, and shows only that the method")
    print("  survives the change at all.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
