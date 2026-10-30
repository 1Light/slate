                      
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod                        
from app.qloo import Qloo                                   
from app.resolve import Film, resolve_all                   
from app.structure import _corr, analyse                    


def main() -> int:
    qloo = Qloo()
    bad = 0

    for path in sorted(Path("data/lineups").glob("*.json")):
        if path.stem.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        films = [Film(title=f["title"], year=f["year"],
                      director=f.get("director", ""), aliases=f.get("aliases", []))
                 for f in data["films"]]
        et = data.get("entity_type", "urn:entity:movie")
        try:
            resolved, _ = resolve_all(qloo, films, et)
            m = matrix_mod.build(qloo, resolved, et)
            a = analyse(m)
        except Exception as exc:                                     
            print(f"\n{data.get('name', path.stem)}")
            print(f"  [ -- ] skipped: {type(exc).__name__}. "
                  "Run scripts/warm_cache.py first.")
            continue
        names = m.films
        n = len(names)

        print(f"\n{data.get('name', path.stem)}  ({n} films)")
        print(f"  observed {a.completeness['fraction']:.0%} of the matrix; "
              f"the rest filled as censored")

        given = []
        for f in names:
            row = [v for v in m.ranks[f].values() if v is not None]
            given.append(sum(row) / len(row))
        spread = max(given) - min(given)
        ok = spread < 1e-9
        bad += not ok
        print(f"  [{'ok ' if ok else 'BAD'}] mean rank given is "
              f"{'identical' if ok else f'spread by {spread:.2f}'} across films")

        cen = [a.centrality[f] for f in names]
        lof = [a.isolation[f] for f in names]
        r = _corr(cen, lof)
        ok = r is None or abs(r) < 0.9
        bad += not ok
        print(f"  [{'ok ' if ok else 'BAD'}] LOF vs mean distance r = "
              f"{'n/a' if r is None else f'{r:+.2f}'}"
              f"{'' if ok else '  -- LOF is just the Borda score again'}")

        c = a.popularity_confound
        print(f"  [   ] popularity vs isolation r = "
              f"{'n/a' if c is None else f'{c:+.2f}'}"
              f"   ({'supports' if c is not None and c >= 0.30 else 'does not support'}"
              " a 'broad appeal' label)")

        cc = a.cut_check
        if cc.get("best") is not None:
            tie = cc.get("within_noise") or []
            print(f"  [   ] {cc['chosen']} groups, silhouette {cc['best']:+.3f}"
                  + (f"; {len(tie)} counts scored within noise, fewest taken"
                     if len(tie) > 1 else ""))

        st = a.stability
        if st and st.get("ari") is not None:
            weak = [c for c in st["clusters"]
                    if c.get("lift") is not None and c["lift"] < 0.10]
            bad += bool(weak)
            print(f"  [{'BAD' if weak else 'ok '}] groups survive leaving one "
                  f"film out: ARI {st['ari']:+.3f} over {st['runs']} runs")
            for c in st["clusters"]:
                if c.get("lift") is None:
                    continue
                print(f"           {c['size']:>2} items  held {c['jaccard']:.2f}  "
                      f"chance {c['chance']:.2f}  lift {c['lift']:+.2f}  "
                      f"{c['verdict']}")
            if weak:
                print("           -> a group no better than chance is not a "
                      "finding")

    print(f"\n{'all checks passed' if not bad else f'{bad} CHECK(S) FAILED'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
