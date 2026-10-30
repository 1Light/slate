from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi import Response
from fastapi.responses import (FileResponse, PlainTextResponse, HTMLResponse,
                               JSONResponse as _JSONResponse)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .build import (ENTITY_VIEW, LINEUPS, MIN_FILMS, ROOT, VIEW_ORDER,
                    MixedTypes,
                    Refused, _compare_row, _films_from_lines, _lineup_ari,
                    ENTITY_LABEL, ENTITY_NOUN, _against_chance,
                    _best_subset_fast, _bridge_check, _choose_best,
                    _diff, _fit_brief,
                    _load_lineup, _pipeline, _read_as, _shape_from,
                    _subset)
from . import paper, store
from .agent import improve, to_dict
from .audience import BALANCED, MODES, Reference, select
from .extract import (ExtractFailed, from_answers,
                      from_description, kinds_for)
from .ingest import (BadSource, DESCRIPTION, PREFERENCES, SURVEY,
                     read as read_source, sniff)
from .qloo import Qloo, QlooError, id_of
from .references import by_kind, resolve as resolve_refs
from .resolve import resolve_all
from .structure import analyse

STATIC = ROOT / "static"

MAX_FILMS = 24
MAX_CANDIDATES = 60
CUSTOM_PER_HOUR = 6
AGENT_PER_HOUR = 12
PANEL_PER_HOUR = 40
WINDOW = 3600

def _public_json(value):
    if isinstance(value, dict):
        return {key: _public_json(item) for key, item in value.items()
                if key not in {"popularity", "bridge_popularity", "top_popularity"}}
    if isinstance(value, (list, tuple)):
        return [_public_json(item) for item in value]
    return value


class JSONResponse(_JSONResponse):
    def render(self, content) -> bytes:
        return super().render(_public_json(content))


app = FastAPI(title="Slate", docs_url=None, redoc_url=None,
              default_response_class=JSONResponse)
_hits: dict[str, list[float]] = defaultdict(list)


class SlateRequest(BaseModel):
    films: list[str] = Field(min_length=MIN_FILMS, max_length=MAX_FILMS)
    name: str = "Your slate"
    entity_type: str | None = None


class AgentRequest(BaseModel):
    slug: str | None = None
    films: list[str] | None = None
    name: str = "Your slate"
    locked: list[str] = Field(default_factory=list)


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
    if len(films) > MAX_FILMS:
        raise HTTPException(422, f"{MAX_FILMS} titles at most.")

    known = req.entity_type in ENTITY_LABEL
    start = req.entity_type if known else "urn:entity:movie"
    try:
        _, _, _, _, shape = _pipeline(req.name, "", films, start,
                                      "preset" if known else "custom")
    except MixedTypes as mix:
        return JSONResponse(status_code=409, content={
            "mixed": True,
            "kinds": [{
                "entity_type": kind,
                "label": ENTITY_LABEL.get(kind, "titles"),
                "titles": titles,
                "enough": len(titles) >= MIN_FILMS,
            } for kind, titles in mix.found.items()],
            "missing": mix.missing,
            "least": MIN_FILMS,
        })
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
    locked: list[str] = Field(default_factory=list)


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

    lost: list[str] = []
    try:
        _, _, m, _, base = _pipeline(name, note, films + extra, entity_type,
                                     "preset")
        lost = list(base.get("unresolved") or [])
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
    chance = None
    if req.keep is not None and req.keep < len(small.films):
        if req.keep < MIN_FILMS:
            raise HTTPException(422, f"Keep at least {MIN_FILMS} titles.")
        held = [t for t in small.films if t in set(req.locked)]
        if len(held) > req.keep:
            raise Refused(422, f"You have locked {len(held)} titles, but "
                               f"requested {req.keep} slots. Unlock some "
                               "titles or increase the slot count to "
                               "continue.")
        was = list(small.films)
        small = _subset(small, _best_subset_fast(small, req.keep,
                                                 req.locked))
        chance = None if len(held) == req.keep else _against_chance(
            m, list(small.films), was)

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
            shape, _a = _shape_from(name, note, small, "panel", lost, entity_type)
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

    shape, _a = _shape_from(name, note, small, "panel", lost, entity_type)
    shape["diff"] = _diff(base, shape)
    shape["added"] = [f.title for f in extra if f.title in small.films]
    gone = sorted(set(m.films) - set(small.films))
    shape["dropped"] = gone
    shape["by_you"] = [t for t in gone if t.lower() in dropped]
    if chance:
        shape["chance"] = chance
    return shape


