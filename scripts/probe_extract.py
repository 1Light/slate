                      
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.extract import (ExtractFailed, from_answers,               
                         from_description)
from app.ingest import read_preferences, read_survey                
from app.qloo import Qloo                                           
from app.references import resolve                                  

EXAMPLES = Path(__file__).resolve().parent.parent / "data" / "examples"


class _Row:
    def __init__(self, name):
        self.name = name
        self.kind = None
        self.liked = True
        self.quote = ""
        self.row = None
        self.question = ""

EMPTY = ("Our members are mostly young professionals in their thirties "
         "with high disposable income. They travel often and care about "
         "design.")

NAMED = ("They are the sort of people who still talk about Arrival years "
         "later, listen to a lot of Radiohead, and could not get on with "
         "Dune at all.")


def show(title, found):
    print(f"\n{title}")
    if not found:
        print("  nothing found")
        return
    for item in found:
        kind = item.kind.split(":")[-1] if item.kind else "unsure"
        mark = "+" if item.liked else "-"
        where = f" row {item.row}" if item.row else ""
        print(f"  {mark} {item.name:<24} {kind:<10}{where}")
        if item.quote:
            print(f"      \u201c{item.quote[:70]}\u201d")


def main() -> int:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("DEEPSEEK_API_KEY is not set.")
        return 2

    try:
        print("=" * 70)
        print("A description naming nothing")
        print("=" * 70)
        found = from_description(EMPTY)
        show("result", found)
        if found:
            print("\n  PROBLEM: names were invented from demographics.")
        else:
            print("\n  Correct: nothing was named, so nothing was found.")

        print("\n" + "=" * 70)
        print("A description naming three things, one disliked")
        print("=" * 70)
        found = from_description(NAMED)
        show("result", found)
        dune = [f for f in found if f.name.lower() == "dune"]
        if dune and dune[0].liked:
            print("\n  PROBLEM: Dune was disliked and came back positive.")

        print("\n" + "=" * 70)
        print("The survey file, nineteen answers")
        print("=" * 70)
        survey = read_survey(
            (EXAMPLES / "taste_survey.csv").read_text(encoding="utf-8"),
            "taste_survey.csv")
        found = from_answers(survey.answers)
        show(f"{len(found)} names from {len(survey.answers)} answers", found)

        unsure = [f for f in found if not f.kind]
        print(f"\n  {len(unsure)} unsure of kind"
              + (f": {', '.join(f.name for f in unsure)}" if unsure else ""))

        print("\n  resolving against Qloo")
        review = resolve(Qloo(), found)
        print(f"  {len(review.references)} references, "
              f"{len(review.unresolved)} unresolved, "
              f"{len(review.negative_only)} negative only")
        for ref in review.references:
            print(f"    {ref.title:<28} weight {ref.weight:.0f}  "
                  f"{len(ref.sources)} sources")
        for item in review.unresolved:
            print(f"    unresolved: {item.name} \u2014 {item.why}")
        for item in review.negative_only:
            print(f"    negative:   {item.name}")

        print("\n" + "=" * 70)
        print("The aggregated file, resolved without the model")
        print("=" * 70)
        counted = read_preferences(
            (EXAMPLES / "audience_preferences.csv").read_text(encoding="utf-8"),
            "audience_preferences.csv")
        review = resolve(Qloo(), [_Row(c.name) for c in counted.counted],
                         {c.name.casefold(): {"liked": c.liked,
                                              "disliked": c.disliked}
                          for c in counted.counted})
        print(f"  {len(review.references)} resolved, "
              f"{len(review.unresolved)} unresolved")
        for ref in review.references:
            print(f"    {ref.title:<28} "
                  f"{ref.entity_type.split(':')[-1]:<10} "
                  f"weight {ref.weight:.0f}")
        for item in review.unresolved:
            print(f"    unresolved: {item.name} \u2014 {item.why}")

    except ExtractFailed as exc:
        print(f"\nthe model failed: {exc}")
        return 1

    print("\n" + "=" * 70)
    print("Check by eye: every name above should be in the source, every")
    print("dislike should be marked negative, and the survey's kinds")
    print("should follow its questions rather than the model's hunch.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
