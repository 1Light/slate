from __future__ import annotations

from pathlib import Path


def test_workspaces_belong_to_one_browser():
    src = (Path(__file__).resolve().parent.parent / "app" / "store.py").read_text()
    import ast as _ast
    tree = _ast.parse(src)
    for fn in ("listing", "read", "update", "remove", "add_version"):
        node = next(n for n in tree.body
                    if isinstance(n, _ast.FunctionDef) and n.name == fn)
        assert "owner" in [a.arg for a in node.args.args], fn
    assert "WHERE owner = %s AND id = %s" in src


def test_the_store_runs_without_postgres():
    src = (Path(__file__).resolve().parent.parent / "app" / "store.py").read_text()
    assert "import sqlite3" in src
    assert "DATABASE_URL" in src
    block = src[src.index("def _pg("):src.index("def _lite(")]
    assert "except ImportError" in block, "a missing driver falls back"


def test_a_browser_id_is_checked():
    src = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text()
    block = src[src.index("def _owner("):src.index("@app.get(\"/api/spaces\")")]
    assert "isalnum()" in block
    assert "[:64]" in block
    assert "len(clean) < 8" in block


def test_versions_are_capped():
    src = (Path(__file__).resolve().parent.parent / "app" / "store.py").read_text()
    assert "MAX_VERSIONS = 20" in src
    block = src[src.index("def add_version("):src.index("def remove(")]
    assert "kept[0].get(\"titles\") == titles" in block, "no duplicate saves"
    assert "[:MAX_VERSIONS]" in block


def test_an_old_database_still_opens():
    import json as _json, sqlite3 as _sql, tempfile, time as _t
    import app.store as store
    folder = Path(tempfile.mkdtemp())
    db = folder / "old.db"
    con = _sql.connect(db)
    con.execute("CREATE TABLE workspaces (id TEXT PRIMARY KEY, owner TEXT "
                "NOT NULL, name TEXT NOT NULL, entity_type TEXT NOT NULL, "
                "slots INTEGER NOT NULL, titles TEXT NOT NULL, versions "
                "TEXT NOT NULL, touched REAL NOT NULL)")
    con.execute("INSERT INTO workspaces VALUES (?,?,?,?,?,?,?,?)",
                ("old1", "someone", "Made earlier", "urn:entity:movie", 5,
                 _json.dumps(list("ABCDE")), _json.dumps([]), _t.time()))
    con.commit()
    con.close()

    was = store._SQLITE
    try:
        store._SQLITE = db
        rows = store.listing("someone")
        assert rows and rows[0]["placed"] is None
        assert len(rows[0]["titles"]) == 5
        store.update("someone", "old1", placed=4)
        assert store.listing("someone")[0]["placed"] == 4
        store._lite()
    finally:
        store._SQLITE = was


def test_locks_survive_and_clean_themselves():
    import tempfile
    import app.store as store
    was = store._SQLITE
    try:
        store._SQLITE = Path(tempfile.mkdtemp()) / "l.db"
        made = store.create("me", "T", ["A", "B", "C", "D"],
                            "urn:entity:movie", locked=["A", "nope"])
        assert made["locked"] == ["A"], "a lock outside the lineup is dropped"
        store.update("me", made["id"], locked=["A", "B"])
        assert store.read("me", made["id"])["locked"] == ["A", "B"]
        store.update("me", made["id"], titles=["B", "C", "D"])
        assert store.read("me", made["id"])["locked"] == ["B"], (
            "removing a title removes its lock")
    finally:
        store._SQLITE = was
