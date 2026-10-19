#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import agent as agent_mod          # noqa: E402
from app import matrix as matrix_mod         # noqa: E402
from app.main import _load_lineup            # noqa: E402
from app.qloo import Qloo, QlooError         # noqa: E402
from app.resolve import resolve_all          # noqa: E402
from app.structure import analyse            # noqa: E402

LINEUPS = Path(__file__).resolve().parent.parent / "data" / "lineups"


def main() -> int:
    total = 0
    for path in sorted(LINEUPS.glob("*.json")):
        name, _note, films, entity_type = _load_lineup(path.stem)
        print(f"\n{name}")
        try:
            qloo = Qloo()
            resolved, failed = resolve_all(qloo, films, entity_type)
            m = matrix_mod.build(qloo, resolved, entity_type)
            a = analyse(m)
            print(f"  shape:  {a.headline['films']} films, "
                  f"{a.headline['clusters']} clusters, "
                  f"{a.headline['bridges']} bridges")
            if failed:
                print(f"  unresolved: {', '.join(failed)}")
            result = agent_mod.improve(qloo, m, a, slate_name=name,
                                       entity_type=entity_type)
            print(f"  agent:  {result.verdict}")
            stats = qloo.stats()
            print(f"  calls:  {stats['live_calls']} live, {stats['cache_hits']} cached")
            total += stats["live_calls"]
        except QlooError as exc:
            print(f"  FAILED: {exc}")
            return 1

    print(f"\nCache warm. {total} live calls made in total.")
    print("The demo now runs without touching Qloo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
