from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

SURVEY = "survey_csv"
PREFERENCES = "preference_csv"
DESCRIPTION = "description"

SURVEY_COLUMNS = ("question", "response")
PREFERENCE_COLUMNS = ("name", "liked_count", "disliked_count")

MAX_ROWS = 400
MAX_BYTES = 512_000
MAX_DESCRIPTION = 4_000


def _rows_failed(rows: list[int], filename: str, needs: str) -> str:
    where = filename or "that file"
    if len(rows) == 1:
        return (f"Row {rows[0]} of {where} could not be read. Check that "
                f"each row has {needs}.")
    listed = (f"{', '.join(str(r) for r in rows[:-1])} and {rows[-1]}"
              if len(rows) > 2 else f"{rows[0]} and {rows[1]}")
    return (f"{len(rows)} rows in {where} could not be read: rows "
            f"{listed}. Check that each row has {needs}.")


class BadSource(Exception):

    def __init__(self, detail: str, row: int | None = None):
        super().__init__(detail)
        self.detail = detail
        self.row = row


@dataclass
class Answer:

    row: int
    question: str
    response: str


@dataclass
class Counted:

    row: int
    name: str
    liked: int
    disliked: int


@dataclass
class Source:
    kind: str
    filename: str = ""
    answers: list[Answer] = field(default_factory=list)
    counted: list[Counted] = field(default_factory=list)
    description: str = ""
    skipped: list[str] = field(default_factory=list)
    synthetic: bool = False

    @property
    def empty(self) -> bool:
        return not (self.answers or self.counted or self.description.strip())


def _rows(text: str) -> list[dict]:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise BadSource(f"That file is larger than "
                        f"{MAX_BYTES // 1000} kB.")
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except csv.Error as exc:
        raise BadSource(f"That file could not be read as CSV: {exc}") from exc
    if not rows:
        raise BadSource("That file has a header but no rows.")
    if len(rows) > MAX_ROWS:
        raise BadSource(f"That file has {len(rows)} rows. "
                        f"{MAX_ROWS} is the most Slate reads at once.")
    return rows


def _headers(rows: list[dict], needed: tuple[str, ...], kind: str) -> None:
    have = {(h or "").strip().lower() for h in rows[0]}
    missing = [c for c in needed if c not in have]
    if missing:
        raise BadSource(
            f"A {kind} needs {' and '.join(needed)}. "
            f"Missing: {', '.join(missing)}.")


def _get(row: dict, column: str) -> str:
    for key, value in row.items():
        if (key or "").strip().lower() == column:
            return (value or "").strip()
    return ""


def read_survey(text: str, filename: str = "") -> Source:
    rows = _rows(text)
    _headers(rows, SURVEY_COLUMNS, "survey")

    out = Source(kind=SURVEY, filename=filename)
    for n, row in enumerate(rows, 2):
        question = _get(row, "question")
        response = _get(row, "response")
        if not response:
            out.skipped.append(f"row {n}: no response")
            continue
        if not question:
            out.skipped.append(f"row {n}: no question, so the answer "
                               "cannot be read")
            continue
        out.answers.append(Answer(row=n, question=question,
                                  response=response))
    if not out.answers:
        raise BadSource("No row in that file has both a question and a "
                        "response.")
    return out


def read_preferences(text: str, filename: str = "") -> Source:
    rows = _rows(text)
    _headers(rows, PREFERENCE_COLUMNS, "preferences file")

    out = Source(kind=PREFERENCES, filename=filename)
    seen: dict[str, Counted] = {}
    bad: list[int] = []
    for n, row in enumerate(rows, 2):
        name = _get(row, "name")
        if not name:
            bad.append(n)
            continue

        counts = {}
        for column in ("liked_count", "disliked_count"):
            raw = _get(row, column)
            try:
                value = int(raw)
            except ValueError:
                value = -1
            if value < 0:
                counts = None
                break
            counts[column] = value
        if counts is None:
            bad.append(n)
            continue

        key = name.casefold()
        if key in seen:
            was = seen[key]
            was.liked += counts["liked_count"]
            was.disliked += counts["disliked_count"]
            out.skipped.append(f"row {n}: {name} appears again, "
                               "counts added to the earlier row")
            continue
        got = Counted(row=n, name=name, liked=counts["liked_count"],
                      disliked=counts["disliked_count"])
        seen[key] = got
        out.counted.append(got)

    if bad:
        raise BadSource(_rows_failed(bad, filename, "a name, and that "
                                     "liked_count and disliked_count are "
                                     "whole numbers"))
    if not out.counted:
        raise BadSource("No row in that file has a name.")
    if all(c.liked == 0 for c in out.counted):
        raise BadSource("Nothing in that file has a positive response, so "
                        "there is no audience to build for.")
    return out


def read_description(text: str) -> Source:
    text = (text or "").strip()
    if not text:
        raise BadSource("Describe the audience first.")
    if len(text) > MAX_DESCRIPTION:
        raise BadSource(f"That description is longer than "
                        f"{MAX_DESCRIPTION} characters.")
    return Source(kind=DESCRIPTION, description=text)


def read(kind: str, text: str, filename: str = "") -> Source:
    if kind == SURVEY:
        return read_survey(text, filename)
    if kind == PREFERENCES:
        return read_preferences(text, filename)
    if kind == DESCRIPTION:
        return read_description(text)
    raise BadSource(f"Unknown source kind: {kind}")


def sniff(text: str) -> str | None:
    try:
        first = next(csv.reader(io.StringIO(text)))
    except (csv.Error, StopIteration):
        return None
    have = {(h or "").strip().lower() for h in first}
    if all(c in have for c in SURVEY_COLUMNS):
        return SURVEY
    if all(c in have for c in PREFERENCE_COLUMNS):
        return PREFERENCES
    return None
