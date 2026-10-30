                      
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod                        
from app.qloo import Qloo                                   
from app.resolve import Film, resolve_all                   

ML = Path("data/ml-32m")
MIN_RATERS = 30
MIN_PAIRS = 10


def norm(title: str) -> str:
                                                                      
    t = re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip().casefold()
                                                                 
    article = re.fullmatch(r"(.+),\s*(the|a|an|la|le|les|el|il|der|die|das)", t)
    if article:
        t = f"{article.group(2)} {article.group(1)}"
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def film_key(film):
                                                                   
    return norm(film.title), int(film.year or 0)


def match_movies(want, movie_rows):
                                                                           

                                                                              
                                                                                
       
    catalog = defaultdict(dict)
    for row in movie_rows:
        catalog[norm(row["title"])][int(row["movieId"])] = row

    ids, titles, made, genres, audit = {}, {}, {}, {}, []
    for key, entry in sorted(want.items()):
        title_key, asked = key
        candidates = []
        for mid, row in sorted(catalog.get(title_key, {}).items()):
            ym = re.search(r"\((\d{4})\)\s*$", row["title"])
            year = int(ym.group(1)) if ym else 0
            if asked and year == asked:
                candidates.append((mid, row, year))
        status = ("matched" if len(candidates) == 1 else
                  "ambiguous" if candidates else "unmatched")
        record = {
            "requested_title": entry["film"].title,
            "requested_year": asked,
            "lineups": sorted(entry["lineups"]),
            "status": status,
            "candidates": [{"movie_id": mid, "title": row["title"], "year": year}
                           for mid, row, year in candidates],
            "accepted_movie_ids": [],
        }
        if status == "matched":
            mid, row, year = candidates[0]
            if mid in ids and ids[mid] != key:
                raise ValueError(f"MovieLens ID {mid} matched two requested films")
            ids[mid] = key
            titles[key] = row["title"]
            made[key] = year
            genres[key] = {g for g in row.get("genres", "").split("|")
                           if g and g != "(no genres listed)"}
            record["accepted_movie_ids"] = [mid]
        audit.append(record)
    return ids, titles, made, genres, audit



