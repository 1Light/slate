#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod            # noqa: E402
from app.build import _load_lineup              # noqa: E402
from app.qloo import Qloo                       # noqa: E402
from app.resolve import resolve_all             # noqa: E402

ML = Path("data/ml-32m")
LINEUPS = ["one-genre", "berlinale2024", "cannes2023", "sundance2024"]
MIN_RATERS = 30


def norm(title: str) -> str:
    t = re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip().lower()
    t = re.sub(r"^(the|a|an)\s+", "", t)
    t = re.sub(r",\s*(the|a|an)$", "", t)
    return re.sub(r"[^a-z0-9]+", "", t)


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        share = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[order[k]] = share
        i = j + 1
    return out


def spearman(xs, ys):
    if len(xs) < 3:
        return None
    rx, ry = ranks(xs), ranks(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    top = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    left = math.sqrt(sum((a - mx) ** 2 for a in rx))
    right = math.sqrt(sum((b - my) ** 2 for b in ry))
    return top / (left * right) if left and right else None


def main() -> int:
    if not (ML / "ratings.csv").exists():
        print(f"MovieLens not found at {ML}/ratings.csv")
        return 2

    want = {}
    for slug in LINEUPS:
        name, _note, films, entity_type = _load_lineup(slug)
        for f in films:
            want[norm(f.title)] = (slug, f, entity_type)

    ids, titles, made, genres = {}, {}, {}, {}
    with (ML / "movies.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = norm(row["title"])
            if key not in want:
                continue
            ym = re.search(r"\((\d{4})\)\s*$", row["title"])
            year = int(ym.group(1)) if ym else 0
            asked = want[key][1].year
            if asked and year and abs(year - asked) > 1:
                continue
            ids[int(row["movieId"])] = key
            titles[key] = row["title"]
            made[key] = year
            genres[key] = {g for g in row.get("genres", "").split("|")
                           if g and g != "(no genres listed)"}

    print(f"matched {len(titles)} of {len(want)} films across "
          f"{len(LINEUPS)} lineups")
    if len(titles) < 8:
        print("too few to measure")
        return 1

    print("reading ratings")
    raters = defaultdict(set)
    users = set()
    with (ML / "ratings.csv").open(encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if row[0] == "userId":
                continue
            users.add(row[0])
            mid = int(row[1])
            if mid in ids:
                raters[ids[mid]].add(row[0])
    total = len(users)
    print(f"   {total:,} users in the dataset")
    for k in sorted(raters, key=lambda k: -len(raters[k]))[:3]:
        print(f"   most rated: {titles[k]} ({len(raters[k]):,})")

    print("asking Qloo for distances")
    qloo = Qloo()
    distance = {}
    for slug in LINEUPS:
        name, _n, films, entity_type = _load_lineup(slug)
        resolved, _missed = resolve_all(qloo, films, entity_type)
        m = matrix_mod.build(qloo, resolved, entity_type)
        for i, a in enumerate(m.films):
            for b in m.films[i + 1:]:
                ka, kb = norm(a), norm(b)
                if ka in raters and kb in raters:
                    distance[tuple(sorted((ka, kb)))] = m.distance(a, b)

    rows = []
    for (a, b), d in sorted(distance.items()):
        ua, ub = raters[a], raters[b]
        na, nb = len(ua), len(ub)
        both = len(ua & ub)
        if na < MIN_RATERS or nb < MIN_RATERS or both < 5:
            continue
        union = len(ua | ub)
        jac = both / union if union else 0.0
        expect = na * nb / total
        lift = both / expect if expect else 0.0
        under = math.sqrt(na * nb * (total - na) * (total - nb))
        phi = ((total * both - na * nb) / under) if under else 0.0
        rows.append({
            "pair": (a, b), "d": d, "jaccard": jac, "lift": lift, "phi": phi,
            "fame": min(na, nb), "gap": abs(na - nb),
        })

    if len(rows) < 20:
        print(f"only {len(rows)} usable pairs, not enough")
        return 1

    print(f"\n{len(rows)} pairs with at least {MIN_RATERS} raters each\n")
    ds = [r["d"] for r in rows]

    pops = {}
    for slug in LINEUPS:
        _n2, _nt, films2, et2 = _load_lineup(slug)
        resolved2, _m2 = resolve_all(qloo, films2, et2)
        m2 = matrix_mod.build(qloo, resolved2, et2)
        for t in m2.films:
            pops[norm(t)] = m2.popularity(t)

    gj, yd, pd_, target = [], [], [], []
    for r in rows:
        a, b = r["pair"]
        ga, gb = genres.get(a, set()), genres.get(b, set())
        union = ga | gb
        gj.append(len(ga & gb) / len(union) if union else 0.0)
        yd.append(abs(made.get(a, 0) - made.get(b, 0)))
        pa, pb = pops.get(a), pops.get(b)
        pd_.append(abs(pa - pb) if pa is not None and pb is not None else 0.0)
        target.append(r["phi"])

    baselines = [
        ("Slate distance", spearman(ds, target)),
        ("Shared genres", spearman(gj, target)),
        ("Years apart", spearman(yd, target)),
        ("Popularity gap", spearman(pd_, target)),
    ]
    print("\n  against the same audience overlap:")
    for nm, v in baselines:
        print(f"    {nm:<22} {v:+.3f}" if v is not None
              else f"    {nm:<22}    n/a")


    print("  Slate distance against, by Spearman:")
    for field, label in (("jaccard", "shared raters (Jaccard)"),
                         ("lift", "more shared than chance (lift)"),
                         ("phi", "association (phi)")):
        rho = spearman(ds, [r[field] for r in rows])
        print(f"    {label:<34} {rho:+.3f}" if rho is not None
              else f"    {label:<34} n/a")

    print("\n  the same three against popularity alone:")
    fame = [r["fame"] for r in rows]
    for field, label in (("jaccard", "shared raters (Jaccard)"),
                         ("lift", "more shared than chance (lift)"),
                         ("phi", "association (phi)")):
        rho = spearman(fame, [r[field] for r in rows])
        print(f"    {label:<34} {rho:+.3f}" if rho is not None
              else f"    {label:<34} n/a")

    close = sorted(rows, key=lambda r: r["d"])[:5]
    far = sorted(rows, key=lambda r: -r["d"])[:5]
    print("\n  closest pairs by Slate")
    for r in close:
        a, b = r["pair"]
        print(f"    {titles[a][:28]:<28} / {titles[b][:28]:<28} "
              f"jaccard {r['jaccard']:.3f}  lift {r['lift']:5.2f}")
    print("\n  furthest pairs by Slate")
    for r in far:
        a, b = r["pair"]
        print(f"    {titles[a][:28]:<28} / {titles[b][:28]:<28} "
              f"jaccard {r['jaccard']:.3f}  lift {r['lift']:5.2f}")

    by_distance = sorted(rows, key=lambda r: (r["d"], r["pair"]))
    def row(r):
        a, b = r["pair"]
        return {"a": titles[a], "b": titles[b], "distance": r["d"],
                "overlap": round(r["jaccard"], 4),
                "phi": round(r["phi"], 4), "lift": round(r["lift"], 3),
                "n": r["fame"]}

    vpath = Path("data/validation.json")
    if vpath.exists():
        v = json.loads(vpath.read_text(encoding="utf-8"))
        m = v.setdefault("movielens", {})
        m["overlap_rho"] = spearman(ds, [r["phi"] for r in rows])
        m["overlap_jaccard_rho"] = spearman(ds, [r["jaccard"] for r in rows])
        m["overlap_popularity_rho"] = spearman(fame, [r["phi"] for r in rows])
        m["overlap_pairs"] = len(rows)
        m["closest"] = [row(r) for r in by_distance[:4]]
        m["furthest"] = [row(r) for r in by_distance[-4:]]
        m["all_pairs"] = [row(r) for r in by_distance]
        vpath.write_text(json.dumps(v, indent=2, ensure_ascii=False),
                         encoding="utf-8")
        print(f"\nwrote the overlap figures into {vpath}")

    out = Path("data/overlap.json")
    out.write_text(json.dumps({
        "pairs": len(rows),
        "films": len(titles),
        "users": total,
        "min_raters": MIN_RATERS,
        "slate": {f: spearman(ds, [r[f] for r in rows])
                  for f in ("jaccard", "lift", "phi")},
        "popularity": {f: spearman(fame, [r[f] for r in rows])
                       for f in ("jaccard", "lift", "phi")},
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
