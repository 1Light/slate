                      
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.build import (LINEUPS, _bridge_check, _compare_row,               
                       _load_lineup, _pipeline)

DATA = Path(__file__).resolve().parent.parent / "data"


def _without_qloo_values(shape: dict) -> dict:
    out = dict(shape)
    for key in ("films", "bridges", "isolated"):
        rows = out.get(key)
        if isinstance(rows, list):
            out[key] = [{k: v for k, v in r.items() if k != "popularity"}
                        if isinstance(r, dict) else r for r in rows]
    return out


def main() -> int:
    rows, served = [], {}

    for path in sorted(LINEUPS.glob("*.json")):
        slug = path.stem
        name, note, films, entity_type = _load_lineup(slug)
        try:
            shape = _pipeline(name, note, films, entity_type, "preset")[-1]
        except Exception as exc:
            print(f"  {slug}: skipped ({type(exc).__name__})")
            continue
        served[slug] = _without_qloo_values(shape)
        if slug.startswith("_"):
            print(f"  {slug}: {len(shape['clusters'])} groups  (probe)")
            continue
        rows.append(_compare_row(slug, shape))
        print(f"  {slug}: {rows[-1]['clusters']} clusters, "
              f"{rows[-1]['bridges']} bridges")

    (DATA / "precomputed.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8")
    (DATA / "served.json").write_text(
        json.dumps(served, ensure_ascii=False), encoding="utf-8")

    v_path = DATA / "validation.json"
    v = json.loads(v_path.read_text(encoding="utf-8")) if v_path.exists() else {}
    try:
        v["bridge"] = _bridge_check()
    except Exception as exc:
        print(f"  bridge check skipped ({type(exc).__name__})")
    v["lineup_ari"] = [
        {"name": s["name"].split("\u2014")[0].strip(),
         "ari": s["stability"]["ari"]}
        for slug, s in served.items()
        if not slug.startswith("_") and s.get("stability")
        and s["stability"].get("ari") is not None
    ]
    v["lineup_ari"].sort(key=lambda r: -r["ari"])
    v_path.write_text(json.dumps(v, indent=2, ensure_ascii=False),
                      encoding="utf-8")

    print(f"wrote {DATA / 'precomputed.json'}")
    print(f"wrote {DATA / 'served.json'}  ({len(served)} lineups)")
    print(f"wrote {v_path}  (bridge check and lineup ARI)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