class BriefRequest(BaseModel):
    slug: str | None = None
    lineup: list[str] | None = None
    candidate: str
    pool: list[str] = Field(default_factory=list)
    entity_type: str | None = None
    slots: int | None = None
    locked: list[str] = Field(default_factory=list)


class ChooseRequest(BaseModel):
    lineup: list[str]
    candidates: list[str]
    slots: int = 1
    entity_type: str | None = None


class SpaceNew(BaseModel):
    owner: str
    titles: list[str]
    name: str | None = None
    entity_type: str | None = None
    audience: dict | None = None


class AudienceRead(BaseModel):
    kind: str
    text: str
    filename: str = ""
    synthetic: bool = False


class AudienceBuild(BaseModel):
    owner: str
    references: list[dict]
    candidates: list[str]
    entity_type: str
    slots: int
    mode: str = BALANCED
    locked: list[str] = Field(default_factory=list)
    name: str | None = None
    audience: dict | None = None


class SpaceEdit(BaseModel):
    owner: str
    name: str | None = None
    titles: list[str] | None = None
    slots: int | None = None
    placed: int | None = None
    locked: list[str] | None = None


class SpaceVersion(BaseModel):
    owner: str
    titles: list[str]
    groups: int | None = None
    sizes: list[int] = Field(default_factory=list)


def _owner(raw: str) -> str:
    clean = "".join(c for c in (raw or "") if c.isalnum())[:64]
    if len(clean) < 8:
        raise HTTPException(422, "Missing or malformed id.")
    return clean


@app.get("/api/spaces")
def spaces(owner: str, request: Request):
    out = []
    for w in store.listing(_owner(owner)):
        kept = w["versions"]
        row = {k: v for k, v in w.items() if k != "versions"}
        row["versions"] = len(kept)
        newest = next((v for v in kept if v.get("sizes")), None)
        if newest:
            row["sizes"] = newest["sizes"]
            row["groups"] = newest.get("groups")
        out.append(row)
    return {"spaces": out}


@app.get("/api/spaces/{wid}")
def space(wid: str, owner: str, request: Request):
    got = store.read(_owner(owner), wid)
    if got is None:
        raise HTTPException(404, "No such workspace.")
    return got


@app.post("/api/spaces")
def space_new(req: SpaceNew, request: Request):
    if _over_limit(request, "space", PANEL_PER_HOUR):
        raise HTTPException(429, "Hourly limit reached.")
    titles = [t.strip() for t in req.titles if t.strip()]
    if len(titles) < MIN_FILMS:
        raise HTTPException(422, f"Give at least {MIN_FILMS} titles.")
    if len(titles) > MAX_FILMS:
        raise HTTPException(422, f"{MAX_FILMS} titles at most.")

    kind = req.entity_type if req.entity_type in ENTITY_LABEL else None
    if kind is None:
        films = _films_from_lines(titles)
        try:
            kind = _read_as(Qloo(), films, "urn:entity:movie")[0]
        except MixedTypes as mix:
            return JSONResponse(status_code=409, content={
                "mixed": True,
                "kinds": [{
                    "entity_type": k,
                    "label": ENTITY_LABEL.get(k, "titles"),
                    "titles": got,
                    "enough": len(got) >= MIN_FILMS,
                } for k, got in mix.found.items()],
                "missing": mix.missing,
                "least": MIN_FILMS,
            })
        except QlooError as exc:
            raise HTTPException(503, str(exc)) from exc
    name = (req.name or titles[0])[:120]
    return store.create(_owner(req.owner), name, titles, kind)


@app.patch("/api/spaces/{wid}")
def space_edit(wid: str, req: SpaceEdit, request: Request):
    fields = {k: v for k, v in
              (("name", req.name), ("titles", req.titles),
               ("slots", req.slots), ("placed", req.placed),
               ("locked", req.locked))
              if v is not None}
    got = store.update(_owner(req.owner), wid, **fields)
    if got is None:
        raise HTTPException(404, "No such workspace.")
    return got


