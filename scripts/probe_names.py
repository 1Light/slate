                      
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.build import ENTITY_LABEL, _films_from_lines               
from app.qloo import Qloo                                           
from app.resolve import resolve_film                                

TYPES = list(ENTITY_LABEL)


SHORT = {"movie": "urn:entity:movie", "artist": "urn:entity:artist",
         "book": "urn:entity:book", "podcast": "urn:entity:podcast",
         "tv_show": "urn:entity:tv_show"}


def pinned(pairs: list[str]) -> int:
    qloo = Qloo()
    good, bad = [], []
    print(f"asking Qloo about {len(pairs)} names, one type each\n")
    for pair in pairs:
        if "=" not in pair:
            print(f"  {pair}: needs name=type")
            return 2
        raw, short = pair.rsplit("=", 1)
        kind = SHORT.get(short.strip())
        if not kind:
            print(f"  {pair}: type must be one of {', '.join(SHORT)}")
            return 2
        film = _films_from_lines([raw.strip()])[0]
        got = resolve_film(qloo, film, kind)
        label = ENTITY_LABEL[kind]
        if got:
            good.append(raw.strip())
            year = f" ({got.qloo_year})" if got.qloo_year else ""
            print(f"  {raw.strip():<28} {label:<16} {got.qloo_name}{year}")
        else:
            bad.append(f"{raw.strip()} as {label}")
            print(f"  {raw.strip():<28} {label:<16} nothing")

    print("\n" + "=" * 70)
    print(f"{len(good)} resolve, {len(bad)} do not.")
    if bad:
        print("\nDo not use:")
        for item in bad:
            print(f"  {item}")
    print("=" * 70)
    return 1 if bad else 0


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--pinned":
        return pinned(args[1:])
    if args and args[0] == "--file":
        names = [ln.strip() for ln in Path(args[1]).read_text().splitlines()
                 if ln.strip()]
    elif args:
        names = args
    else:
        print(__doc__)
        return 2

    qloo = Qloo()
    films = _films_from_lines(names)
    print(f"asking Qloo about {len(films)} names across "
          f"{len(TYPES)} types\n")

    clean, ambiguous, missing = [], [], []
    for film in films:
        hits = {}
        for kind in TYPES:
            got = resolve_film(qloo, film, kind)
            if got:
                hits[kind] = got

        if not hits:
            missing.append(film.title)
            print(f"  {film.title:<32} nothing")
            continue

        shown = ", ".join(
            f"{ENTITY_LABEL[k]}: {v.qloo_name}"
            + (f" ({v.qloo_year})" if v.qloo_year else "")
            + f" [{v.score}]"
            for k, v in sorted(hits.items(),
                               key=lambda kv: -kv[1].score))
        if len(hits) == 1:
            clean.append((film.title, next(iter(hits))))
            print(f"  {film.title:<32} {shown}")
        else:
            ambiguous.append((film.title, list(hits)))
            print(f"  {film.title:<32} {shown}   <- several types")

    print("\n" + "=" * 70)
    print(f"{len(clean)} resolve as exactly one type, "
          f"{len(ambiguous)} as several, {len(missing)} not at all.")
    if clean:
        by_kind: dict[str, list[str]] = {}
        for title, kind in clean:
            by_kind.setdefault(kind, []).append(title)
        print("\nSafe to use, by type:")
        for kind, titles in by_kind.items():
            print(f"  {ENTITY_LABEL[kind]}: {', '.join(titles)}")
    if ambiguous:
        print("\nNeed a year in brackets, or avoid:")
        for title, kinds in ambiguous:
            print(f"  {title}: {', '.join(ENTITY_LABEL[k] for k in kinds)}")
    if missing:
        print("\nDo not use:")
        for title in missing:
            print(f"  {title}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
