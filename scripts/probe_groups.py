#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import random
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
LINEUPS = ["one-genre", "bridge-probe", "berlinale2024", "cannes2023",
           "sundance2024"]
MIN_RATERS = 30
SHUFFLES = 10_000


def norm(title: str) -> str:
    t = re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip().lower()
    t = re.sub(r"^(the|a|an)\s+", "", t)
    t = re.sub(r",\s*(the|a|an)$", "", t)
    return re.sub(r"[^a-z0-9]+", "", t)


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

    print("reading ratings")
    raters: dict[str, set] = defaultdict(set)
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

    def phi(a: str, b: str) -> float | None:
        ua, ub = raters.get(a), raters.get(b)
        if not ua or not ub:
            return None
        na, nb = len(ua), len(ub)
        if na < MIN_RATERS or nb < MIN_RATERS:
            return None
        both = len(ua & ub)
        under = math.sqrt(na * nb * (total - na) * (total - nb))
        return ((total * both - na * nb) / under) if under else None

    print("\nasking Qloo and grouping each lineup")
    qloo = Qloo()
    inside, between, per_lineup = [], [], []

    for slug in LINEUPS:
        name, _n, films, entity_type = _load_lineup(slug)
        resolved, _missed = resolve_all(qloo, films, entity_type)
        m = matrix_mod.build(qloo, resolved, entity_type)
        a = analyse(m, stability=False)
        member = {t: i for i, c in enumerate(a.clusters) for t in c}

        here_in, here_out = [], []
        covered = [t for t in m.films
                   if len(raters.get(norm(t), ())) >= MIN_RATERS]
        for i, x in enumerate(covered):
            for y in covered[i + 1:]:
                v = phi(norm(x), norm(y))
                if v is None:
                    continue
                (here_in if member[x] == member[y] else here_out).append(v)

        if len(here_in) >= 2 and len(here_out) >= 2:
            per_lineup.append((name.split("\u2014")[0].strip(),
                               len(covered), len(a.clusters),
                               stats.mean(here_in), stats.mean(here_out)))
        inside.extend(here_in)
        between.extend(here_out)
        print(f"   {name.split(chr(8212))[0].strip()[:24]:<26} "
              f"{len(covered)}/{len(m.films)} covered, "
              f"{len(here_in)} same-group pairs, "
              f"{len(here_out)} different-group pairs")

    if len(inside) < 5 or len(between) < 5:
        print(f"\nnot enough pairs: {len(inside)} inside, "
              f"{len(between)} between")
        return 1

    mi, mb = stats.mean(inside), stats.mean(between)
    gap = mi - mb

    if per_lineup:
        print("\n   lineup by lineup")
        for nm, cov, k, a_in, a_out in per_lineup:
            mark = "  " if a_in > a_out else " <-"
            print(f"      {nm[:24]:<26} {cov:>2} titles, {k} groups   "
                  f"same {a_in:.3f}   different {a_out:.3f}{mark}")

    pooled = inside + between
    n_in = len(inside)
    rng = random.Random(20260125)
    better = 0
    for _ in range(SHUFFLES):
        rng.shuffle(pooled)
        if stats.mean(pooled[:n_in]) - stats.mean(pooled[n_in:]) >= gap:
            better += 1
    p = (better + 1) / (SHUFFLES + 1)

    print(f"\n   {len(inside)} pairs inside a group, "
          f"{len(between)} pairs across groups")
    print(f"   mean shared audience inside   {mi:+.4f}")
    print(f"   mean shared audience across   {mb:+.4f}")
    print(f"   gap                           {gap:+.4f}")
    print(f"   chance alone does this well in {better} of {SHUFFLES:,} "
          f"shuffles (p = {p:.4f})")

    vpath = Path("data/validation.json")
    if vpath.exists():
        v = json.loads(vpath.read_text(encoding="utf-8"))
        v["groups"] = {
            "inside_pairs": len(inside), "between_pairs": len(between),
            "inside_mean": round(mi, 5), "between_mean": round(mb, 5),
            "gap": round(gap, 5), "p": round(p, 5), "shuffles": SHUFFLES,
            "lineups": [{"name": nm, "titles": cov, "groups": k,
                         "inside": round(a_in, 5), "between": round(a_out, 5)}
                        for nm, cov, k, a_in, a_out in per_lineup],
        }
        vpath.write_text(json.dumps(v, indent=2, ensure_ascii=False),
                         encoding="utf-8")
        print(f"\n   wrote the group figures into {vpath}")

    print("\n" + "=" * 64)
    if gap > 0 and p < 0.01:
        print("THE GROUPS HOLD. Two titles Slate puts in the same group share")
        print("more audience than two it separates, and chance alone almost")
        print("never produces a gap this size. The groups describe real")
        print("viewing, not only Qloo's rankings.")
    elif gap > 0 and p < 0.05:
        print("THE GROUPS HOLD, WEAKLY. The gap points the right way and")
        print("would be uncommon by chance, but it is not decisive. Say so")
        print("plainly rather than claiming more.")
    elif gap > 0:
        print("INCONCLUSIVE. The gap points the right way but chance produces")
        print("it often enough that it proves nothing. The page should claim")
        print("the distance result and not the group result.")
    else:
        print("NOT SUPPORTED. Titles in the same group share no more audience")
        print("than titles Slate separates. The heading should ask about")
        print("distance, which is what the pair test actually shows.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
