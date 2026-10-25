from __future__ import annotations

import html
from datetime import date

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def letter(i) -> str:
    try:
        return LETTERS[int(i)]
    except (TypeError, ValueError, IndexError):
        return "?"


def _(text) -> str:
    return html.escape(str(text if text is not None else ""))


def _when() -> str:
    today = date.today()
    return f"{today.day} {today.strftime('%B')} {today.year}"


CSS = """
@page { size: A4; margin: 20mm 18mm; }
body { font: 11pt/1.55 Georgia, 'Times New Roman', serif; color: #1a1a1a;
  max-width: 170mm; margin: 0 auto; }
h1 { font-size: 20pt; line-height: 1.15; margin: 0 0 2px; font-weight: normal; }
.sub { color: #555; font-size: 9.5pt; margin: 0 0 9mm; }
h2 { font-size: 9.5pt; margin: 6mm 0 1.5mm; text-transform: uppercase;
  letter-spacing: 0.08em; font-weight: normal; color: #777; }
p { margin: 0 0 2.5mm; }
table { border-collapse: collapse; width: 100%; margin: 1mm 0 4mm;
  font-size: 10pt; break-inside: avoid; }
td { padding: 1.2mm 2mm 1.2mm 0; }
.rule td { border-bottom: 0.3pt solid #ddd; }
td.n { text-align: right; width: 20mm; font-variant-numeric: tabular-nums; }
td.g { padding-left: 6mm; color: #777; width: 22mm; }
.groups td { vertical-align: top; }
.groups .k { width: 7mm; }
.groups .c { width: 18mm; color: #777; font-size: 9.5pt; }
.note { font-size: 8.5pt; color: #666; line-height: 1.5; }
footer { margin-top: 8mm; padding-top: 2.5mm; border-top: 0.3pt solid #ccc;
  font-size: 8pt; color: #777; }
"""

METHOD = (
    "<h2>Method and limits</h2>"
    "<p class=\"note\">Distance between two titles is built from Qloo&rsquo;s "
    "affinity rankings: each title is asked about, the positions it gives the "
    "others are recorded, and the two directions are averaged. Groups are "
    "found by agglomerative clustering, with the number chosen by silhouette "
    "score. Sets are compared by how far apart their two most alike titles "
    "sit, then by the next closest pair where that ties.</p>"
    "<p class=\"note\">A group describes this lineup and nothing beyond it. "
    "Take four of these titles and run them alone and they will separate "
    "again. Distance measures shared taste, not attendance, revenue or the "
    "number of people reached, and it says nothing about whether a programme "
    "will select a title.</p>"
)


def _groups(clusters, nouns, mark=None, skip=None) -> str:
    mark, skip = set(mark or []), set(skip or [])
    rows = []
    for i, group in enumerate(clusters):
        names = [t for t in (list(group.get("films") or group.get("titles")
                                   or []) if isinstance(group, dict)
                             else list(group)) if t not in skip]
        if not names:
            continue
        titles = " &middot; ".join(
            f"<i>{_(t)}</i>" if t in mark else _(t) for t in names)
        rows.append(
            f'<tr class="rule"><td class="k">{letter(i)}</td>'
            f'<td class="c">{len(names)} {_(nouns)}</td>'
            f"<td>{titles}</td></tr>")
    return f'<table class="groups">{"".join(rows)}</table>'


def page(title: str, sub: str, guts: str) -> str:
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{_(title)}</title><style>{CSS}</style></head><body>"
        f"<h1>{_(title)}</h1><p class=\"sub\">{_(sub)}</p>"
        f"{guts}{METHOD}"
        f"<footer>Slate &middot; built on Qloo &middot; {_when()}</footer>"
        "</body></html>")


def lineup_doc(shape: dict, name: str, slots: int | None) -> str:
    films = shape.get("films", [])
    clusters = shape.get("clusters", [])
    noun, nouns = shape.get("noun", "item"), shape.get("nouns", "items")
    n = len(films)

    bridges = shape.get("bridges") or []
    linked = {b["film"] for b in bridges}

    guts = (f"<p>These {n} {_(nouns)} separate into {len(clusters)} "
            "groups.</p>" + _groups(clusters, nouns, skip=linked))

    if bridges:
        rows = "".join(
            '<tr class="rule"><td class="k">'
            + " &middot; ".join(letter(x) for x in (b.get("connects") or []))
            + f'</td><td>{_(b["film"])}</td></tr>' for b in bridges)
        guts += ("<h2>Bridges</h2><p>Each bridge is close to titles in more "
                 "than one group, so it connects them instead of fitting "
                 "into just one.</p>"
                 f'<table class="groups">{rows}</table>')

    alone = shape.get("isolated") or []
    if alone:
        guts += ("<h2>What stands alone</h2><p>" + _(alone[0]["film"])
                 + " is an outlier. It covers taste nothing else here "
                 "covers.</p>")

    spare = [p for p in (shape.get("tightest") or [])
             if p["a"] not in linked and p["b"] not in linked][:3]
    if spare:
        rows = "".join(
            f'<tr class="rule"><td>{_(p["a"])} &nbsp;&middot;&nbsp; '
            f'{_(p["b"])}</td><td class="n">{p["distance"]:.1f}</td>'
            f'<td class="g">group {letter(p.get("cluster"))}</td></tr>'
            for p in spare)
        guts += ("<h2>Where a slot could be freed</h2>"
                 f"<table>{rows}</table>"
                 "<p class=\"note\">Each pair sits closer together than "
                 "anything else in its group, so dropping either one leaves "
                 "the other covering that ground.</p>")

    room = f" in {slots} slots" if slots else ""
    return page(name, f"{n} {nouns}{room} \u00b7 {_when()}", guts)


