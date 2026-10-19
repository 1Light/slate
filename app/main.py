from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent as agent_mod
from . import matrix as matrix_mod
from .qloo import Qloo, QlooError
from .resolve import Film, resolve_all
from .structure import analyse

ROOT = Path(__file__).resolve().parent.parent
LINEUPS = ROOT / "data" / "lineups"
STATIC = ROOT / "static"

MAX_FILMS = 24
MIN_FILMS = 4
CUSTOM_PER_HOUR = 6
AGENT_PER_HOUR = 12
WINDOW = 3600

app = FastAPI(title="Slate", docs_url=None, redoc_url=None)
_hits: dict[str, list[float]] = defaultdict(list)


class SlateRequest(BaseModel):
    films: list[str] = Field(min_length=MIN_FILMS, max_length=MAX_FILMS)
    name: str = "Your slate"


class AgentRequest(BaseModel):
    slug: str | None = None
    films: list[str] | None = None
    name: str = "Your slate"


def _over_limit(request: Request, bucket: str, cap: int) -> bool:
    ip = request.client.host if request.client else "unknown"
    key = f"{bucket}:{ip}"
    now = time.time()
    _hits[key] = [t for t in _hits[key] if now - t < WINDOW]
    if len(_hits[key]) >= cap:
        return True
    _hits[key].append(now)
    return False


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
        raise HTTPException(404, "No such programme.")
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
        "bridges": [{**b, "betweenness": round(b["betweenness"], 3)} for b in a.bridges],
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
    "urn:entity:tv_show": "television",
    "urn:entity:podcast": "podcasts",
}

ENTITY_NOUN = {
    "urn:entity:movie": ("film", "films"),
    "urn:entity:artist": ("act", "acts"),
    "urn:entity:book": ("book", "books"),
    "urn:entity:tv_show": ("series", "series"),
    "urn:entity:podcast": ("show", "shows"),
}

ENTITY_VIEW = {
    "urn:entity:artist": "Music",
    "urn:entity:book": "Books",
    "urn:entity:podcast": "Podcasts",
    "urn:entity:tv_show": "Television",
}
VIEW_ORDER = ["urn:entity:artist", "urn:entity:book",
              "urn:entity:podcast", "urn:entity:tv_show"]

OTHER_TYPES = ("urn:entity:artist",)
ENOUGH = 0.7


def _read_as(qloo, films, entity_type):
    best = (entity_type, *resolve_all(qloo, films, entity_type))
    if len(best[1]) >= len(films) * ENOUGH:
        return best
    for other in OTHER_TYPES:
        if other == entity_type:
            continue
        got = resolve_all(qloo, films, other)
        if len(got[0]) > len(best[1]):
            best = (other, *got)
        if len(best[1]) >= len(films) * ENOUGH:
            break
    return best


def _pipeline(name, note, films, entity_type, source):
    qloo = Qloo()
    if source == "custom":
        entity_type, resolved, failed = _read_as(qloo, films, entity_type)
    else:
        resolved, failed = resolve_all(qloo, films, entity_type)
    if len(resolved) < MIN_FILMS:
        raise HTTPException(422, "Too few titles were found in Qloo to read a shape.")
    m = matrix_mod.build(qloo, resolved, entity_type)
    if len(m.films) < MIN_FILMS:
        raise HTTPException(422, "Too few titles have affinity data to compare.")
    a = analyse(m)
    shape = _shape(name, note, resolved, m, a, source, failed)
    shape["entity_type"] = entity_type
    shape["reading"] = ENTITY_LABEL.get(entity_type, "entities")
    one, many = ENTITY_NOUN.get(entity_type, ("item", "items"))
    shape["noun"] = one
    shape["nouns"] = many
    return qloo, resolved, m, a, shape


@app.get("/api/lineups")
def lineups():
    out = []
    for path in sorted(LINEUPS.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        full = data.get("name", path.stem)
        out.append({
            "slug": path.stem,
            "name": full,
            "short": data.get("short") or full.split("—")[0].strip(),
            "note": data.get("note", ""),
            "count": len(data.get("films", [])),
            "order": data.get("order", 99),
        })
    out.sort(key=lambda x: (x["order"], x["slug"]))
    return out


@app.get("/api/lineups/{slug}")
def lineup(slug: str):
    name, note, films, entity_type = _load_lineup(slug)
    try:
        _, _, _, _, shape = _pipeline(name, note, films, entity_type, "preset")
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc
    return shape


@app.post("/api/analyse")
def analyse_custom(req: SlateRequest, request: Request):
    if _over_limit(request, "analyse", CUSTOM_PER_HOUR):
        raise HTTPException(429, "Hourly limit reached for new slates. The three "
                                 "festival programmes are already computed and free.")
    films = _films_from_lines(req.films)
    if len(films) < MIN_FILMS:
        raise HTTPException(422, f"Give at least {MIN_FILMS} titles.")
    try:
        _, _, _, _, shape = _pipeline(req.name, "", films, "urn:entity:movie", "custom")
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc
    return shape


@app.post("/api/agent")
def run_agent(req: AgentRequest, request: Request):
    if _over_limit(request, "agent", AGENT_PER_HOUR):
        raise HTTPException(429, "Hourly limit reached for the agent.")

    if req.slug:
        name, note, films, entity_type = _load_lineup(req.slug)
    elif req.films:
        name, note, entity_type = req.name, "", "urn:entity:movie"
        films = _films_from_lines(req.films)
    else:
        raise HTTPException(422, "Give a programme or a list of titles.")

    try:
        source = "agent" if req.slug else "custom"
        qloo, _, m, a, shape = _pipeline(name, note, films, entity_type, source)
        result = agent_mod.improve(qloo, m, a, slate_name=name,
                                   entity_type=shape["entity_type"])
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc

    return {"shape": shape, "agent": agent_mod.to_dict(result)}


PRECOMPUTED = PROJECT_ROOT / "data" / "precomputed.json" if "PROJECT_ROOT" in dir() else None


@app.get("/api/compare")
def compare():
    cached = LINEUPS.parent / "precomputed.json"
    if cached.exists():
        try:
            return JSONResponse(json.loads(cached.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass

    out = []
    for path in sorted(LINEUPS.glob("*.json"),
                       key=lambda p: (json.loads(p.read_text(encoding="utf-8"))
                                      .get("order", 99), p.stem)):
        slug = path.stem
        try:
            name, note, films, entity_type = _load_lineup(slug)
            shape = _pipeline(name, note, films, entity_type, "preset")[-1]
        except Exception:
            continue
        out.append(_compare_row(slug, shape))
    return JSONResponse(out)


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


@app.get("/api/views")
def views():
    out = []
    for et in VIEW_ORDER:
        for path in sorted(LINEUPS.glob("_probe-*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("entity_type") != et:
                continue
            out.append({
                "slug": path.stem,
                "label": ENTITY_VIEW[et],
                "name": data.get("name", path.stem),
                "count": len(data.get("films", [])),
            })
            break
    return JSONResponse(out)


@app.get("/api/validation")
def validation():
    out = {}
    path = ROOT / "data" / "validation.json"
    if path.exists():
        try:
            out = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out = {}
    out["bridge"] = _bridge_check()
    out["lineup_ari"] = _lineup_ari()
    return JSONResponse(out)


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


@app.get("/health")
def health():
    return JSONResponse({"ok": True})


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
