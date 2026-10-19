from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from .matrix import Matrix, censored_fill
from .qloo import Qloo, id_of, name_of, popularity_of, year_of
from .resolve import Resolved
from .structure import Analysis, analyse

CANDIDATES_PER_ROUND = 5
MAX_ROUNDS = 2
CANDIDATE_POOL = 24


@dataclass
class Step:
    act: str
    detail: str
    evidence: dict = field(default_factory=dict)


@dataclass
class Swap:
    out_title: str
    in_title: str
    in_id: str
    in_year: int | None
    in_popularity: float | None
    before: dict
    after: dict
    gain: float
    reason: str = ""


@dataclass
class AgentResult:
    steps: list[Step]
    swaps: list[Swap]
    rejected: list[dict]
    verdict: str
    calls: int
    before_groups: list[list[str]] = field(default_factory=list)
    after_groups: list[list[str]] = field(default_factory=list)


def _score(headline: dict, slate: int) -> float:
    k = headline["clusters"]
    ideal = max(2.0, slate / 3.0)
    reach = 3.0 * min(k, ideal) + 0.4 * max(0.0, k - ideal)
    crowding = headline["largest_cluster"] * 1.0
    shredding = 2.5 * max(0.0, k - ideal)
    return reach - crowding - shredding + headline["bridges"] * 0.5


def _most_redundant(analysis: Analysis, matrix: Matrix) -> str | None:
    groups = [g for g in analysis.clusters if len(g) >= 3]
    if not groups:
        return None
    biggest = max(groups, key=len)
    return min(biggest, key=lambda f: analysis.centrality[f])


def _centre_of_mass(analysis: Analysis) -> list[str]:
    ranked = sorted(analysis.centrality.items(), key=lambda kv: kv[1])
    return [f for f, _ in ranked[:3]]


def _rebuild_with(matrix: Matrix, out_title: str, in_title: str,
                  in_row: dict[str, int], resolved_in: Resolved) -> Matrix:
    films = [f for f in matrix.films if f != out_title] + [in_title]
    candidates = len(films) - 1
    ranks: dict[str, dict[str, float]] = {}
    imputed: dict[str, set[str]] = {}

    mirrored = {t: r for t, r in in_row.items() if t in films}
    fill = censored_fill(len(mirrored), candidates)

    for a in matrix.films:
        if a == out_title:
            continue
        row = {k: v for k, v in matrix.ranks.get(a, {}).items()
               if k != out_title and k in films}
        seen = in_row.get(a)
        row[in_title] = fill if seen is None else seen
        ranks[a] = row
        was = set(matrix.imputed.get(a, ()))
        was.discard(out_title)
        if seen is None:
            was.add(in_title)
        imputed[a] = was

    row = dict(mirrored)
    absent = [t for t in films if t != in_title and t not in row]
    for t in absent:
        row[t] = fill
    ranks[in_title] = row
    imputed[in_title] = set(absent)

    resolved = {k: v for k, v in matrix.resolved.items() if k != out_title}
    resolved[in_title] = resolved_in

    partial = sorted({t for a in imputed for t in imputed[a]})

    return Matrix(films=films, ranks=ranks, resolved=resolved,
                  ghosts=list(matrix.ghosts), partial=partial,
                  imputed=imputed)


def _row_from(entities: list[dict], id_to_title: dict[str, str]) -> dict[str, int]:
    row: dict[str, int] = {}
    position = 0
    for e in entities:
        rid = id_of(e)
        if not rid:
            continue
        title = id_to_title.get(rid.casefold())
        if title and title not in row:
            position += 1
            row[title] = position
    return row