@app.post("/api/spaces/{wid}/versions")
def space_version(wid: str, req: SpaceVersion, request: Request):
    got = store.add_version(_owner(req.owner), wid, req.titles, req.groups,
                            req.sizes)
    if got is None:
        raise HTTPException(404, "No such workspace.")
    return got


@app.delete("/api/spaces/{wid}")
def space_delete(wid: str, owner: str, request: Request):
    if not store.remove(_owner(owner), wid):
        raise HTTPException(404, "No such workspace.")
    return {"gone": wid}


@app.post("/api/brief")
def brief(req: BriefRequest, request: Request):
    if _over_limit(request, "brief", PANEL_PER_HOUR):
        raise HTTPException(429, "Hourly limit reached.")

    if req.slug:
        name, note, films, entity_type = _load_lineup(req.slug)
    elif req.lineup:
        name, note = "Your lineup", ""
        entity_type = (req.entity_type if req.entity_type in ENTITY_LABEL
                       else "urn:entity:movie")
        films = _films_from_lines(req.lineup)
    else:
        raise HTTPException(422, "Give a lineup or a list of titles.")

    known = {f.title.lower() for f in films}
    if req.candidate.strip().lower() in known:
        here = next(f.title for f in films
                    if f.title.lower() == req.candidate.strip().lower())
        raise Refused(409, f"{here} is already in this lineup.")

    extra = _films_from_lines([req.candidate] + list(req.pool))
    extra = [f for f in extra if f.title.lower() not in known]

    try:
        _, _, m, _, shape = _pipeline(name, note, films + extra, entity_type,
                                      "preset")
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc

    dropped = list(shape.get("excluded") or [])

    def placed(title):
        hit = [t for t in m.films if t.lower() == title.lower()]
        return hit[0] if hit else None

    want = placed(req.candidate)
    if want is None:
        kind = ENTITY_LABEL.get(entity_type, "titles")
        if any(t.lower() == req.candidate.lower() for t in (dropped or [])):
            raise Refused(422, f"Qloo has {req.candidate} but no data "
                               "linking it to this lineup, so it cannot be "
                               "compared.")
        raise Refused(404, f"Slate could not find {_tidy(req.candidate)} "
                           f"among {kind}." + _year_hint(entity_type))

    lineup = [t for t in m.films if t.lower() in known]
    if len(lineup) < 2:
        raise HTTPException(422, "The lineup needs at least two titles.")

    pool = [t for t in m.films if t not in set(lineup)]
    small = _subset(m, lineup + [want])
    out = _fit_brief(m, lineup, want, pool=lineup + pool,
                     slots=req.slots, locked=req.locked)
    out["name"] = name
    out["noun"], out["nouns"] = ENTITY_NOUN.get(entity_type, ("item", "items"))
    out["entity_type"] = entity_type
    out["shape"] = _shape_from(name, note, small, "brief", [], entity_type,
                               stability=False)[0]
    return out


class PaperRequest(BaseModel):
    kind: str
    name: str = "Your lineup"
    slots: int | None = None
    data: dict


def _document(req: PaperRequest) -> str:
    if req.kind == "lineup":
        return paper.lineup_doc(req.data, req.name, req.slots)
    if req.kind == "stand":
        return paper.stand_doc(req.data, req.name)
    if req.kind == "choose":
        return paper.choose_doc(req.data, req.name)
    raise HTTPException(422, "Unknown document.")


@app.post("/api/paper")
def paper_html(req: PaperRequest, request: Request):
    return HTMLResponse(_document(req))


