#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod
from app.qloo import Qloo
from app.resolve import Film, resolve_all

ML = Path("data/ml-32m")
MIN_RATERS = 30


def norm(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"\s*\(\d{4}\)\s*$", "", t)
    m = re.match(r"^(.*),\s*(the|a|an|la|le|les|el|il|der|die|das)$", t)
    if m:
        t = f"{m.group(2)} {m.group(1)}"
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    if len(xs) < 3:
        return None
    rx, ry = ranks(xs), ranks(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else None


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


def main() -> int:
    if not (ML / "ratings.csv").exists():
        print(f"MovieLens not found at {ML}/ratings.csv")
        return 2

    slug = sys.argv[1] if len(sys.argv) > 1 else "one-genre"
    data = json.loads((Path("data/lineups") / f"{slug}.json")
                      .read_text(encoding="utf-8"))
    wanted = {norm(f["title"]) for f in data["films"]}
    years = {norm(f["title"]): f.get("year", 0) for f in data["films"]}

    print(f"{data.get('name', slug)}")
    print("=" * 64)

    ids, titles, genres, made = {}, {}, {}, {}
    with (ML / "movies.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = norm(row["title"])
            if key not in wanted:
                continue
            ym = re.search(r"\((\d{4})\)\s*$", row["title"])
            year = int(ym.group(1)) if ym else 0
            want = years[key]
            if want and year and abs(year - want) > 1:
                continue
            ids[int(row["movieId"])] = key
            titles[key] = row["title"]
            genres[key] = {g for g in row.get("genres", "").split("|")
                           if g and g != "(no genres listed)"}
            made[key] = year

    found = sorted(titles)
    print(f"\nmatched {len(found)}/{len(wanted)} films")
    if len(found) < 4:
        return 1

    tagged = [genres[k] for k in found if genres.get(k)]
    shared = set.intersection(*tagged) if tagged else set()
    if shared:
        print(f"every film here is tagged {' and '.join(sorted(shared))}")

    by_user = defaultdict(dict)
    with (ML / "ratings.csv").open(encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if row[0] == "userId":
                continue
            mid = int(row[1])
            if mid in ids:
                by_user[int(row[0])][ids[mid]] = float(row[2])

    human = {}
    for i, a in enumerate(found):
        for b in found[i + 1:]:
            xs, ys = [], []
            for seen in by_user.values():
                if a in seen and b in seen:
                    xs.append(seen[a])
                    ys.append(seen[b])
            if len(xs) < MIN_RATERS:
                continue
            r = pearson(xs, ys)
            if r is not None:
                human[(a, b)] = r

    print(f"{len(human)} pairs with {MIN_RATERS}+ co-raters")
    if len(human) < 10:
        return 1

    qloo = Qloo()
    et = data.get("entity_type", "urn:entity:movie")
    films = [Film(title=f["title"], year=f["year"],
                  director=f.get("director", ""), aliases=f.get("aliases", []))
             for f in data["films"]]
    resolved, _ = resolve_all(qloo, films, et)
    m = matrix_mod.build(qloo, resolved, et)
    back = {norm(t): t for t in m.films}
    pops = {norm(t): m.popularity(t) for t in m.films}

    qd, gj, yd, fg, agree = [], [], [], [], []
    for (a, b), r in human.items():
        if a not in back or b not in back:
            continue
        qd.append(m.distance(back[a], back[b]))
        ga, gb = genres.get(a, set()), genres.get(b, set())
        union = ga | gb
        gj.append(len(ga & gb) / len(union) if union else 0.0)
        yd.append(abs(made.get(a, 0) - made.get(b, 0)))
        pa, pb = pops.get(a), pops.get(b)
        fg.append(abs(pa - pb) if pa is not None and pb is not None else 0.0)
        agree.append(r)

    rows = [
        ("Qloo distance", spearman(qd, agree), "cultural affinity"),
        ("Genre overlap", spearman(gj, agree), "Jaccard on MovieLens labels"),
        ("Year apart", spearman(yd, agree), "release dates"),
        ("Fame gap", spearman(fg, agree), "difference in Qloo popularity"),
    ]
    width = max(len(n) for n, _, _ in rows)
    print(f"\nPREDICTING RATING AGREEMENT, over {len(agree)} pairs\n")
    for name, r, how in rows:
        if r is None:
            print(f"  {name:<{width}}    n/a   {how}")
            continue
        print(f"  {name:<{width}}  {r:+.3f}  {'#' * round(abs(r) * 26)}")
        print(f"  {'':<{width}}          {how}")

    rho = rows[0][1]
    others = [(abs(r), n) for n, r, _ in rows[1:] if r is not None]
    best_other = max(others)[1] if others else None
    beat = all(abs(rho) > v for v, _ in others)

    print("\n" + "=" * 64)
    if beat:
        print("QLOO WINS. Cultural affinity predicts whether two films' viewers")
        print("agree better than genre, year or fame do. On a set where every")
        print("film carries the same genre tag, that is the whole argument.")
        return 0
    print(f"{best_other.upper()} MATCHES OR BEATS QLOO. Say so. The claim is that")
    print("cultural affinity sees something free metadata cannot, and on this")
    print("lineup it is not demonstrated.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
