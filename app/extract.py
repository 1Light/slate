from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

API = os.environ.get("DEEPSEEK_URL",
                     "https://api.deepseek.com/chat/completions")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
TIMEOUT = float(os.environ.get("DEEPSEEK_TIMEOUT", "60"))

KINDS = {
    "film": "urn:entity:movie",
    "tv_show": "urn:entity:tv_show",
    "artist": "urn:entity:artist",
    "book": "urn:entity:book",
    "podcast": "urn:entity:podcast",
}

MAX_NAMES = 120

SYSTEM = """You read what people wrote about what they enjoy and list the \
named works they mention. You do not add anything that is not there.

Return only JSON, no prose and no markdown fences, shaped like:

{"found": [{"name": "...", "kind": "...", "liked": true, "quote": "..."}]}

name   exactly as written, without surrounding words
kind   one of film, tv_show, artist, book, podcast, or unsure
liked  true if the writer was positive about it, false if negative
quote  the shortest span of the original text that supports this

Rules.

Only list works actually named. "Young professionals who travel a lot" \
names nothing, so return {"found": []}.

Where a question is given, it usually settles the kind. "Which artists do \
you like?" means an artist, even for a name that could be something else. \
Prefer the question over your own recognition of the name.

Where nothing settles it and the name could plausibly be several kinds, \
use "unsure". Do not guess to avoid an empty field.

A name mentioned negatively still goes in the list, with liked false. Do \
not leave it out and do not mark it liked.

The same name mentioned twice goes in twice, once per mention.

Do not translate, correct spelling, or expand abbreviations. Return the \
name as written."""


@dataclass
class Found:

    name: str
    kind: str | None
    liked: bool
    quote: str
    row: int | None = None
    question: str = ""


class ExtractFailed(Exception):
    pass


def _key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise ExtractFailed("No DEEPSEEK_API_KEY is set, so free text "
                            "cannot be read.")
    return key


def _call(user: str, system: str = "") -> str:
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system or SYSTEM},
                     {"role": "user", "content": user}],
        "temperature": 0,
        "stream": False,
    }).encode("utf-8")
    request = urllib.request.Request(
        API, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {_key()}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:
            got = json.loads(answer.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ExtractFailed(f"The model refused the request "
                            f"({exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ExtractFailed("The model could not be reached.") from exc
    except json.JSONDecodeError as exc:
        raise ExtractFailed("The model's reply was not JSON.") from exc

    try:
        return got["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise ExtractFailed("The model's reply had no content.") from exc


def _parse(text: str, key: str = "found") -> list[dict]:
    text = (text or "").strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        got = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractFailed("The model's reply was not JSON.") from exc
    rows = got.get(key) if isinstance(got, dict) else got
    if not isinstance(rows, list):
        raise ExtractFailed("The model's reply was not a list of names.")
    return rows


def _clean(rows: list[dict], *, row: int | None = None,
           question: str = "", within: str = "") -> list[Found]:
    out = []
    haystack = (within or "").casefold()
    for item in rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or len(name) > 200:
            continue
        if haystack and name.casefold() not in haystack:
            continue
        kind = str(item.get("kind") or "").strip().lower()
        out.append(Found(
            name=name,
            kind=KINDS.get(kind),
            liked=bool(item.get("liked", True)),
            quote=str(item.get("quote") or "")[:300],
            row=row,
            question=question,
        ))
    return out


def from_description(text: str) -> list[Found]:
    said = _call(f"Text:\n{text}")
    return _clean(_parse(said), within=text)[:MAX_NAMES]


def from_answers(answers: list) -> list[Found]:
    if not answers:
        return []
    lines = [f"{a.row}. Question: {a.question}\n   Answer: {a.response}"
             for a in answers]
    said = _call("Each numbered item is one survey answer. Read the "
                 "question and the answer together. Add the item number "
                 "to each result as \"row\".\n\n" + "\n".join(lines))

    by_row = {a.row: a for a in answers}
    out = []
    for item in _parse(said):
        if not isinstance(item, dict):
            continue
        try:
            row = int(item.get("row"))
        except (TypeError, ValueError):
            row = None
        source = by_row.get(row)
        got = _clean([item], row=row,
                     question=source.question if source else "",
                     within=source.response if source else "")
        out.extend(got)
    return out[:MAX_NAMES]


TYPES = """You are told the names of films, music artists, books, podcasts \
and TV shows. For each one, say which kind it is.

Reply with JSON only, no preamble and no markdown:
{"kinds": [{"name": "...", "kind": "film"}]}

kind must be one of: film, tv_show, artist, book, podcast, unsure.

Copy each name back exactly as it was given.
Use "unsure" only when the name genuinely could be several kinds and \
nothing lets you tell. Prefer the best-known work of that name."""


def kinds_for(names: list[str]) -> dict[str, str | None]:
    if not names:
        return {}
    said = _call("\n".join(names[:MAX_NAMES]), system=TYPES)
    by_name = {n.casefold(): n for n in names}
    out: dict[str, str | None] = {}
    for item in _parse(said, key="kinds"):
        if not isinstance(item, dict):
            continue
        given = by_name.get(str(item.get("name", "")).strip().casefold())
        if not given:
            continue
        out[given] = KINDS.get(item.get("kind"))
    return out
