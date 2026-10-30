                      
from __future__ import annotations

import csv
import json
import math
import random
import re
import statistics as stats
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import matrix as matrix_mod                        
from app.build import _load_lineup                          
from app.qloo import Qloo                                   
from app.resolve import resolve_all                         
from app.structure import analyse                           

ML = Path("data/ml-32m")
LINEUPS = ["one-genre", "_probe-bridge", "berlinale2024", "cannes2023",
           "sundance2024"]
MIN_RATERS = 30
SHUFFLES = 10_000


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



def main() -> int:
    if not all((ML / name).exists() for name in ("movies.csv", "ratings.csv")):
        print(f"MovieLens requires movies.csv and ratings.csv in {ML}/")
        return 2

    want = {}
    for slug in LINEUPS:
        _name, _note, films, _et = _load_lineup(slug)
        for f in films:
            entry = want.setdefault(film_key(f), {"film": f, "lineups": set()})
            entry["lineups"].add(slug)

    with (ML / "movies.csv").open(encoding="utf-8", newline="") as fh:
        ids, titles, _made, _genres, audit = match_movies(want, csv.DictReader(fh))
    audit_path = Path("data/groups_matches.json")
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

    print(f"matched {len(titles)} of {len(want)} titles")

    print("reading ratings")
    raters: dict[tuple[str, int], set] = defaultdict(set)
    seen = set()
    with (ML / "ratings.csv").open(encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if row[0] == "userId":
                continue
            seen.add(row[0])
            mid = int(row[1])
            if mid in ids:
                raters[ids[mid]].add(row[0])
    total = len(seen)
    print(f"   {total:,} users in the dataset")

    def both_seen(a: tuple[str, int], b: tuple[str, int]):
        ua, ub = raters.get(a), raters.get(b)
        if not ua or not ub:
            return None
        if len(ua) < MIN_RATERS or len(ub) < MIN_RATERS:
            return None
        return ua, ub

    def phi(a: tuple[str, int], b: tuple[str, int]) -> float | None:
        pair = both_seen(a, b)
        if pair is None:
            return None
        ua, ub = pair
        na, nb, both = len(ua), len(ub), len(ua & ub)
        under = math.sqrt(na * nb * (total - na) * (total - nb))
        return ((total * both - na * nb) / under) if under else None

    def jaccard(a: tuple[str, int], b: tuple[str, int]) -> float | None:
        pair = both_seen(a, b)
        if pair is None:
            return None
        ua, ub = pair
        union = len(ua | ub)
        return len(ua & ub) / union if union else None

    print("\nasking Qloo and grouping each lineup")
    qloo = Qloo()
    per_lineup = []
    worlds = []

    for slug in LINEUPS:
        name, _n, films, entity_type = _load_lineup(slug)
        resolved, _missed = resolve_all(qloo, films, entity_type)
        m = matrix_mod.build(qloo, resolved, entity_type)
        a = analyse(m, stability=False)
        member = {t: i for i, c in enumerate(a.clusters) for t in c}

        keys = {t: film_key(m.resolved[t].film) for t in m.films}
        covered = [t for t in m.films
                   if len(raters.get(keys[t], ())) >= MIN_RATERS]
        values, jac = {}, {}
        for i, x in enumerate(covered):
            for y in covered[i + 1:]:
                v = phi(keys[x], keys[y])
                if v is None:
                    continue
                values[(x, y)] = v
                j = jaccard(keys[x], keys[y])
                if j is not None:
                    jac[(x, y)] = j

        here_in = [v for (x, y), v in values.items()
                   if member[x] == member[y]]
        here_out = [v for (x, y), v in values.items()
                    if member[x] != member[y]]
        short = name.split("\u2014")[0].strip()
        print(f"   {short[:24]:<26} {len(covered)}/{len(m.films)} covered, "
              f"{len(here_in)} same-group pairs, "
              f"{len(here_out)} different-group pairs")

        if not values or not here_in or not here_out:
            continue

        sizes = [sum(1 for t in c if t in set(covered)) for c in a.clusters]
        worlds.append({
            "name": short, "titles": covered, "values": values,
            "jaccard": jac, "real": dict(member),
            "sizes": [n for n in sizes if n],
        })
        per_lineup.append((short, len(covered), len(a.clusters),
                           stats.mean(here_in), stats.mean(here_out)))

    if not worlds:
        print("\nno lineup had enough MovieLens coverage to test")
        return 1

    def gap_from(labels_per_world, field: str = "values") -> float:
        a_in, a_out = [], []
        for world, labels in zip(worlds, labels_per_world):
            for (x, y), v in world[field].items():
                (a_in if labels[x] == labels[y] else a_out).append(v)
        if not a_in or not a_out:
            return float("-inf")
        return stats.mean(a_in) - stats.mean(a_out)

    real = [w["real"] for w in worlds]
    counts = {}
    for field in ("values", "jaccard"):
        a_in, a_out = [], []
        for world in worlds:
            for (x, y), v in world[field].items():
                lab = world["real"]
                (a_in if lab[x] == lab[y] else a_out).append(v)
        counts[field] = (len(a_in), len(a_out),
                         stats.mean(a_in) if a_in else 0.0,
                         stats.mean(a_out) if a_out else 0.0)

    true_gap = {f: gap_from(real, f) for f in ("values", "jaccard")}

    if per_lineup:
        print("\n   lineup by lineup, phi")
        for nm, cov, k, a_in, a_out in per_lineup:
            mark = "  " if a_in > a_out else " <-"
            print(f"      {nm[:24]:<26} {cov:>2} titles, {k} groups   "
                  f"same {a_in:.3f}   different {a_out:.3f}{mark}")

    rng = random.Random(20260125)
    better = {"values": 0, "jaccard": 0}
    for _ in range(SHUFFLES):
        drawn = []
        for world in worlds:
            shuffled = world["titles"][:]
            rng.shuffle(shuffled)
            labels, at = {}, 0
            for g, n in enumerate(world["sizes"]):
                for t in shuffled[at:at + n]:
                    labels[t] = g
                at += n
            for t in shuffled[at:]:
                labels[t] = len(world["sizes"]) - 1
            drawn.append(labels)
        for field in ("values", "jaccard"):
            if gap_from(drawn, field) >= true_gap[field]:
                better[field] += 1

    p = {f: (better[f] + 1) / (SHUFFLES + 1) for f in better}

    for field, label in (("values", "phi, the reported measure"),
                         ("jaccard", "Jaccard, the measure first tried")):
        n_in, n_out, m_in, m_out = counts[field]
        print(f"\n   {label}")
        print(f"      {n_in} pairs inside a group, {n_out} across groups")
        print(f"      inside   {m_in:+.4f}")
        print(f"      across   {m_out:+.4f}")
        print(f"      gap      {true_gap[field]:+.4f}")
        print(f"      {better[field]} of {SHUFFLES:,} permutations reached "
              f"it (p = {p[field]:.5f})")

    vpath = Path("data/validation.json")
    if vpath.exists():
        v = json.loads(vpath.read_text(encoding="utf-8"))
        v["groups"] = {
            "match_policy": "unique normalised title plus exact year",
            "match_audit": str(audit_path),
            "seed": 20260125,
            "min_raters": MIN_RATERS,
            "inside_pairs": counts["values"][0],
            "between_pairs": counts["values"][1],
            "inside_mean": round(counts["values"][2], 5),
            "between_mean": round(counts["values"][3], 5),
            "gap": round(true_gap["values"], 5),
            "p": round(p["values"], 5),
            "reached": better["values"],
            "shuffles": SHUFFLES,
            "permuted": "titles within each lineup, group sizes preserved",
            "jaccard_gap": round(true_gap["jaccard"], 5),
            "jaccard_p": round(p["jaccard"], 5),
            "lineups": [{"name": nm, "titles": cov, "groups": k,
                         "inside": round(a_in, 5), "between": round(a_out, 5)}
                        for nm, cov, k, a_in, a_out in per_lineup],
        }
        vpath.write_text(json.dumps(v, indent=2, ensure_ascii=False),
                         encoding="utf-8")
        print(f"\n   wrote the group figures into {vpath}")

    g = true_gap["values"]
    print("\n" + "=" * 68)
    if g > 0 and p["values"] < 0.01:
        print("THE GROUPS HOLD on these lineups. Two titles Slate puts in the")
        print("same group share more audience than two it separates, and")
        print("randomly reassigning titles to groups of the same sizes almost")
        print("never does as well.")
    elif g > 0 and p["values"] < 0.05:
        print("THE GROUPS HOLD, WEAKLY. The gap points the right way and")
        print("would be uncommon by chance, but it is not decisive.")
    elif g > 0:
        print("INCONCLUSIVE. The gap points the right way but chance produces")
        print("it often enough that it proves nothing.")
    else:
        print("NOT SUPPORTED. Titles in the same group share no more audience")
        print("than titles Slate separates.")
    print()
    print("Read it as a demonstration, not a general finding. The lineups")
    print("were picked because MovieLens covers them, and the measure was")
    print("changed after seeing the first one's results.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
