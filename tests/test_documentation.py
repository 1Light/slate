from __future__ import annotations

from pathlib import Path


def test_the_readme_is_committed():
    root = Path(__file__).resolve().parent.parent
    assert (root / "README.md").exists()
    assert (root / "LICENSE").exists(), "an open source licence is required"
    ignore = (root / ".gitignore").read_text()
    assert "!README.md" not in ignore and "*.md" not in ignore


def test_the_readme_points_at_things_that_exist():
    root = Path(__file__).resolve().parent.parent
    text = (root / "README.md").read_text()
    assert "docs/figure.png" in text
    import re
    for name in re.findall(r"scripts/(probe_\w+\.py|warm_cache\.py)", text):
        assert (root / "scripts" / name).exists(), name
    assert text.rstrip().endswith("MIT. See [LICENSE](LICENSE).")


def test_the_readme_claims_only_what_was_measured():
    text = (Path(__file__).resolve().parent.parent / "README.md").read_text()
    flat = " ".join(text.split())
    for claim in ("0.35", "0.24", "\u22120.650", "+0.251", "\u22120.498"):
        assert claim in flat, claim
    assert "Honest limits" in text
    assert "not attendance" in flat
    assert "inferences from taste relationships" in flat


def test_the_ignore_rules_match_the_project():
    root = Path(__file__).resolve().parent.parent
    rules = (root / ".gitignore").read_text()
    assert "*.md" not in rules
    for gone in ("slate_setup.sh", "apply.sh", "search_*.json"):
        assert gone not in rules, gone
    for needed in (".env", "data/cache/", "data/ml-32m/", "data/slate.db",
                   "__pycache__/", ".venv/"):
        assert needed in rules, needed