@app.post("/api/paper.pdf")
def paper_pdf(req: PaperRequest, request: Request):
    made = paper.as_pdf(_document(req))
    if made is None:
        raise HTTPException(501, "No PDF renderer on this server.")
    name = "".join(c for c in req.name if c.isalnum() or c in " -_")[:60]
    return Response(
        made, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="{name or "Slate"}.pdf"'})


@app.post("/api/choose")
def choose(req: ChooseRequest, request: Request):
    if _over_limit(request, "choose", PANEL_PER_HOUR):
        raise HTTPException(429, "Hourly limit reached.")

    kind = (req.entity_type if req.entity_type in ENTITY_LABEL
            else "urn:entity:movie")
    base = _films_from_lines(req.lineup)
    known = {f.title.lower() for f in base}
    asked = _films_from_lines(req.candidates)
    here = [_tidy(f.title) for f in asked if f.title.lower() in known]
    extra = [f for f in asked if f.title.lower() not in known]
    slots = max(1, req.slots)

    if not extra:
        raise Refused(409, _nameList(here) + (" are" if len(here) > 1
                                              else " is")
                      + " already in this lineup. Give titles that are not "
                        "in it yet.")

    try:
        _, _, m, _, shape = _pipeline("Your lineup", "", base + extra, kind,
                                      "preset")
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc

    lineup = [t for t in m.films if t.lower() in known]
    pool = [t for t in m.films if t not in set(lineup)]
    dropped = list(shape.get("excluded") or [])
    thin = [f.title for f in extra
            if any(t.lower() == f.title.lower() for t in dropped)]
    missed = [f.title for f in extra
              if not any(t.lower() == f.title.lower() for t in m.films)
              and f.title not in thin]

    if len(lineup) < 2:
        raise HTTPException(422, "The lineup needs at least two titles.")

    notes = _candidate_notes(here, missed, thin,
                             ENTITY_LABEL.get(kind, "titles"), kind)
    if len(pool) < slots + 1:
        left = len(pool)
        leaves = (f"That leaves {spell_count(left)} "
                  f"{'title' if left == 1 else 'titles'}. " if notes else "")
        raise Refused(422, " ".join(notes + [
            leaves + f"Room for {slots} requires at least "
            f"{spell_count(slots + 1)} titles to compare."]))

    got = _choose_best(m, lineup, pool, slots)
    if got is None:
        raise HTTPException(422, "Nothing to choose between.")

    full = lineup + got["best"]["films"]
    small = _subset(m, full)
    got["notes"] = notes
    got["unplaced"] = missed
    got["noun"], got["nouns"] = ENTITY_NOUN.get(kind, ("item", "items"))
    got["shape"] = _shape_from("Your lineup", "", small, "choose", [], kind,
                               stability=False)[0]
    return got


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
                         entity_type=shape["entity_type"],
                         locked=req.locked)
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


CANDIDATES = ROOT / "data" / "candidates"


