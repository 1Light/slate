#!/usr/bin/env python3
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
