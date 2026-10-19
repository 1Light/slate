#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import _compare_row, _load_lineup, _pipeline   # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "precomputed.json"


def main() -> int:
    rows = []
    for path in sorted((OUT.parent / "lineups").glob("*.json")):
        if path.stem.startswith("_"):
            continue
        slug = path.stem
        name, note, films, entity_type = _load_lineup(slug)
        shape = _pipeline(name, note, films, entity_type, "preset")[-1]
        rows.append(_compare_row(slug, shape))
        print(f"  {slug}: {rows[-1]['clusters']} clusters, "
              f"{rows[-1]['bridges']} bridges")
    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