def spearman(xs, ys):
    if len(xs) < 3:
        return None
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
    if not all((ML / name).exists() for name in ("movies.csv", "ratings.csv")):
        print(f"MovieLens requires movies.csv and ratings.csv in {ML}/")
        print("  curl -O https://files.grouplens.org/datasets/movielens/ml-32m.zip")
        print("  unzip ml-32m.zip -d data/")
        return 2

    slug = sys.argv[1] if len(sys.argv) > 1 else "one-genre"
    path = Path("data/lineups") / f"{slug}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    films = [Film(title=f["title"], year=f.get("year", 0),
                  director=f.get("director", ""), aliases=f.get("aliases", []))
             for f in data["films"]]
    wanted = {film_key(f): {"film": f, "lineups": {slug}} for f in films}

    print(f"{data.get('name', slug)}")
    print("=" * 64)
    with (ML / "movies.csv").open(encoding="utf-8", newline="") as fh:
        ids, titles, made, genres, audit = match_movies(wanted, csv.DictReader(fh))
    audit_path = Path("data") / f"movielens_matches_{slug}.json"
    audit_path.write_text(json.dumps({
        "policy": "unique normalised title plus exact year; no fuzzy fallback",
        "matches": audit,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"MovieLens match audit: {audit_path}")
    for record in audit:
        accepted = record["accepted_movie_ids"]
        matched = record["candidates"][0]["title"] if accepted else record["status"]
        print(f"   {record['requested_title']} ({record['requested_year']})"
              f" -> {matched}; accepted IDs: {accepted}")

    found = sorted(titles)
    missing = [k for k in wanted if k not in titles]
    print(f"\n1. MATCHED  {len(found)}/{len(wanted)} films in MovieLens")
    for k in missing:
        print(f"      not found: {wanted[k]['film'].title} ({wanted[k]['film'].year})")
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

    human, labels, thin = {}, [], 0
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
    resolved, _ = resolve_all(qloo, films, data.get("entity_type", "urn:entity:movie"))
    m = matrix_mod.build(qloo, resolved, data.get("entity_type", "urn:entity:movie"))
    back = {film_key(m.resolved[t].film): t for t in m.films}

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
    if rho is None:
        print("   No correlation: one of the pair-level series is constant.")
        return 1
    print(f"   rho = {rho:+.3f}")
    print("   (negative is the hypothesis: closer in Qloo -> people agree more)")

    print("\n5. BASELINES   correlations on the same evaluated pairs")
    gj, yd, pd_, agree = [], [], [], []
    pops = {}
    for t in m.films:
        pops[film_key(m.resolved[t].film)] = m.popularity(t)
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
        print(f"   every matched film shares the {' and '.join(sorted(shared))} tag")
        print("   the genre baseline still uses each film's complete genre set")

    rows = [
        ("Slate distance", rho, "cultural affinity"),
        ("Shared genres", spearman(gj, agree), "Jaccard on MovieLens labels"),
        ("Years apart", spearman(yd, agree), "release dates"),
        ("Popularity gap", spearman(pd_, agree),
         "difference in Qloo popularity"),
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
    print(f"\n   largest absolute correlation in this sample: {best}")

    labels.sort(key=lambda r: r[2])
    print("\n   closest by Qloo:")
    for a, b, d, r, n in labels[:4]:
        print(f"      d={d:5.2f}  r={r:+.2f}  n={n:>5}  {a[:28]} / {b[:28]}")
    print("   furthest by Qloo:")
    for a, b, d, r, n in labels[-4:]:
        print(f"      d={d:5.2f}  r={r:+.2f}  n={n:>5}  {a[:28]} / {b[:28]}")

                                                                        
                                                                          
    report = {
        "lineup": slug, "lineup_name": data.get("name", slug),
        "rho": rho, "pairs": len(xs), "ratings": kept, "users": len(by_user),
        "matched": len(found), "of": len(wanted),
        "unmatched": [wanted[k]["film"].title for k in missing],
        "match_policy": "unique normalised title plus exact year",
        "match_audit": str(audit_path),
        "min_co_raters": MIN_RATERS,
        "baselines": [{"name": name, "rho": r, "measure": how}
                      for name, r, how in rows],
        "agreement_pairs": [
            {"a": a, "b": b, "distance": d, "agreement": r, "n": n}
            for a, b, d, r, n in labels],
        "limit": "Exploratory pairwise rating-correlation check on one lineup; "
                 "not a test of attendance or audience-guided selection.",
    }
    out = Path("data") / f"movielens_agreement_{slug}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    vpath = Path("data/validation.json")
    if slug == "one-genre" and vpath.exists():
        v = json.loads(vpath.read_text(encoding="utf-8"))
        mv = v.setdefault("movielens", {})
        mv.update(report)
                                                                            
        mv.pop("headline", None)
        mv.pop("baseline_verdict", None)
        mv["reproduce"] = "python3 scripts/probe_movielens.py"
        mv["baseline_reproduce"] = mv["reproduce"]
        vpath.write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"updated rating-agreement fields in {vpath}; overlap and groups preserved")

    print("\n" + "=" * 64)
    print("This compares Qloo distance with Pearson rating correlations among")
    print("co-raters, using Spearman correlation across film pairs.")
    print("Negative rho means closer pairs tend to have more correlated ratings.")
    if beat:
        print("Slate has the largest absolute correlation among these baselines")
        print("on this sample; this is not a significance test of their differences.")
    else:
        print(f"At least one baseline matches or exceeds Slate: {best}.")
    print("Treat this as an exploratory result on this lineup, not a general")
    print("finding or an attendance forecast. Report unfavourable results too.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
