from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .build import (ENTITY_VIEW, LINEUPS, MIN_FILMS, ROOT, VIEW_ORDER,
                    Refused, _compare_row, _films_from_lines, _lineup_ari,
                    ENTITY_LABEL, _best_subset_fast, _bridge_check, _diff,
                    _load_lineup, _pipeline, _shape_from, _subset)
from .agent import improve, to_dict
from .qloo import Qloo, QlooError
from .structure import analyse

STATIC = ROOT / "static"

MAX_FILMS = 24
CUSTOM_PER_HOUR = 6
AGENT_PER_HOUR = 12
PANEL_PER_HOUR = 40
WINDOW = 3600

app = FastAPI(title="Slate", docs_url=None, redoc_url=None)
_hits: dict[str, list[float]] = defaultdict(list)


class SlateRequest(BaseModel):
    films: list[str] = Field(min_length=MIN_FILMS, max_length=MAX_FILMS)
    name: str = "Your slate"
    entity_type: str | None = None


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


@app.exception_handler(Refused)
def _refused(request: Request, exc: Refused):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status)


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


SERVED = ROOT / "data" / "served.json"
_served: dict | None = None


def _precomputed(slug: str):
    global _served
    if _served is None:
        try:
            _served = json.loads(SERVED.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _served = {}
    return _served.get(slug)


@app.get("/api/lineups/{slug}")
def lineup(slug: str):
    ready = _precomputed(slug)
    if ready is not None:
        return ready
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
        raise HTTPException(422, f"Add at least {MIN_FILMS} titles.")

    known = req.entity_type in ENTITY_LABEL
    start = req.entity_type if known else "urn:entity:movie"
    try:
        _, _, _, _, shape = _pipeline(req.name, "", films, start,
                                      "preset" if known else "custom")
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc
    return shape


class PanelRequest(BaseModel):
    slug: str | None = None
    films: list[str] | None = None
    entity_type: str | None = None
    swap: bool = False
    drop: list[str] = Field(default_factory=list)
    add: list[str] = Field(default_factory=list)
    keep: int | None = None


@app.post("/api/panel")
def panel(req: PanelRequest, request: Request):
    if _over_limit(request, "panel", PANEL_PER_HOUR):
        raise HTTPException(429, "Hourly limit reached for edits.")

    if req.slug:
        name, note, films, entity_type = _load_lineup(req.slug)
    elif req.films:
        name, note = "Your lineup", ""
        entity_type = (req.entity_type if req.entity_type in ENTITY_LABEL
                       else "urn:entity:movie")
        films = _films_from_lines(req.films)
    else:
        raise HTTPException(422, "Give a lineup or a list of titles.")

    extra = _films_from_lines([t for t in req.add if t.strip()])
    known = {f.title.lower() for f in films}
    extra = [f for f in extra if f.title.lower() not in known]

    try:
        _, _, m, _, base = _pipeline(name, note, films + extra, entity_type,
                                     "preset")
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc

    if extra:
        try:
            _, _, _, _, base = _pipeline(name, note, films, entity_type,
                                         "preset")
        except QlooError:
            pass

    dropped = {t.strip().lower() for t in req.drop if t.strip()}
    keep = [t for t in m.films if t.lower() not in dropped]
    if len(keep) < MIN_FILMS:
        raise HTTPException(422, f"Keep at least {MIN_FILMS} titles.")

    small = _subset(m, keep) if len(keep) < len(m.films) else m
    if req.keep is not None and req.keep < len(small.films):
        if req.keep < MIN_FILMS:
            raise HTTPException(422, f"Keep at least {MIN_FILMS} titles.")
        small = _subset(small, _best_subset_fast(small, req.keep))

    if req.swap:
        if _over_limit(request, "agent", AGENT_PER_HOUR):
            raise HTTPException(429, "Hourly limit reached for the agent.")
        try:
            result = improve(Qloo(), small, analyse(small), slate_name=name,
                             entity_type=entity_type)
        except QlooError as exc:
            raise HTTPException(503, str(exc)) from exc

        agent = to_dict(result)
        if not result.swaps:
            shape, _a = _shape_from(name, note, small, "panel", [], entity_type)
            shape["diff"] = _diff(base, shape)
            shape["added"] = []
            gone = sorted(set(m.films) - set(small.films))
            shape["dropped"] = gone
            shape["by_you"] = [t for t in gone if t.lower() in dropped]
            shape["agent"] = agent
            return shape

        titles = list(small.films)
        for sw in result.swaps:
            titles = [t for t in titles if t != sw.out_title] + [sw.in_title]
        try:
            _, _, _, _, shape = _pipeline(name, note, _films_from_lines(titles),
                                          entity_type, "preset")
        except QlooError as exc:
            raise HTTPException(503, str(exc)) from exc
        shape["diff"] = _diff(base, shape)
        shape["added"] = [sw.in_title for sw in result.swaps]
        here = {f["title"] for f in shape["films"]}
        gone = sorted(set(m.films) - here)
        shape["dropped"] = gone
        shape["by_you"] = [t for t in gone if t.lower() in dropped]
        shape["agent"] = agent
        return shape

    shape, _a = _shape_from(name, note, small, "panel", [], entity_type)
    shape["diff"] = _diff(base, shape)
    shape["added"] = [f.title for f in extra if f.title in small.films]
    gone = sorted(set(m.films) - set(small.films))
    shape["dropped"] = gone
    shape["by_you"] = [t for t in gone if t.lower() in dropped]
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
        result = improve(qloo, m, a, slate_name=name,
                                   entity_type=shape["entity_type"])
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc

    return {"shape": shape, "agent": to_dict(result)}


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


EXAMPLES = ROOT / "data" / "examples"


@app.get("/api/examples/{slug}")
def example(slug: str):
    path = EXAMPLES / f"{slug}.json"
    if not path.exists() or path.parent != EXAMPLES:
        raise HTTPException(404, "No such example.")
    d = json.loads(path.read_text(encoding="utf-8"))
    return {
        "name": d["name"],
        "entity_type": d["entity_type"],
        "titles": [f["title"] + (f" ({f['year']})" if f.get("year") else "")
                   for f in d["films"]],
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
    if "bridge" not in out:
        out["bridge"] = _bridge_check()
    if "lineup_ari" not in out:
        out["lineup_ari"] = _lineup_ari()
    return JSONResponse(out)


@app.get("/health")
def health():
    return JSONResponse({"ok": True})


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
