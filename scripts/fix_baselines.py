#!/usr/bin/env python3
"""Put the agreement baselines back into validation.json.

An earlier version of probe_overlap.py wrote baselines measured against
audience overlap into the key the page reads for its metadata test. That
test compares against rating agreement. Against overlap, release year
scores -0.594 against Slate's -0.650, because people watch in eras, so the
table appeared to show metadata nearly matching Qloo.

These are the figures probe_movielens.py prints.

    python3 scripts/fix_baselines.py
"""
import json
from pathlib import Path

RIGHT = [
    {"name": "Slate distance", "rho": -0.498},
    {"name": "Shared genres", "rho": 0.038},
    {"name": "Years apart", "rho": -0.139},
    {"name": "Popularity gap", "rho": 0.06},
]

path = Path("data/validation.json")
v = json.loads(path.read_text(encoding="utf-8"))
was = v["movielens"].get("baselines")
v["movielens"]["baselines"] = RIGHT
path.write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")

print("was:", [(b["name"], b["rho"]) for b in (was or [])])
print("now:", [(b["name"], b["rho"]) for b in RIGHT])