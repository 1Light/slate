#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod   # noqa: E402
from app.resolve import Film            # noqa: E402
from app.qloo import Qloo              # noqa: E402
from app.resolve import resolve_all     # noqa: E402
from app.structure import analyse      # noqa: E402

EXAMPLES = Path(__file__).resolve().parent.parent / "data" / "examples"


def main() -> int:
    qloo = Qloo()
    keep = []

    for path in sorted(EXAMPLES.glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        films = [Film(title=f["title"], year=f.get("year", 0)) for f in d["films"]]
        print(f"\n{d['name']}  ({len(films)} given)")

        try:
            resolved, missed = resolve_all(qloo, films, d["entity_type"])
        except Exception as exc:
            print(f"  could not resolve: {type(exc).__name__}")
            continue
        if missed:
            print(f"  not found: {', '.join(missed)}")

        if len(resolved) < 4:
            print(f"  only {len(resolved)} resolved, dropping this set")
            continue

        m = matrix_mod.build(qloo, resolved, d["entity_type"])

        placed = set(m.films)
        named = set(resolved)
        unplaced = sorted(named - placed)
        if unplaced:
            print(f"  RESOLVED BUT NOT PLACED: {', '.join(unplaced)}")
        if missed:
            print(f"  REMOVE THESE: {', '.join(sorted(set(missed) | set(unplaced)))}"
                  if unplaced else f"  REMOVE THESE: {', '.join(missed)}")
        elif unplaced:
            print(f"  REMOVE THESE: {', '.join(unplaced)}")

        a = analyse(m)
        sizes = [len(c) for c in a.clusters]
        bridges = [b["film"] for b in a.bridges]
        alone = [i["film"] for i in a.isolated]
        ari = (a.stability or {}).get("ari")

        print(f"  {len(m.films)} placed, {len(a.clusters)} audiences {sizes}")
        if ari is not None:
            print(f"  ARI {ari:+.3f}")
        if bridges:
            print(f"  bridge: {', '.join(bridges)}")
        if alone:
            print(f"  outlier: {', '.join(alone)}")

        ok = (len(a.clusters) >= 2 and len(m.films) >= len(films) * 0.75
              and (ari is None or ari >= 0.5))
        print(f"  {'KEEP' if ok else 'WEAK, consider rewriting'}")
        if ok:
            keep.append(path.stem)

    print(f"\nusable: {', '.join(keep) if keep else 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