@app.get("/api/candidates")
def candidates(kind: str):
    if kind not in ENTITY_LABEL:
        raise HTTPException(422, "Unknown type.")
    path = CANDIDATES / f"{kind.rsplit(':', 1)[1]}.json"
    if not path.exists():
        return {"one": [], "many": []}
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/examples")
def examples():
    out = []
    for path in sorted(EXAMPLES.glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        out.append({
            "slug": path.stem,
            "name": d["name"],
            "entity_type": d["entity_type"],
            "titles": [f["title"] + (f" ({f['year']})" if f.get("year") else "")
                       for f in d["films"]],
        })
    return {"examples": out}


AUDIENCE_SAMPLES = ("taste_survey.csv", "audience_preferences.csv")


@app.get("/api/examples/audience/{name}")
def audience_example(name: str):
    if name not in AUDIENCE_SAMPLES:
        raise HTTPException(404, "No such example.")
    path = EXAMPLES / name
    if not path.exists():
        raise HTTPException(404, "No such example.")
    return PlainTextResponse(path.read_text(encoding="utf-8"),
                             media_type="text/csv")


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
        "slots": d.get("slots"),
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


SPELT = ["zero", "one", "two", "three", "four", "five", "six", "seven",
         "eight", "nine", "ten"]


def spell_count(n: int) -> str:
    return SPELT[n] if 0 <= n < len(SPELT) else str(n)


def _tidy(title: str) -> str:
    return title.strip().rstrip(".,;:").strip() or title.strip()


def _year_hint(entity_type: str) -> str:
    if entity_type in ("urn:entity:movie", "urn:entity:tv_show"):
        return " Check the spelling, or add a year in brackets, like " \
               "Monster (2023)."
    return " Check the spelling, or try another title."


def _nameList(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def _candidate_notes(here: list[str], missed: list[str], thin: list[str],
                     kind: str, entity_type: str = "") -> list[str]:
    said = []
    if here:
        said.append(_nameList(here) + (" are" if len(here) > 1 else " is")
                    + " already in this lineup.")
    if missed:
        said.append(f"Slate could not find {_nameList(missed)} among "
                    f"{kind}." + _year_hint(entity_type))
    if thin:
        said.append(f"Qloo has {_nameList(thin)} but no data linking "
                    + ("them" if len(thin) > 1 else "it")
                    + " to this lineup.")
    return said


class _Named:
    def __init__(self, name, kind, liked, quote, row, question):
        self.name = name
        self.kind = kind
        self.liked = liked
        self.quote = quote
        self.row = row
        self.question = question


def _ref_out(ref) -> dict:
    return {
        "title": ref.title,
        "entity_type": ref.entity_type,
        "entity_id": ref.entity_id,
        "weight": ref.weight,
        "disliked": ref.disliked,
        "sources": ref.sources[:6],
    }


@app.post("/api/audience/read")
def audience_read(req: AudienceRead, request: Request):
    if _over_limit(request, "audience", PANEL_PER_HOUR):
        raise HTTPException(429, "Hourly limit reached.")

    kind = req.kind
    if kind not in (SURVEY, PREFERENCES, DESCRIPTION):
        guess = sniff(req.text)
        if not guess:
            raise HTTPException(422, "That file is neither a survey nor a "
                                     "preferences file. A survey needs "
                                     "question and response; a preferences "
                                     "file needs name, liked_count and "
                                     "disliked_count.")
        kind = guess

    try:
        source = read_source(kind, req.text, req.filename)
    except BadSource as exc:
        where = f" (row {exc.row})" if exc.row else ""
        raise HTTPException(422, exc.detail + where) from exc

    source.synthetic = req.synthetic

    try:
        if kind == DESCRIPTION:
            found = from_description(source.description)
            counts = None
        elif kind == SURVEY:
            found = from_answers(source.answers)
            counts = None
        else:
            proposed = kinds_for([c.name for c in source.counted])
            found = [_Named(c.name, proposed.get(c.name), True, "", c.row, "")
                     for c in source.counted]
            counts = {c.name.casefold(): {"liked": c.liked,
                                          "disliked": c.disliked}
                      for c in source.counted}
    except ExtractFailed as exc:
        raise HTTPException(503, str(exc)) from exc

    if not found:
        raise HTTPException(422, "Nothing in that names a film, artist, "
                                 "book, podcast or TV show, so there is no "
                                 "audience to build for. Add what they like "
                                 "by name.")

    try:
        review = resolve_refs(Qloo(), found, counts)
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc

    if not review.usable:
        raise HTTPException(422, "None of those names could be matched to "
                                 "Qloo's catalogue, so there is no "
                                 "audience to build for.")

    grouped = by_kind(review.references)
    return {
        "kind": kind,
        "filename": source.filename,
        "synthetic": source.synthetic,
        "skipped": source.skipped,
        "groups": [{
            "entity_type": entity_type,
            "label": ENTITY_LABEL.get(entity_type, "titles"),
            "references": [_ref_out(r) for r in refs],
        } for entity_type, refs in grouped.items()],
        "unresolved": [{"name": u.name, "why": u.why, "quotes": u.quotes}
                       for u in review.unresolved],
        "negative_only": [{"name": u.name, "why": u.why, "quotes": u.quotes}
                          for u in review.negative_only],
        "count": len(review.references),
    }


class AudienceCandidates(BaseModel):
    candidates: list[str]


@app.post("/api/audience/candidates")
def audience_candidates(req: AudienceCandidates, request: Request):
    if _over_limit(request, "audience", PANEL_PER_HOUR):
        raise HTTPException(429, "Hourly limit reached.")

    wanted = _films_from_lines([t for t in req.candidates if t.strip()])
    if len(wanted) < MIN_FILMS:
        raise HTTPException(422, f"Give Slate at least {MIN_FILMS} "
                                 "candidates.")
    if len(wanted) > MAX_CANDIDATES:
        raise HTTPException(422, f"{MAX_CANDIDATES} candidates at most.")

    qloo = Qloo()
    claimed: dict[str, str] = {}
    by_kind: dict[str, list[dict]] = {}
    try:
        for kind in ENTITY_LABEL:
            resolved, _ = resolve_all(qloo, wanted, kind)
            for title, got in resolved.items():
                if title in claimed:
                    continue
                claimed[title] = kind
                by_kind.setdefault(kind, []).append({
                    "title": title,
                    "year": getattr(got, "qloo_year", None),
                })
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc

    if not by_kind:
        raise HTTPException(422, "None of those candidates could be matched "
                                 "to Qloo's catalogue.")

    return {
        "kinds": [{
            "entity_type": kind,
            "label": ENTITY_LABEL[kind],
            "titles": titles,
            "enough": len(titles) >= MIN_FILMS,
        } for kind, titles in by_kind.items()],
        "missing": [f.title for f in wanted if f.title not in claimed],
    }


@app.post("/api/audience/build")
def audience_build(req: AudienceBuild, request: Request):
    if _over_limit(request, "audience", PANEL_PER_HOUR):
        raise HTTPException(429, "Hourly limit reached.")

    if req.mode not in MODES:
        raise HTTPException(422, "Pick Balanced or Demand-led.")
    if req.entity_type not in ENTITY_LABEL:
        raise HTTPException(422, "Pick what Slate should select.")

    refs = [Reference(title=r.get("title", ""),
                      entity_type=r.get("entity_type", ""),
                      entity_id=r.get("entity_id", ""),
                      weight=float(r.get("weight") or 1.0),
                      disliked=int(r.get("disliked") or 0),
                      sources=list(r.get("sources") or []))
            for r in req.references if r.get("entity_id")]
    if not refs:
        raise HTTPException(422, "Confirm at least one audience reference.")

    wanted = _films_from_lines([t for t in req.candidates if t.strip()])
    if len(wanted) < req.slots:
        raise HTTPException(422, f"{len(wanted)} candidates cannot fill "
                                 f"{req.slots} slots.")
    if not MIN_FILMS <= req.slots <= MAX_FILMS:
        raise HTTPException(422, f"Slate selects between {MIN_FILMS} and "
                                 f"{MAX_FILMS} titles.")

    try:
        pool, missed = resolve_all(Qloo(), wanted, req.entity_type)
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc

    titles = list(pool)
    if len(titles) < req.slots:
        kind = ENTITY_LABEL.get(req.entity_type, "titles")
        raise HTTPException(422, f"Only {len(titles)} of those candidates "
                                 f"could be found among {kind}, which "
                                 f"cannot fill {req.slots} slots.")

    locked = [t for t in titles
              if any(t.casefold() == w.casefold() for w in req.locked)]
    unknown = [w for w in req.locked
               if not any(t.casefold() == w.casefold() for t in titles)]
    if unknown:
        raise HTTPException(422, f"{_nameList(unknown)} cannot be required, "
                                 "because it is not among the candidates "
                                 "Slate found.")
    if len(locked) > req.slots:
        raise HTTPException(422, f"{len(locked)} titles are required but "
                                 f"there are only {req.slots} slots.")

    ids = {pool[t].entity_id: t for t in titles}
    rankings = {}
    try:
        for ref in refs:
            rows = Qloo().rank_within(ref.entity_id, list(ids),
                                      req.entity_type)
            order = [ids[id_of(r)] for r in rows if id_of(r) in ids]
            if order:
                rankings[ref.title] = order
    except QlooError as exc:
        raise HTTPException(503, str(exc)) from exc

    refs = [r for r in refs if r.title in rankings]
    if not refs:
        raise HTTPException(422, "Qloo could not relate any of those "
                                 "references to these candidates, so there "
                                 "is nothing to select on.")

    try:
        got = select(titles, refs, rankings, req.slots, req.mode, locked)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    audience = dict(req.audience or {})
    audience.update({
        "mode": req.mode,
        "references": [_ref_out(r) for r in refs],
        "candidates": titles,
        "locked": locked,
        "unresolved_candidates": missed,
        "served": got["served"],
        "how": got["how"],
        "score": got["score"],
        "weakest": got["weakest"],
        "slots": req.slots,
    })

    name = (req.name or got["chosen"][0])[:120]
    return store.create(_owner(req.owner), name, got["chosen"],
                        req.entity_type, slots=req.slots,
                        audience=audience, locked=locked)


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


@app.get("/app")
def workbench():
    return FileResponse(STATIC / "app.html")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
