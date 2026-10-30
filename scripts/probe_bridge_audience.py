#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import statistics as stats
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod            # noqa: E402
from app.build import _load_lineup              # noqa: E402
from app.qloo import Qloo                       # noqa: E402
from app.resolve import resolve_all             # noqa: E402
from app.structure import analyse               # noqa: E402

ML = Path("data/ml-32m")
LINEUPS = ["_probe-bridge", "one-genre", "berlinale2024", "cannes2023",
           "sundance2024"]
MIN_RATERS = 30


def norm(title: str) -> str:
    t = re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip().lower()
    t = re.sub(r"^(the|a|an)\s+", "", t)
    t = re.sub(r",\s*(the|a|an)$", "", t)
    return re.sub(r"[^a-z0-9]+", "", t)


def reach(mine: set, group: list, raters: dict) -> float | None:
    shares = []
    for other in group:
        theirs = raters.get(norm(other))
        if not theirs or len(theirs) < MIN_RATERS:
            continue
        shares.append(len(mine & theirs) / len(theirs))
    return stats.mean(shares) if shares else None


def main() -> int:
    if not (ML / "ratings.csv").exists():
        print(f"MovieLens not found at {ML}/ratings.csv")
        return 2

    want = {}
    for slug in LINEUPS:
        _name, _note, films, _et = _load_lineup(slug)
        for f in films:
            want[norm(f.title)] = f

    ids, titles = {}, {}
    with (ML / "movies.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = norm(row["title"])
            if key not in want:
                continue
            ym = re.search(r"\((\d{4})\)\s*$", row["title"])
            year = int(ym.group(1)) if ym else 0
            asked = want[key].year
            if asked and year and abs(year - asked) > 1:
                continue
            ids[int(row["movieId"])] = key
            titles[key] = row["title"]

    print(f"matched {len(titles)} of {len(want)} titles")
    if len(titles) < 8:
        print("too few to measure")
        return 1

    print("reading ratings")
    raters: dict[str, set] = defaultdict(set)
    with (ML / "ratings.csv").open(encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if row[0] == "userId":
                continue
            mid = int(row[1])
            if mid in ids:
                raters[ids[mid]].add(row[0])
    print(f"   {sum(len(v) for v in raters.values()):,} ratings kept")

    print("\nasking Qloo and grouping each lineup")
    qloo = Qloo()
    bridges, plain, cases, why = [], [], [], []

    for slug in LINEUPS:
        name, _n, films, entity_type = _load_lineup(slug)
        resolved, _missed = resolve_all(qloo, films, entity_type)
        m = matrix_mod.build(qloo, resolved, entity_type)
        a = analyse(m, stability=False)
        member = {t: i for i, c in enumerate(a.clusters) for t in c}
        spans = {b["film"]: b["connects"] for b in a.bridges}

        seen = sum(1 for t in m.films
                   if len(raters.get(norm(t), ())) >= MIN_RATERS)
        named = [b["film"] for b in a.bridges]
        covered = [b for b in named
                   if len(raters.get(norm(b), ())) >= MIN_RATERS]
        why.append(f"{name.split(chr(8212))[0].strip()[:22]:<24} "
                   f"{seen}/{len(m.films)} titles in MovieLens, "
                   f"{len(a.clusters)} groups, "
                   f"bridges {', '.join(named) or 'none'}"
                   + (f" (covered: {', '.join(covered)})" if covered
                      else " (none covered)"))

        for title in m.films:
            key = norm(title)
            mine = raters.get(key)
            if not mine or len(mine) < MIN_RATERS:
                continue
            own = member[title]

            here = reach(mine, [t for t in a.clusters[own] if t != title],
                         raters)
            there = {i: reach(mine, c, raters)
                     for i, c in enumerate(a.clusters) if i != own}
            there = {i: v for i, v in there.items() if v is not None}
            if here is None or not there:
                continue

            best = max(there.values())
            evenness = best / here if here else 0.0

            row = {"lineup": name.split("\u2014")[0].strip(), "title": title,
                   "own": own, "here": here, "best_other": best,
                   "evenness": evenness, "raters": len(mine)}
            if title in spans:
                row["connects"] = spans[title]
                bridges.append(row)
            else:
                plain.append(row)
            cases.append(row)

    if not bridges:
        print("\nno bridges had enough MovieLens coverage to test")
        print("   what was in the way, lineup by lineup:")
        for line in why:
            print(f"      {line}")
        return 1

    print(f"\n{len(bridges)} bridges and {len(plain)} other titles had "
          f"enough coverage")

    def show(rows, label):
        print(f"\n   {label}")
        for r in sorted(rows, key=lambda r: -r["evenness"])[:6]:
            print(f"      {r['evenness']:5.2f}  own {r['here']:.3f}  "
                  f"other {r['best_other']:.3f}  "
                  f"{r['title'][:30]:<32} {r['lineup'][:18]}")

    show(bridges, "bridges, most even first")
    show(plain, "other titles, most even first")

    bm = stats.median(r["evenness"] for r in bridges)
    pm = stats.median(r["evenness"] for r in plain)
    print(f"\n   median evenness: bridges {bm:.3f}, others {pm:.3f}")

    out = Path("data/bridge_audience.json")
    out.write_text(json.dumps({
        "bridges": bridges, "others": plain,
        "bridge_median": bm, "other_median": pm,
        "min_raters": MIN_RATERS,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"   wrote {out}")

    print("\n" + "=" * 64)
    if bm > pm * 1.15:
        print("SUPPORTED. A bridge reaches the group it spans about as well")
        print("as its own, where other titles lean towards their own group.")
        print("Calling it a title that reaches two audiences is fair.")
    elif bm > pm:
        print("WEAKLY SUPPORTED. Bridges are more even than other titles, but")
        print("not by much. The page should say they sit between groups by")
        print("taste rather than claim they reach both audiences.")
    else:
        print("NOT SUPPORTED. Bridges are no more even than anything else.")
        print("The bridge tag describes Qloo's rankings, not shared viewing,")
        print("and the page should say only that.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
