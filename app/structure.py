from __future__ import annotations

from dataclasses import dataclass, field
from random import Random

from .matrix import Matrix

KNN_VALUES = (2, 3, 4)
BRIDGE_TOP_N = 3
POPULAR_QUANTILE = 0.75

NULL_ROUNDS = 12
SINGLETON_SHARE = 0.25
MOST_GROUPS = 0.5
WEAK_SEPARATION = 0.3
K_TOLERANCE = 0.03

ISOLATION_TOP_N = 3
ISOLATION_MIN = 1.0
LOF_K_SMALL = (2, 3, 4)
LOF_K_LARGE = (3, 4, 5)
SMALL_SLATE = 12
CONFOUND_MIN = 0.30


@dataclass
class Analysis:
    clusters: list[list[str]]
    member: dict[str, int]
    merge_order: list[tuple[float, list[str], list[str]]]
    centrality: dict[str, float]
    bridges: list[dict]
    isolated: list[dict]
    tightest_pairs: list[tuple[str, str, float, int]]
    completeness: dict = field(default_factory=dict)
    isolation: dict[str, float] = field(default_factory=dict)
    cut_check: dict = field(default_factory=dict)
    stability: dict = field(default_factory=dict)
    popularity_confound: float | None = None

    @property
    def headline(self) -> dict:
        multi = [g for g in self.clusters if len(g) > 1]
        n = sum(len(g) for g in self.clusters)
        return {
            "films": n,
            "clusters": len(self.clusters),
            "largest_cluster": max((len(g) for g in self.clusters), default=0),
            "duplicate_slots": sum(len(g) - 1 for g in multi),
            "bridges": len(self.bridges),
        }


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def _corr(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


def _lof(matrix: Matrix, films: list[str], k: int) -> dict[str, float]:
    n = len(films)
    k = max(1, min(k, n - 1))

    ordered = {f: sorted((matrix.distance(f, g), g) for g in films if g != f)
               for f in films}
    k_dist = {f: ordered[f][k - 1][0] for f in films}
    nbrs = {f: [g for d, g in ordered[f] if d <= k_dist[f] + 1e-9] for f in films}

    lrd = {}
    for f in films:
        reach = [max(k_dist[g], matrix.distance(f, g)) for g in nbrs[f]]
        mean_reach = max(sum(reach) / len(reach), 1e-9)
        lrd[f] = 1.0 / mean_reach

    return {f: sum(lrd[g] / lrd[f] for g in nbrs[f]) / len(nbrs[f])
            for f in films}


def _unit(matrix: Matrix, a: str, b: str) -> float:
    n = len(matrix.films)
    if n < 3:
        return matrix.distance(a, b)
    return (matrix.distance(a, b) - 1) / (n - 2)


def _silhouette(matrix: Matrix, clusters: list[list[str]]) -> float | None:
    total = sum(len(g) for g in clusters)
    if len(clusters) < 2 or len(clusters) >= total:
        return None
    acc = 0.0
    for g in clusters:
        for f in g:
            if len(g) == 1:
                continue
            a = sum(_unit(matrix, f, x) for x in g if x != f) / (len(g) - 1)
            b = min(sum(_unit(matrix, f, x) for x in h) / len(h)
                    for h in clusters if h is not g)
            if max(a, b) > 0:
                acc += (b - a) / max(a, b)
    return acc / total


def _choose_k(matrix: Matrix, films: list[str], merges) -> dict:
    n = len(films)
    scored = []
    for k in range(2, n):
        groups = _cut_to(films, merges, k)
        if len(groups) != k:
            continue
        s = _silhouette(matrix, groups)
        if s is None:
            continue
        alone = sum(1 for g in groups if len(g) == 1)
        scored.append({"k": k, "silhouette": round(s, 9), "alone": alone})
    if not scored:
        return {"scored": [], "chosen": None, "best": None}

    usable = [r for r in scored
              if r["alone"] <= n * SINGLETON_SHARE
              and r["k"] <= n * MOST_GROUPS] or scored
    peak = max(r["silhouette"] for r in usable)

    close = [r for r in usable
             if round(peak - r["silhouette"], 9) <= K_TOLERANCE]
    best = min(close, key=lambda r: r["k"])
    return {
        "scored": scored,
        "chosen": best["k"],
        "best": best["silhouette"],
        "peak": peak,
        "peak_k": max(usable, key=lambda r: r["silhouette"])["k"],
        "within_noise": sorted(r["k"] for r in close),
    }


def _rerank(ranks, keep: list[str]) -> dict[str, dict[str, float]]:
    out = {}
    worst = len(keep) + 1
    for a in keep:
        def at(b, row=ranks.get(a, {})):
            v = row.get(b)
            return worst if v is None else v
        others = sorted((b for b in keep if b != a), key=at)
        out[a] = {b: i + 1 for i, b in enumerate(others)}
    return out


def _leave_one_out(matrix: Matrix, clusters: list[list[str]]) -> tuple:
    films = matrix.films
    base = {f: i for i, g in enumerate(clusters) for f in g}
    holds: dict[int, list[float]] = {i: [] for i in range(len(clusters))}
    rands: list[float] = []

    for drop in films:
        keep = [f for f in films if f != drop]
        small = Matrix(films=keep, ranks=_rerank(matrix.ranks, keep),
                       resolved=matrix.resolved)
        merges = _agglomerate(small)
        pick = _choose_k(small, keep, merges)
        if not pick["chosen"]:
            continue
        groups = _cut_to(keep, merges, pick["chosen"])
        got = {f: i for i, g in enumerate(groups) for f in g}

        r = _rand(base, got, keep)
        if r is not None:
            rands.append(r)
        for i, g in enumerate(clusters):
            left = [f for f in g if f != drop]
            if len(left) < 2:
                continue
            holds[i].append(max(_jaccard(left, h) for h in groups))
    return holds, rands


def _chance_hold(matrix: Matrix, sizes: list[int], rounds: int = NULL_ROUNDS) -> dict:
    films = matrix.films
    want = sorted(set(sizes))
    seen: dict[int, list[float]] = {s: [] for s in want}
    rng = Random(len(films) * 101 + sum(want))

    for _ in range(rounds):
        shuffled = {}
        for a in films:
            others = [b for b in films if b != a]
            rng.shuffle(others)
            shuffled[a] = {b: i + 1 for i, b in enumerate(others)}
        noise = Matrix(films=films, ranks=shuffled, resolved=matrix.resolved)

        pool = list(films)
        rng.shuffle(pool)
        groups, at = [], 0
        for size in sizes:
            groups.append(pool[at:at + size])
            at += size
        groups = [g for g in groups if g]
        if len(groups) < 2:
            continue

        holds, _ = _leave_one_out(noise, groups)
        for i, g in enumerate(groups):
            if len(g) in seen and holds[i]:
                seen[len(g)].append(sum(holds[i]) / len(holds[i]))

    return {s: (sum(v) / len(v) if v else None) for s, v in seen.items()}


def _stability(matrix: Matrix, clusters: list[list[str]]) -> dict:
    films = matrix.films
    if len(films) < 6:
        return {}

    holds, rands = _leave_one_out(matrix, clusters)
    sizes = [len(g) for g in clusters]
    chance = _chance_hold(matrix, sizes)

    out = []
    for i, g in enumerate(clusters):
        vals = holds[i]
        j = sum(vals) / len(vals) if vals else None
        base = chance.get(len(g))
        lift = None if j is None or base is None else j - base
        out.append({
            "size": len(g),
            "jaccard": None if j is None else round(j, 2),
            "chance": None if base is None else round(base, 2),
            "lift": None if lift is None else round(lift, 2),
            "verdict": None if lift is None
                       else "holds" if lift >= 0.25
                       else "holds weakly" if lift >= 0.10
                       else "no better than chance",
        })
    return {
        "ari": round(sum(rands) / len(rands), 3) if rands else None,
        "clusters": out,
        "runs": len(rands),
        "null_rounds": NULL_ROUNDS,
    }


def _rand(a: dict, b: dict, shared: list[str]) -> float | None:
    if len(shared) < 3:
        return None
    pairs = [(x, y) for i, x in enumerate(shared) for y in shared[i + 1:]]
    together_a = sum(1 for x, y in pairs if a[x] == a[y])
    together_b = sum(1 for x, y in pairs if b[x] == b[y])
    both = sum(1 for x, y in pairs if a[x] == a[y] and b[x] == b[y])
    expected = together_a * together_b / len(pairs)
    most = (together_a + together_b) / 2
    return 1.0 if most == expected else (both - expected) / (most - expected)


def _jaccard(one: list[str], two: list[str]) -> float:
    union = len(set(one) | set(two))
    return len(set(one) & set(two)) / union if union else 0.0


def _agglomerate(matrix: Matrix):
    films = matrix.films
    clusters = [[f] for f in films]
    merges = []
    while len(clusters) > 1:
        best = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                d = sum(_unit(matrix, x, y) for x in clusters[i] for y in clusters[j])
                d /= len(clusters[i]) * len(clusters[j])
                key = (round(d, 12), min(clusters[i] + clusters[j]))
                if best is None or key < best[0]:
                    best = (key, d, i, j)
        _key, d, i, j = best
        merges.append((d, list(clusters[i]), list(clusters[j])))
        clusters = [c for k, c in enumerate(clusters) if k not in (i, j)] + [clusters[i] + clusters[j]]
    return merges


def _cut_to(films: list[str], merges, k: int):
    groups = [[f] for f in films]
    for _d, a, b in merges:
        if len(groups) <= k:
            break
        ia = next((i for i, g in enumerate(groups) if set(a) <= set(g)), None)
        ib = next((i for i, g in enumerate(groups) if set(b) <= set(g)), None)
        if ia is None or ib is None or ia == ib:
            continue
        joined = groups[ia] + groups[ib]
        groups = [g for i, g in enumerate(groups) if i not in (ia, ib)]
        groups.append(joined)
    return sorted(groups, key=len, reverse=True)


def _knn(matrix: Matrix, k: int) -> dict[str, set[str]]:
    adj = {f: set() for f in matrix.films}
    for a in matrix.films:
        nearest = sorted((b for b in matrix.films if b != a),
                         key=lambda b: (round(matrix.distance(a, b), 12), b))
        for b in nearest[:k]:
            adj[a].add(b)
            adj[b].add(a)
    return adj


def _betweenness(films: list[str], adj: dict[str, set[str]]) -> dict[str, float]:
    bc = {f: 0.0 for f in films}
    for s in films:
        stack, pred = [], {f: [] for f in films}
        sigma = {f: 0 for f in films}
        dist = {f: -1 for f in films}
        sigma[s], dist[s] = 1, 0
        queue = [s]
        while queue:
            v = queue.pop(0)
            stack.append(v)
            for w in sorted(adj[v]):
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = {f: 0.0 for f in films}
        while stack:
            w = stack.pop()
            for v in sorted(pred[w]):
                if sigma[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                bc[w] += delta[w]
    n = len(films)
    scale = (n - 1) * (n - 2) if n > 2 else 1
    return {f: 2 * v / scale for f, v in bc.items()}


def _completeness(matrix: Matrix) -> dict:
    films = matrix.films
    n = len(films)
    expected = n * (n - 1)
    present = sum(
        1
        for a in films
        for b in films
        if a != b and matrix.observed(a, b)
    )
    per_film = {}
    for f in films:
        got = sum(1 for a in films if a != f and matrix.observed(a, f))
        per_film[f] = got / (n - 1) if n > 1 else 1.0

    thin = sorted((f for f, frac in per_film.items() if frac < 1.0),
                  key=lambda f: per_film[f])

    return {
        "filled": present,
        "expected": expected,
        "fraction": present / expected if expected else 1.0,
        "per_film": per_film,
        "incomplete": thin,
        "ghosts": list(matrix.ghosts),
    }


def _redundant_pairs(matrix: Matrix, clusters: list[list[str]],
                     big: int = 5, many: int = 3) -> list[tuple]:
    out = []
    for i, group in enumerate(clusters):
        if len(group) < 2:
            continue
        pairs = sorted(
            ((a, b, matrix.distance(a, b))
             for n, a in enumerate(group) for b in group[n + 1:]),
            key=lambda p: p[2],
        )
        take = many if len(group) >= big else 1
        out.extend((a, b, d, i) for a, b, d in pairs[:take])
    return sorted(out, key=lambda p: p[2])


def analyse(matrix: Matrix, groups: int | None = None,
            stability: bool = True) -> Analysis:
    films = matrix.films
    n = len(films)
    if n < 4:
        raise ValueError("Need at least 4 films with usable data")

    merges = _agglomerate(matrix)

    pick = _choose_k(matrix, films, merges)

    best = pick.get("best")
    weak = best is not None and best < WEAK_SEPARATION
    pick["weak"] = weak

    if groups is None:
        groups = 1 if weak else (pick.get("chosen") or 2)
    pick["used"] = groups
    clusters = _cut_to(films, merges, groups)
    member = {t: i for i, g in enumerate(clusters) for t in g}

    centrality = {
        f: sum(matrix.distance(f, b) for b in films if b != f) / (n - 1)
        for f in films
    }

    bc_by_k = {k: _betweenness(films, _knn(matrix, k)) for k in KNN_VALUES}
    rank_at_k: dict[str, dict[int, int]] = {}
    for k, scores in bc_by_k.items():
        for pos, f in enumerate(sorted(films, key=lambda x: -scores[x]), 1):
            rank_at_k.setdefault(f, {})[k] = pos

    adj = _knn(matrix, 3)
    bridges = []
    for f in films:
        if max(rank_at_k[f].values()) > BRIDGE_TOP_N:
            continue
        spans = sorted({member[b] for b in adj[f]})
        if len(spans) < 2:
            continue
        bridges.append({
            "film": f,
            "betweenness": sum(bc_by_k[k][f] for k in KNN_VALUES) / len(KNN_VALUES),
            "worst_rank": max(rank_at_k[f].values()),
            "connects": spans,
            "via": sorted(adj[f], key=lambda b: member[b]),
            "popularity": matrix.popularity(f),
        })
    bridges.sort(key=lambda b: b["worst_rank"])

    ks = LOF_K_SMALL if n <= SMALL_SLATE else LOF_K_LARGE
    lof_by_k = {k: _lof(matrix, films, k) for k in ks}
    lof_mean = {f: sum(lof_by_k[k][f] for k in ks) / len(ks) for f in films}

    lof_rank: dict[str, dict[int, int]] = {}
    for k in ks:
        for pos, f in enumerate(sorted(films, key=lambda x: -lof_by_k[k][x]), 1):
            lof_rank.setdefault(f, {})[k] = pos

    pops = [matrix.popularity(f) for f in films]
    confound = None
    if all(p is not None for p in pops):
        confound = _corr([lof_mean[f] for f in films], pops)

    known = [p for p in pops if p is not None]
    popular_cut = _quantile(known, POPULAR_QUANTILE) if known else None
    explains = confound is not None and confound >= CONFOUND_MIN

    bridge_titles = {b["film"] for b in bridges}
    isolated = []
    for f in films:
        if f in bridge_titles:
            continue
        if lof_mean[f] <= ISOLATION_MIN:
            continue
        if max(lof_rank[f].values()) > ISOLATION_TOP_N:
            continue
        pop = matrix.popularity(f)
        if pop is None or popular_cut is None:
            kind = "unknown"
        elif explains and pop >= popular_cut:
            kind = "broad appeal"
        else:
            kind = "distinct audience"
        isolated.append({
            "film": f,
            "lof": lof_mean[f],
            "by_k": dict(lof_rank[f]),
            "cluster_size": len(clusters[member[f]]),
            "distance": centrality[f],
            "popularity": pop,
            "kind": kind,
        })
    isolated.sort(key=lambda x: -x["lof"])

    tightest = _redundant_pairs(matrix, clusters)

    return Analysis(
        clusters=clusters,
        member=member,
        merge_order=merges,
        centrality=centrality,
        bridges=bridges,
        isolated=isolated,
        tightest_pairs=tightest,
        completeness=_completeness(matrix),
        isolation=lof_mean,
        cut_check=pick,
        stability=_stability(matrix, clusters) if stability else {},
        popularity_confound=confound,
    )