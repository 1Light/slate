#!/usr/bin/env python
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.build import _load_lineup        # noqa: E402
from app.qloo import Qloo, id_of          # noqa: E402
from app.resolve import resolve_all       # noqa: E402

ROUNDS = 3


def main() -> int:
    slug = sys.argv[1] if len(sys.argv) > 1 else "sundance2024"
    name, _note, films, entity_type = _load_lineup(slug)

    qloo = Qloo()
    resolved, missed = resolve_all(qloo, films, entity_type)
    if missed:
        print(f"could not resolve: {', '.join(missed)}")
    titles = list(resolved)
    ids = {t: resolved[t].entity_id for t in titles}
    print(f"{name}: {len(titles)} titles\n")

    # Every round must be a real call, so point the cache somewhere
    # throwaway rather than switching it off, which the path builder needs.
    import tempfile
    scratch = Path(tempfile.mkdtemp(prefix="slate-censor-"))
    qloo.cache_dir = scratch

    short_anchors = []
    for anchor in titles:
        others = [t for t in titles if t != anchor]
        want = len(others)

        seen = []
        for round_no in range(ROUNDS):
            # A fresh directory per round, or round two reads round one.
            qloo.cache_dir = scratch / str(round_no)
            qloo.cache_dir.mkdir(parents=True, exist_ok=True)
            rows = qloo.rank_within(ids[anchor], [ids[t] for t in others],
                                    entity_type)
            got = {id_of(e).casefold() for e in rows if id_of(e)}
            seen.append(got)
            time.sleep(0.2)

        sizes = {len(s) for s in seen}
        if sizes == {want}:
            continue

        same = all(s == seen[0] for s in seen)
        short_anchors.append((anchor, want, sizes, same))
        mark = "same set each time" if same else "SET VARIED"
        print(f"  {anchor[:30]:<32} asked {want}, got {sorted(sizes)}  {mark}")

    print()
    if not short_anchors:
        print("Every request returned everything asked for. Nothing to fill.")
        return 0

    varied = [a for a in short_anchors if not a[3]]
    print(f"{len(short_anchors)} of {len(titles)} anchors came back short.")

    print("\n" + "=" * 64)
    if varied:
        print("FLAKY. The set of missing titles changed between identical")
        print(f"requests on {len(varied)} anchor(s). That is noise, not Qloo")
        print("declining to rank. Slate should retry before filling.")
    else:
        print("DETERMINISTIC. The same titles are missing every time, so Qloo")
        print("is leaving out what it has no basis for ranking rather than")
        print("dropping them at random. Filling with the midpoint is the")
        print("right call, and retrying would change nothing.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())