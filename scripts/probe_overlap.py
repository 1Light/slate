                      
from __future__ import annotations

import csv
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod                        
from app.build import _load_lineup                          
from app.qloo import Qloo                                   
from app.resolve import resolve_all                         

ML = Path("data/ml-32m")
LINEUPS = ["one-genre", "berlinale2024", "cannes2023", "sundance2024"]
MIN_RATERS = 30


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


def pair_metrics(ua, ub, total):
    na, nb = len(ua), len(ub)
    both = len(ua & ub)
    union = na + nb - both
    expect = na * nb / total if total else 0.0
    under = math.sqrt(na * nb * (total - na) * (total - nb))
    return {
        "n_a": na, "n_b": nb, "both": both,
        "jaccard": both / union if union else 0.0,
        "lift": both / expect if expect else 0.0,
        "phi": (total * both - na * nb) / under if under else 0.0,
        "fame": min(na, nb), "gap": abs(na - nb),
    }


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
    if not all((ML / name).exists() for name in ("movies.csv", "ratings.csv")):
        print(f"MovieLens requires movies.csv and ratings.csv in {ML}/")
        return 2

    want = {}
    for slug in LINEUPS:
        _name, _note, films, _entity_type = _load_lineup(slug)
        for f in films:
            entry = want.setdefault(film_key(f), {"film": f, "lineups": set()})
            entry["lineups"].add(slug)

    with (ML / "movies.csv").open(encoding="utf-8", newline="") as fh:
        ids, titles, made, genres, audit = match_movies(want, csv.DictReader(fh))
    audit_path = Path("data/overlap_matches.json")
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
    distance, pops = {}, {}
    for slug in LINEUPS:
        _name, _n, films, entity_type = _load_lineup(slug)
        resolved, _missed = resolve_all(qloo, films, entity_type)
        m = matrix_mod.build(qloo, resolved, entity_type)
        keys = {t: film_key(m.resolved[t].film) for t in m.films}
        for t in m.films:
            pops[keys[t]] = m.popularity(t)
        for i, a in enumerate(m.films):
            for b in m.films[i + 1:]:
                ka, kb = keys[a], keys[b]
                if ka in raters and kb in raters:
                                                                       
                    ka, kb = sorted((ka, kb))
                    distance[(slug, ka, kb)] = m.distance(a, b)

    rows = []
    for (slug, a, b), d in sorted(distance.items()):
        metrics = pair_metrics(raters[a], raters[b], total)
        if (metrics["n_a"] < MIN_RATERS or metrics["n_b"] < MIN_RATERS
                or metrics["both"] < 5):
            continue
        rows.append({"lineup": slug, "pair": (a, b), "d": d, **metrics})

    if len(rows) < 20:
        print(f"only {len(rows)} usable pairs, not enough")
        return 1

    print(f"\n{len(rows)} pairs with at least {MIN_RATERS} raters each\n")
    ds = [r["d"] for r in rows]

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

    print("\n  the same three against the smaller title's rater count:")
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
                "n": r["both"], "n_a": r["n_a"], "n_b": r["n_b"],
                "movie_id_a": next(mid for mid, key in ids.items() if key == a),
                "movie_id_b": next(mid for mid, key in ids.items() if key == b),
                "lineup": r["lineup"]}

    vpath = Path("data/validation.json")
    if vpath.exists():
        v = json.loads(vpath.read_text(encoding="utf-8"))
        m = v.setdefault("movielens", {})
        m["overlap_rho"] = spearman(ds, [r["phi"] for r in rows])
        m["overlap_jaccard_rho"] = spearman(ds, [r["jaccard"] for r in rows])
        m["overlap_popularity_rho"] = spearman(fame, [r["phi"] for r in rows])
        m["overlap_pairs"] = len(rows)
        m["overlap_match_policy"] = "unique normalised title plus exact year"
        m["overlap_popularity_measure"] = "smaller title's MovieLens rater count"
        m["overlap_pairs_by_lineup"] = {
            slug: sum(r["lineup"] == slug for r in rows) for slug in LINEUPS}
        m["overlap_matched_films"] = len(titles)
        m["overlap_evaluated_films"] = len({k for r in rows for k in r["pair"]})
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
        "evaluated_films": len({k for r in rows for k in r["pair"]}),
        "pairs_by_lineup": {slug: sum(r["lineup"] == slug for r in rows)
                            for slug in LINEUPS},
        "rater_count_baseline": "smaller title's MovieLens rater count",
        "all_pairs": [row(r) for r in by_distance],
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
