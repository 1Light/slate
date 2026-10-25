from __future__ import annotations

import json
from pathlib import Path

from app import matrix as matrix_mod
from app.agent import improve, to_dict
from app.qloo import Qloo, QlooError
from app.resolve import Film, resolve_all
from app.structure import analyse

ROOT = Path(__file__).resolve().parent.parent
LINEUPS = ROOT / "data" / "lineups"
MIN_FILMS = 4


class Refused(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _films_from_lines(lines: list[str]) -> list[Film]:
    films = []
    for raw in lines:
        title = raw.strip()
        if not title:
            continue
        year = 0
        if title.endswith(")") and "(" in title:
            head, _, tail = title.rpartition("(")
            digits = tail.rstrip(")").strip()
            if digits.isdigit() and len(digits) == 4:
                title, year = head.strip(), int(digits)
        films.append(Film(title=title, year=year))
    return films

def _load_lineup(slug: str):
    path = LINEUPS / f"{slug}.json"
    if not path.exists() or path.parent != LINEUPS:
        raise Refused(404, "No such programme.")
    data = json.loads(path.read_text(encoding="utf-8"))
    films = [
        Film(title=f["title"], year=f["year"],
             director=f.get("director", ""), origin=f.get("origin", ""),
             aliases=f.get("aliases", []))
        for f in data["films"]
    ]
    return (data.get("name", slug), data.get("note", ""), films,
            data.get("entity_type", "urn:entity:movie"))

def _shape(name, note, resolved, m, a, source, unresolved):
    cluster_of = a.member
    bridge_titles = {b["film"] for b in a.bridges}
    connects = {b["film"]: b["connects"] for b in a.bridges}
    isolated_of = {i["film"]: i for i in a.isolated}

    films = []
    for title in m.films:
        r = resolved[title]
        films.append({
            "title": title,
            "qloo_name": r.qloo_name,
            "year": r.qloo_year,
            "director": r.film.director,
            "origin": r.film.origin,
            "popularity": r.popularity,
            "cluster": cluster_of[title],
            "distance": round(a.centrality[title], 2),
            "isolation": round(a.isolation.get(title, 1.0), 2),
            "role": ("bridge" if title in bridge_titles
                     else "alone" if title in isolated_of else "interior"),
            "connects": connects.get(title),
            "alone_kind": isolated_of.get(title, {}).get("kind"),
            "coverage": round(a.completeness["per_film"].get(title, 1.0), 2),
        })

    return {
        "name": name,
        "note": note,
        "source": source,
        "headline": {**a.headline,
                     "origins": len({r.film.origin for r in resolved.values()
                                     if r.film.origin})},
        "films": films,
        "clusters": [{"index": i, "films": g} for i, g in enumerate(a.clusters)],
        "bridges": [{**b, "betweenness": round(b["betweenness"], 3),
                     "cluster": cluster_of[b["film"]]} for b in a.bridges],
        "tightest": [{"a": x, "b": y, "distance": round(d, 2), "cluster": c}
                     for x, y, d, c in a.tightest_pairs],
        "excluded": m.ghosts,
        "completeness": round(a.completeness["fraction"], 3),
        "isolated": a.isolated,
        "cut": {k: v for k, v in a.cut_check.items() if k != "scored"},
        "stability": a.stability,
        "popularity_confound": (None if a.popularity_confound is None
                                else round(a.popularity_confound, 2)),
        "unresolved": unresolved,
    }

ENTITY_LABEL = {
    "urn:entity:movie": "films",
    "urn:entity:artist": "musical artists",
    "urn:entity:book": "books",
    "urn:entity:tv_show": "TV shows",
    "urn:entity:podcast": "podcasts",
}

ENTITY_NOUN = {
    "urn:entity:movie": ("film", "films"),
    "urn:entity:artist": ("act", "acts"),
    "urn:entity:book": ("book", "books"),
    "urn:entity:tv_show": ("show", "shows"),
    "urn:entity:podcast": ("podcast", "podcasts"),
}

ENTITY_VIEW = {
    "urn:entity:artist": "Music",
    "urn:entity:book": "Books",
    "urn:entity:podcast": "Podcasts",
    "urn:entity:tv_show": "TV shows",
}
VIEW_ORDER = ["urn:entity:artist", "urn:entity:book",
              "urn:entity:podcast", "urn:entity:tv_show"]

OTHER_TYPES = ("urn:entity:artist", "urn:entity:book",
               "urn:entity:tv_show", "urn:entity:podcast")

def _read_as(qloo, films, entity_type):
    best = (entity_type, *resolve_all(qloo, films, entity_type))
    if len(best[1]) == len(films):
        return best
    for other in OTHER_TYPES:
        if other == entity_type:
            continue
        got = resolve_all(qloo, films, other)
        if len(got[0]) > len(best[1]):
            best = (other, *got)
        if len(best[1]) == len(films):
            break
    return best

def _pipeline(name, note, films, entity_type, source):
    qloo = Qloo()
    if source == "custom":
        entity_type, resolved, failed = _read_as(qloo, films, entity_type)
    else:
        resolved, failed = resolve_all(qloo, films, entity_type)
    if len(resolved) < MIN_FILMS:
        raise Refused(422, "Too few titles were found in Qloo to read a shape.")
    m = matrix_mod.build(qloo, resolved, entity_type)
    if len(m.films) < MIN_FILMS:
        raise Refused(422, "Too few titles have affinity data to compare.")
    a = analyse(m)
    shape = _shape(name, note, resolved, m, a, source, failed)
    shape["entity_type"] = entity_type
    shape["reading"] = ENTITY_LABEL.get(entity_type, "entities")
    one, many = ENTITY_NOUN.get(entity_type, ("item", "items"))
    shape["weak"] = bool((a.cut_check or {}).get("weak"))
    shape["noun"] = one
    shape["nouns"] = many
    return qloo, resolved, m, a, shape

def _compare_row(slug: str, shape: dict) -> dict:
    h = shape["headline"]
    return {
        "slug": slug,
        "name": shape["name"],
        "films": h["films"],
        "origins": h.get("origins", 0),
        "clusters": h["clusters"],
        "bridges": h["bridges"],
        "largest": h["largest_cluster"],
        "sizes": [len(c["films"]) for c in shape["clusters"]],
        "bridge_film": shape["bridges"][0]["film"] if shape["bridges"] else None,
        "bridge_popularity": (shape["bridges"][0]["popularity"]
                              if shape["bridges"] else None),
    }

def _lineup_ari() -> list:
    rows = []
    for path in sorted(LINEUPS.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        try:
            name, note, films, entity_type = _load_lineup(path.stem)
            resolved, _ = resolve_all(Qloo(), films, entity_type)
            m = matrix_mod.build(Qloo(), resolved, entity_type)
            a = analyse(m)
        except Exception:
            continue
        if a.stability and a.stability.get("ari") is not None:
            rows.append({"name": name.split("\u2014")[0].strip(),
                         "ari": a.stability["ari"]})
    rows.sort(key=lambda r: -r["ari"])
    return rows


def _bridge_check() -> dict:
    from .structure import KNN_VALUES, _betweenness, _knn

    rows, pooled = [], []
    for path in sorted(LINEUPS.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        try:
            name, note, films, entity_type = _load_lineup(path.stem)
            resolved, _ = resolve_all(Qloo(), films, entity_type)
            m = matrix_mod.build(Qloo(), resolved, entity_type)
            a = analyse(m, stability=False)
        except Exception:                                   # noqa: BLE001
            continue

        names = m.films
        bc = {f: 0.0 for f in names}
        for k in KNN_VALUES:
            s = _betweenness(names, _knn(m, k))
            for f in names:
                bc[f] += s[f] / len(KNN_VALUES)

        pops = {f: m.popularity(f) for f in names}
        have = [f for f in names if pops[f] is not None]
        if len(have) < 4:
            continue
        r = _spearman([bc[f] for f in have], [pops[f] for f in have])
        top = max(names, key=lambda f: bc[f])
        reported = {b["film"] for b in a.bridges}
        rows.append({
            "lineup": name.split("—")[0].strip(),
            "rho": None if r is None else round(r, 2),
            "top_by_betweenness": top,
            "top_popularity": None if pops[top] is None else round(pops[top], 3),
            "top_was_reported": top in reported,
            "bridges": sorted(reported),
        })
        pooled.extend((bc[f], pops[f]) for f in have)

    overall = _spearman([b for b, _ in pooled], [p for _, p in pooled]) if pooled else None
    caught = [r for r in rows if not r["top_was_reported"] and r["bridges"]]
    return {
        "rows": rows,
        "films": len(pooled),
        "pooled_rho": None if overall is None else round(overall, 2),
        "caught": caught[0] if caught else None,
        "reproduce": "python3 scripts/probe_bridge.py",
    }


def _spearman(xs, ys):
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


def _match_groups(before: list[list[str]], after: list[list[str]]) -> dict:
    moved = []
    where_before = {t: i for i, g in enumerate(before) for t in g}
    where_after = {t: i for i, g in enumerate(after) for t in g}
    for title, i in where_before.items():
        if title not in where_after:
            continue
        kin_before = {t for t in before[i] if t != title and t in where_after}
        kin_after = {t for t in after[where_after[title]] if t != title}
        if kin_before != kin_after:
            moved.append(title)
    return {"moved": moved}


def _diff(base: dict, now: dict) -> dict:
    was = [c["films"] for c in base["clusters"]]
    is_ = [c["films"] for c in now["clusters"]]
    moved = _match_groups(was, is_)["moved"]

    bridges_was = [b["film"] for b in base.get("bridges", [])]
    bridges_now = [b["film"] for b in now.get("bridges", [])]
    gone = [b for b in bridges_was if b not in bridges_now]
    fresh = [b for b in bridges_now if b not in bridges_was]

    parts = []
    if len(is_) != len(was):
        parts.append(f"{len(was)} group{'' if len(was) == 1 else 's'}, "
                     f"now {len(is_)}.")
    else:
        parts.append(f"{len(is_)} group{'' if len(is_) == 1 else 's'}.")

    n = len(moved)
    if n:
        parts.append(f"{n} film{'' if n == 1 else 's'} moved.")

    if gone and not fresh:
        parts.append("The bridge is gone." if len(gone) == 1
                     else "The bridges are gone.")
    elif fresh and not gone:
        parts.append(f"{fresh[0]} now connects groups that had none."
                     if len(fresh) == 1 else "New bridges appeared.")
    elif fresh and gone:
        parts.append(f"{gone[0]} no longer connects the groups; "
                     f"{fresh[0]} does.")

    return {
        "line": " ".join(parts),
        "moved": moved,
        "groups_before": len(was),
        "groups_after": len(is_),
        "bridges_lost": gone,
        "bridges_gained": fresh,
    }


def _reaches(clusters) -> tuple:
    sizes = sorted((len(c) for c in clusters), reverse=True)
    return (len(clusters), -sizes[0] if sizes else 0)


def _best_subset(qloo, films, entity_type, keep: int, source: str):
    from itertools import combinations
    titles = [f.title for f in films]
    if keep >= len(titles):
        return titles
    budget = 60
    tries = list(combinations(titles, keep))
    if len(tries) > budget:
        tries = None

    def shape_of(chosen):
        picked = [f for f in films if f.title in set(chosen)]
        try:
            resolved, _ = resolve_all(qloo, picked, entity_type)
            m = matrix_mod.build(qloo, resolved, entity_type)
            a = analyse(m, stability=False)
        except Exception:
            return None
        return _reaches(a.clusters)

    if tries is not None:
        best, score = None, None
        for combo in tries:
            s = shape_of(combo)
            if s and (score is None or s > score):
                best, score = list(combo), s
        return best or titles[:keep]

    chosen = list(titles)
    while len(chosen) > keep:
        drop, score = None, None
        for t in chosen:
            s = shape_of([x for x in chosen if x != t])
            if s and (score is None or s > score):
                drop, score = t, s
        if drop is None:
            break
        chosen.remove(drop)
    return chosen


def _subset(m, keep: list[str]):
    from app.structure import _rerank
    keep = [t for t in m.films if t in set(keep)]
    return matrix_mod.Matrix(films=keep, ranks=_rerank(m.ranks, keep),
                             resolved=m.resolved)


def _shape_from(name, note, m, source, unresolved, entity_type,
                stability=True):
    a = analyse(m, stability=stability)
    resolved = {t: m.resolved[t] for t in m.films if t in m.resolved}
    shape = _shape(name, note, resolved, m, a, source, unresolved)
    one, many = ENTITY_NOUN.get(entity_type, ("item", "items"))
    shape["entity_type"] = entity_type
    shape["reading"] = ENTITY_LABEL.get(entity_type, "items")
    shape["noun"], shape["nouns"] = one, many
    return shape, a


def _best_subset_fast(m, keep: int):
    from itertools import combinations
    titles = sorted(m.films)
    if keep >= len(titles):
        return titles

    if _choose(len(titles), keep) <= ENUMERATE_UP_TO:
        return list(max(combinations(titles, keep),
                        key=lambda c: _profile(m, list(c))))

    chosen = list(titles)
    while len(chosen) > keep:
        chosen = list(max(
            (tuple(x for x in chosen if x != t) for t in chosen),
            key=lambda c: _profile(m, list(c))))
    return chosen


def _profile(m, titles):
    t = list(titles)
    return tuple(sorted(m.distance(a, b)
                        for i, a in enumerate(t) for b in t[i + 1:]))


def _mean_distance(m, titles):
    p = _profile(m, titles)
    return sum(p) / len(p) if p else 0.0


ENUMERATE_UP_TO = 200_000


def _choose(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    out = 1
    for i in range(min(k, n - k)):
        out = out * (n - i) // (i + 1)
    return out


def _against_chance(m, chosen, pool, rounds=400):
    from itertools import combinations
    import random

    pool = sorted(set(pool))
    chosen = list(chosen)
    k = len(chosen)
    if k < 2 or len(pool) <= k:
        return None

    here = _profile(m, chosen)
    whole = _choose(len(pool), k)

    if whole <= ENUMERATE_UP_TO:
        drawn = [_profile(m, list(c)) for c in combinations(pool, k)]
        how = "exact"
    else:
        seed = random.Random(20260101)
        drawn = [_profile(m, seed.sample(pool, k)) for _ in range(rounds)]
        how = "sampled"

    below = sum(1 for p in drawn if p < here)
    same = sum(1 for p in drawn if p == here)
    return {
        "closest": round(here[0], 6),
        "beats": below,
        "ties": same,
        "counted": len(drawn),
        "possible": whole,
        "how": how,
        "mean": round(sum(here) / len(here), 6),
    }


def _contribution(m, lineup, candidate):
    others = [t for t in lineup if t != candidate]
    if not others:
        return None
    gaps = sorted(((m.distance(candidate, t), t) for t in others),
                  key=lambda p: (round(p[0], 12), p[1]))
    return {
        "film": candidate,
        "distances": [{"film": t, "distance": round(d, 6)} for d, t in gaps],
        "nearest": [{"film": t, "distance": round(d, 6)} for d, t in gaps[:3]],
        "furthest": [{"film": t, "distance": round(d, 6)}
                     for d, t in reversed(gaps[-3:])],
        "closest_with_it": round(_touching(m, others, [candidate])[0], 6),
        "closest_without": round(_profile(m, others)[0], 6),
    }


def _fit_brief(m, lineup, candidate, pool=None, slots=None):
    was = analyse(_subset(m, lineup), stability=False)
    now = analyse(_subset(m, lineup + [candidate]), stability=False)

    here = _contribution(m, lineup, candidate)
    if here is None:
        raise Refused(422, "The lineup needs at least one other title.")

    rivals = []
    for other in (pool or []):
        if other == candidate or other in set(lineup):
            continue
        got = _contribution(m, lineup, other)
        if got:
            rivals.append(got)
    ranked = sorted(rivals + [here],
                    key=lambda r: (-r["closest_with_it"], r["film"]))
    rank = next((i + 1 for i, r in enumerate(ranked)
                 if r["film"] == candidate), None)

    where = next((i for i, c in enumerate(now.clusters) if candidate in c),
                 None)
    role, connects = "interior", None
    for b in now.bridges:
        if b["film"] == candidate:
            role, connects = "bridge", b["connects"]
            break
    else:
        if any(i["film"] == candidate for i in now.isolated):
            role = "alone"

    spare = None
    for a, b, d, g in now.tightest_pairs:
        if candidate in (a, b):
            continue
        spare = {"films": [a, b], "distance": round(d, 6), "group": g}
        break

    full = lineup + [candidate]
    return {
        "candidate": here,
        "lands_in": where,
        "role": role,
        "connects": connects,
        "groups_before": len(was.clusters),
        "groups_after": len(now.clusters),
        "regrouped": _match_groups([list(c) for c in was.clusters],
                                   [list(c) for c in now.clusters])["moved"],
        "spare": spare,
        "clusters": [list(c) for c in now.clusters],
        "alternatives": [r for r in ranked if r["film"] != candidate][:8],
        "rank": rank,
        "of": len(rivals) + 1,
        "over": (len(full) - slots) if slots else 0,
        "chance": _against_chance(m, full, (pool or []) + full) if pool else None,
    }


CHOOSE_CAP = 400


def _touching(m, lineup, picked):
    out = []
    for i, a in enumerate(picked):
        out.extend(m.distance(a, b) for b in picked[i + 1:])
        out.extend(m.distance(a, t) for t in lineup)
    return tuple(sorted(out))


def _choose_best(m, lineup, candidates, slots):
    from itertools import combinations

    candidates = [c for c in candidates if c not in set(lineup)]
    if not candidates or slots < 1:
        return None
    slots = min(slots, len(candidates))
    if _choose(len(candidates), slots) > CHOOSE_CAP:
        raise Refused(422, "Too many ways to choose from that many titles. "
                           "Give fewer, or ask for more slots.")

    was = analyse(_subset(m, lineup), stability=False)
    tried = []
    for picked in combinations(candidates, slots):
        full = lineup + list(picked)
        a = analyse(_subset(m, full), stability=False)
        tried.append({
            "films": list(picked),
            "groups": len(a.clusters),
            "profile": _touching(m, lineup, list(picked)),
            "clusters": [list(c) for c in a.clusters],
            "roles": {
                t: ("bridge" if any(b["film"] == t for b in a.bridges)
                    else "alone" if any(i["film"] == t for i in a.isolated)
                    else "interior")
                for t in picked
            },
            "connects": {b["film"]: b["connects"] for b in a.bridges
                         if b["film"] in set(picked)},
            "joins": {t: next((i for i, c in enumerate(a.clusters) if t in c),
                              None) for t in picked},
        })

    tried.sort(key=lambda r: (tuple(-v for v in r["profile"]), r["films"]))
    best = tried[0]
    return {
        "best": {k: v for k, v in best.items() if k != "profile"},
        "closest": round(best["profile"][0], 6),
        "groups_before": len(was.clusters),
        "next": ({k: v for k, v in tried[1].items()
                  if k not in ("profile", "clusters")}
                 | {"closest": round(tried[1]["profile"][0], 6)}
                 if len(tried) > 1 else None),
        "every": [{"films": r["films"], "groups": r["groups"],
                   "closest": round(r["profile"][0], 6),
                   "next": (round(r["profile"][1], 6)
                            if len(r["profile"]) > 1 else None)}
                  for r in tried],
        "slots": slots,
        "from": len(candidates),
    }