def _explain(swap: Swap, analysis_before: Analysis, slate_name: str) -> str:
    key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    fallback = (
        f"Cutting {swap.out_title} costs the programme little: its audience is "
        f"already covered by the films around it. {swap.in_title} sits further "
        f"out, which is why the slate ends up reaching "
        f"{swap.after['clusters']} groups instead of {swap.before['clusters']}."
    )
    if not key or not model:
        return fallback

    prompt = (
        "You advise a film festival programmer. Explain one proposed change in "
        "two sentences, plainly, no marketing language, no exclamation marks.\n\n"
        f"Programme: {slate_name}\n"
        f"Remove: {swap.out_title}\n"
        f"Add: {swap.in_title}\n"
        f"Audience groups before: {swap.before['clusters']}, after: {swap.after['clusters']}\n"
        f"Largest group before: {swap.before['largest_cluster']}, "
        f"after: {swap.after['largest_cluster']}\n\n"
        "Say what the programme gains. Do not claim attendance figures or "
        "certainty about real audiences."
    )
    try:
        import requests
        r = requests.post(
            os.getenv("LLM_URL", "https://api.openai.com/v1/chat/completions"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "max_tokens": 160,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=20,
        )
        if r.ok:
            text = r.json()["choices"][0]["message"]["content"].strip()
            if text:
                return text
    except Exception:
        pass
    return fallback


def improve(qloo: Qloo, matrix: Matrix, analysis: Analysis,
            slate_name: str = "this slate",
            entity_type: str = "urn:entity:movie",
            rounds: int = MAX_ROUNDS) -> AgentResult:
    steps: list[Step] = []
    swaps: list[Swap] = []
    rejected: list[dict] = []
    start_calls = qloo.calls_made
    opening_groups = [list(g) for g in analysis.clusters]

    for round_no in range(1, rounds + 1):
        headline = analysis.headline
        steps.append(Step(
            "observe",
            f"{headline['films']} films reach {headline['clusters']} audiences; "
            f"the largest group holds {headline['largest_cluster']} slots.",
            {"round": round_no, **headline},
        ))

        out_title = _most_redundant(analysis, matrix)
        if not out_title:
            steps.append(Step("stop", "No group is crowded enough to be worth thinning."))
            break

        steps.append(Step(
            "plan",
            f"{out_title} sits closest to everything else in the biggest group, "
            f"so the programme would miss it least. Looking for a replacement "
            f"further out.",
            {"cut": out_title},
        ))

        centre = _centre_of_mass(analysis)
        in_slate_ids = [matrix.resolved[f].entity_id for f in matrix.films]
        pool = qloo.neighbours(
            [matrix.resolved[f].entity_id for f in centre],
            filter_type=entity_type,
            take=CANDIDATE_POOL,
            exclude=in_slate_ids,
        )
        if not pool:
            steps.append(Step("stop", "Qloo returned no candidates outside the slate."))
            break

        shortlist = list(reversed(pool))[:CANDIDATES_PER_ROUND]
        steps.append(Step(
            "search",
            f"Qloo returned {len(pool)} films outside the slate. Testing the "
            f"{len(shortlist)} least like its centre.",
            {"candidates": [name_of(e) for e in shortlist]},
        ))

        keep_titles = [f for f in matrix.films if f != out_title]
        keep_ids = [matrix.resolved[f].entity_id for f in keep_titles]
        id_to_title = {matrix.resolved[f].entity_id.casefold(): f for f in keep_titles}
        base = _score(analysis.headline, len(matrix.films))

        best: tuple[float, Swap, Matrix, Analysis] | None = None

        for entity in shortlist:
            cid, cname = id_of(entity), name_of(entity)
            if not cid or cname in matrix.films:
                continue

            returned = qloo.rank_within(cid, keep_ids, entity_type)
            row = _row_from(returned, id_to_title)
            if len(row) < max(3, len(keep_titles) // 2):
                rejected.append({"film": cname, "why": "too little affinity data to place it"})
                continue

            stand_in = Resolved(
                film=type("F", (), {"title": cname, "year": year_of(entity) or 0,
                                    "director": "", "aliases": []})(),
                entity_id=cid, qloo_name=cname, qloo_year=year_of(entity),
                popularity=popularity_of(entity), score=10,
            )
            trial_matrix = _rebuild_with(matrix, out_title, cname, row, stand_in)
            try:
                trial = analyse(trial_matrix)
            except ValueError:
                continue

            gain = _score(trial.headline, len(matrix.films)) - base
            if gain <= 0:
                rejected.append({
                    "film": cname,
                    "why": f"lands inside an existing group; "
                           f"still {trial.headline['clusters']} audiences",
                })
                continue
            if best is None or gain > best[0]:
                best = (gain, Swap(
                    out_title=out_title, in_title=cname, in_id=cid,
                    in_year=year_of(entity), in_popularity=popularity_of(entity),
                    before=dict(analysis.headline), after=dict(trial.headline),
                    gain=round(gain, 2),
                ), trial_matrix, trial)

        if best is None:
            steps.append(Step(
                "decide",
                "None of the candidates opened a group the programme does not "
                "already have. Leaving the slate alone.",
                {"rejected": len(rejected)},
            ))
            break

        gain, swap, matrix, analysis = best
        swap.reason = _explain(swap, analysis, slate_name)
        swaps.append(swap)
        steps.append(Step(
            "decide",
            f"Swap {swap.out_title} for {swap.in_title}: "
            f"{swap.before['clusters']} audiences becomes {swap.after['clusters']}.",
            {"gain": swap.gain, "after": swap.after},
        ))

    if swaps:
        first, last = swaps[0], swaps[-1]
        n = len(swaps)
        how_many = f"{n} change{'' if n == 1 else 's'}"
        groups_before, groups_after = first.before["clusters"], last.after["clusters"]
        biggest_before = first.before["largest_cluster"]
        biggest_after = last.after["largest_cluster"]
        bridged = last.after["bridges"] - first.before["bridges"]

        wins = []
        if groups_after > groups_before:
            wins.append(f"take the programme from {groups_before} audiences "
                        f"to {groups_after}")
        if biggest_after < biggest_before:
            wins.append(f"bring the largest group down from {biggest_before} "
                        f"slots to {biggest_after}")
        if bridged > 0:
            wins.append("open a route between groups that had none"
                        if bridged == 1
                        else f"open {bridged} new routes between groups")
        if not wins:
            wins.append("leave the slate the same size but less concentrated")

        joined = (wins[0] if len(wins) == 1
                  else ", ".join(wins[:-1]) + f", and {wins[-1]}")
        verdict = f"{how_many} would {joined}."

    else:
        verdict = (
            "The agent found no change worth making. Every replacement it "
            "tested landed inside a group the programme already covers."
        )

    return AgentResult(steps=steps, swaps=swaps, rejected=rejected[:8],
                       verdict=verdict, calls=qloo.calls_made - start_calls,
                       before_groups=opening_groups,
                       after_groups=[list(g) for g in analysis.clusters])


def to_dict(result: AgentResult) -> dict[str, Any]:
    return {
        "verdict": result.verdict,
        "calls": result.calls,
        "steps": [{"act": s.act, "detail": s.detail, "evidence": s.evidence}
                  for s in result.steps],
        "swaps": [{
            "out": s.out_title, "in": s.in_title, "year": s.in_year,
            "popularity": s.in_popularity, "before": s.before, "after": s.after,
            "gain": s.gain, "reason": s.reason,
        } for s in result.swaps],
        "rejected": result.rejected,
        "before_groups": result.before_groups,
        "after_groups": result.after_groups,
    }