def stand_doc(brief: dict, name: str) -> str:
    c = brief["candidate"]
    who = c["film"]
    nouns = brief.get("nouns", "items")
    guts = _groups(brief.get("clusters", []), nouns, [who])

    before, after = brief["groups_before"], brief["groups_after"]
    if after == before:
        said = f"The number of groups stays at {before}."
    elif after < before:
        said = (f"The number of groups falls from {before} to {after}. It "
                "sits between groups that were separate before, closely "
                "enough that they merge.")
    else:
        said = f"The number of groups goes from {before} to {after}."
    guts += f"<h2>Changes to the lineup</h2><p>{said}</p>"

    if brief.get("role") == "bridge":
        joins = [letter(x) for x in (brief.get("connects") or [])]
        which = (f"group {joins[0]} and group {joins[1]}" if len(joins) == 2
                 else "groups " + ", ".join(joins[:-1]) + f" and {joins[-1]}")
        guts += (f"<h2>Its part in the lineup</h2><p>{_(who)} is a bridge. "
                 f"It connects {which}.</p>")
    elif brief.get("role") == "alone":
        guts += (f"<h2>Its part in the lineup</h2><p>{_(who)} is an outlier. "
                 "It sits further from the rest than anything else here.</p>")

    spare = brief.get("spare")
    if brief.get("over", 0) > 0 and spare:
        x, y = spare["films"]
        guts += (f"<h2>What it could replace</h2><p>{_(x)} or {_(y)} costs "
                 "least to drop. They are the two most alike titles in the "
                 "lineup, so whichever stays still covers that ground.</p>")

    rows = "".join(
        f'<tr class="rule"><td>{_(d["film"])}</td>'
        f'<td class="n">{d["distance"]:.1f}</td></tr>'
        for d in c.get("distances", []))
    guts += f"<h2>How far it sits from each title</h2><table>{rows}</table>"

    return page(f"{who} against {name}",
                f"A {len(c.get('distances', [])) + 1}-title lineup "
                f"\u00b7 {_when()}", guts)


def choose_doc(got: dict, name: str) -> str:
    best = got["best"]
    nouns = got.get("nouns", "items")
    guts = _groups(best.get("clusters", []), nouns, best["films"])

    names = best["films"]
    joined = (names[0] if len(names) == 1
              else " and ".join(names) if len(names) == 2
              else ", ".join(names[:-1]) + f" and {names[-1]}")
    guts += f"<h2>Which to take</h2><p>{_(joined)}.</p>"

    before, after = got["groups_before"], best["groups"]
    guts += ("<h2>Changes to the lineup</h2><p>"
             + (f"The number of groups stays at {before}."
                if after == before else
                f"The number of groups goes from {before} to {after}.")
             + "</p>")

    if got.get("next"):
        nxt = got["next"]["films"]
        guts += ("<h2>The next best set</h2><p>"
                 + _(" and ".join(nxt))
                 + ". Their two most alike titles sit closer together than "
                 "in the set above.</p>")

    rows = "".join(
        f'<tr class="rule"><td>{_(" + ".join(r["films"]))}</td>'
        f'<td class="n">{r["groups"]}</td>'
        f'<td class="n">{r["closest"]:.1f}</td></tr>'
        for r in got.get("every", []))
    guts += ('<h2>Every set, best first</h2><table>'
             '<tr class="rule"><td>Set</td><td class="n">Groups</td>'
             f'<td class="n">Closest pair</td></tr>{rows}</table>'
             '<p class="note">Each set was added to the lineup and the '
             'groups worked out again from scratch.</p>')

    return page(f"{got['slots']} of {got['from']} for {name}",
                f"A {len(got.get('every', []))}-way comparison \u00b7 {_when()}",
                guts)


def as_pdf(markup: str) -> bytes | None:
    try:
        from weasyprint import HTML
    except Exception:
        return None
    try:
        return HTML(string=markup).write_pdf()
    except Exception:
        return None
