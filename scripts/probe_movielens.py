#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod            # noqa: E402
from app.qloo import Qloo                       # noqa: E402
from app.resolve import Film, resolve_all       # noqa: E402

ML = Path("data/ml-32m")
MIN_RATERS = 30
MIN_PAIRS = 10


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
        print("  curl -O https://files.grouplens.org/datasets/movielens/ml-32m.zip")
        print("  unzip ml-32m.zip -d data/")
        return 2

    slug = sys.argv[1] if len(sys.argv) > 1 else "one-genre"
    path = Path("data/lineups") / f"{slug}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    wanted = {norm(f["title"]): f for f in data["films"]}
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
            genres[key] = {g for g in row.get("genres", "").split("|") if g
                           and g != "(no genres listed)"}
            made[key] = year

    found = sorted(titles)
    missing = [k for k in wanted if k not in titles]
    print(f"\n1. MATCHED  {len(found)}/{len(wanted)} films in MovieLens")
    for k in missing:
        print(f"      not found: {wanted[k]['title']}")
    if len(found) < 4:
        print("\nToo few matches. Nothing can be measured on this lineup.")
        return 1

    print("\n2. READING RATINGS  (about a minute)")
    by_user = defaultdict(dict)
    kept = 0
    with (ML / "ratings.csv").open(encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if row[0] == "userId":
                continue
            mid = int(row[1])
            if mid in ids:
                by_user[int(row[0])][ids[mid]] = float(row[2])
                kept += 1
    print(f"   {kept:,} ratings from {len(by_user):,} users touch this lineup")

    human, qloo_d, labels, thin = {}, {}, [], 0
    keys = found
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            xs, ys = [], []
            for seen in by_user.values():
                if a in seen and b in seen:
                    xs.append(seen[a])
                    ys.append(seen[b])
            if len(xs) < MIN_RATERS:
                thin += 1
                continue
            r = pearson(xs, ys)
            if r is None:
                continue
            human[(a, b)] = (r, len(xs))

    print(f"\n3. PAIRS    {len(human)} usable, {thin} below {MIN_RATERS} co-raters")
    if len(human) < MIN_PAIRS:
        print("   Too few. The correlation below would not mean anything.")
        return 1

    qloo = Qloo()
    films = [Film(title=f["title"], year=f["year"], director=f.get("director", ""),
                  aliases=f.get("aliases", [])) for f in data["films"]]
    resolved, _ = resolve_all(qloo, films, data.get("entity_type", "urn:entity:movie"))
    m = matrix_mod.build(qloo, resolved, data.get("entity_type", "urn:entity:movie"))
    back = {norm(t): t for t in m.films}

    xs, ys = [], []
    for (a, b), (r, n) in human.items():
        if a not in back or b not in back:
            continue
        xs.append(m.distance(back[a], back[b]))
        ys.append(r)
        labels.append((titles[a], titles[b], m.distance(back[a], back[b]), r, n))

    if len(xs) < MIN_PAIRS:
        print("   Too few pairs survive matching back to Qloo.")
        return 1

    rho = spearman(xs, ys)
    print(f"\n4. AGREEMENT")
    print(f"   Qloo distance vs MovieLens rating correlation, over {len(xs)} pairs")
    print(f"   rho = {rho:+.3f}")
    print("   (negative is the hypothesis: closer in Qloo -> people agree more)")

    print("\n5. BASELINES   what the same pairs predict from free metadata")
    gj, yd, pd_, agree = [], [], [], []
    pops = {}
    for t in m.films:
        pops[norm(t)] = m.popularity(t)
    for (a, b), (r, _n) in human.items():
        if a not in back or b not in back:
            continue
        ga, gb = genres.get(a, set()), genres.get(b, set())
        union = ga | gb
        gj.append(len(ga & gb) / len(union) if union else 0.0)
        yd.append(abs(made.get(a, 0) - made.get(b, 0)))
        pa, pb = pops.get(a), pops.get(b)
        pd_.append(abs(pa - pb) if pa is not None and pb is not None else 0.0)
        agree.append(r)

    tagged = [genres[k] for k in found if genres.get(k)]
    shared = set.intersection(*tagged) if len(tagged) == len(found) and tagged else set()
    if shared:
        print(f"   every film here is tagged {' and '.join(sorted(shared))}, so a")
        print("   genre label has almost nothing to separate them with")

    rows = [
        ("Qloo distance", rho, "cultural affinity"),
        ("Genre overlap", spearman(gj, agree), "Jaccard on MovieLens labels"),
        ("Year apart", spearman(yd, agree), "release dates"),
        ("Fame gap", spearman(pd_, agree), "difference in Qloo popularity"),
    ]
    width = max(len(n) for n, _, _ in rows)
    print()
    for name, r, how in rows:
        if r is None:
            print(f"   {name:<{width}}      n/a   {how}")
            continue
        print(f"   {name:<{width}}  {r:+.3f}   {'#' * round(abs(r) * 28)}")
        print(f"   {'':<{width}}           {how}")

    scored = [(abs(r), name) for name, r, _ in rows if r is not None]
    best = max(scored)[1]
    beat = all(abs(rho) > abs(r) for _n2, r, _h in rows[1:] if r is not None)
    print(f"\n   strongest predictor: {best}")

    labels.sort(key=lambda r: r[2])
    print("\n   closest by Qloo:")
    for a, b, d, r, n in labels[:4]:
        print(f"      d={d:5.2f}  r={r:+.2f}  n={n:>5}  {a[:28]} / {b[:28]}")
    print("   furthest by Qloo:")
    for a, b, d, r, n in labels[-4:]:
        print(f"      d={d:5.2f}  r={r:+.2f}  n={n:>5}  {a[:28]} / {b[:28]}")

    print("\n" + "=" * 64)
    if rho is None:
        print("No result.")
        return 1
    if rho <= -0.3 and beat:
        print("CORROBORATED, AND IT BEATS THE METADATA. Films Qloo places close")
        print("together are rated more alike by the people who saw both, in a")
        print("dataset Qloo had no part in — and genre, year and fame all predict")
        print("that agreement worse. Independent support for the taste signal,")
        print("not evidence about festival attendance, which nothing public")
        print("can show.")
        return 0
    if rho <= -0.3:
        print("CORROBORATED, BUT A BASELINE MATCHES IT. The signal tracks real")
        print(f"rating behaviour, yet {best} predicts the same agreement at least")
        print("as well. Say so plainly: the claim is that Qloo adds something a")
        print("genre tag cannot, and on this lineup that is not demonstrated.")
        return 0
    if rho <= -0.1:
        print("WEAK AGREEMENT. The sign is right but the effect is small. Report")
        print("the number rather than the conclusion.")
        return 0
    print("NOT CORROBORATED. Qloo's distances do not track how these people")
    print("rated. Either the sample is too thin or the signal does not survive")
    print("contact with rating behaviour. Do not put this on the page.")
    return 1


if __name__ == "__main__":
    sys.exit(main())