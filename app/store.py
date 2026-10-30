from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

MAX_VERSIONS = 20
MAX_WORKSPACES = 40
MAX_TITLES = 64

_PG = None
_SQLITE = Path(os.environ.get("SLATE_DB", "data/slate.db"))


def _pg():
    global _PG
    if _PG is not None:
        return _PG or None
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        _PG = False
        return None
    try:
        import psycopg
        from psycopg_pool import ConnectionPool
    except ImportError:
        _PG = False
        return None
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    try:
        pool = ConnectionPool(url, min_size=1, max_size=4, open=True,
                              timeout=10)
        with pool.connection() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    id          TEXT PRIMARY KEY,
                    owner       TEXT NOT NULL,
                    name        TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    slots       INTEGER NOT NULL,
                    titles      TEXT NOT NULL,
                    versions    TEXT NOT NULL,
                    touched     DOUBLE PRECISION NOT NULL
                )""")
            con.execute("CREATE INDEX IF NOT EXISTS workspaces_owner "
                        "ON workspaces (owner, touched DESC)")
            con.execute("ALTER TABLE workspaces "
                        "ADD COLUMN IF NOT EXISTS placed INTEGER")
            con.execute("ALTER TABLE workspaces "
                        "ADD COLUMN IF NOT EXISTS audience TEXT")
            con.execute("ALTER TABLE workspaces "
                        "ADD COLUMN IF NOT EXISTS locked TEXT")
        _PG = pool
        return pool
    except Exception:
        _PG = False
        return None


def _lite():
    _SQLITE.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_SQLITE)
    con.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id          TEXT PRIMARY KEY,
            owner       TEXT NOT NULL,
            name        TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            slots       INTEGER NOT NULL,
            titles      TEXT NOT NULL,
            versions    TEXT NOT NULL,
            touched     REAL NOT NULL
        )""")
    con.execute("CREATE INDEX IF NOT EXISTS workspaces_owner "
                "ON workspaces (owner, touched DESC)")
    for column, kind in (("placed", "INTEGER"), ("audience", "TEXT"),
                         ("locked", "TEXT")):
        try:
            con.execute(f"ALTER TABLE workspaces ADD COLUMN {column} {kind}")
        except sqlite3.OperationalError:
            pass
    con.commit()
    return con


def _run(sql: str, args: tuple = (), fetch: bool = False):
    pool = _pg()
    if pool:
        with pool.connection() as con:
            cur = con.execute(sql, args)
            return cur.fetchall() if fetch else None
    con = _lite()
    try:
        cur = con.execute(sql.replace("%s", "?"), args)
        rows = cur.fetchall() if fetch else None
        con.commit()
        return rows
    finally:
        con.close()


def backend() -> str:
    return "postgres" if _pg() else "sqlite"


COLUMNS = ("id, owner, name, entity_type, slots, titles, versions, "
           "touched, placed, audience, locked")


def _row(r) -> dict:
    return {
        "id": r[0], "name": r[2], "entity_type": r[3], "slots": r[4],
        "titles": json.loads(r[5]), "versions": json.loads(r[6]),
        "touched": r[7],
        "placed": r[8],
        "audience": json.loads(r[9]) if r[9] else None,
        "locked": json.loads(r[10]) if r[10] else [],
    }


def listing(owner: str) -> list[dict]:
    rows = _run(f"SELECT {COLUMNS} FROM workspaces WHERE owner = %s "
                "ORDER BY touched DESC LIMIT %s",
                (owner, MAX_WORKSPACES), fetch=True) or []
    return [_row(r) for r in rows]


def read(owner: str, wid: str) -> dict | None:
    rows = _run(f"SELECT {COLUMNS} FROM workspaces WHERE owner = %s AND id = %s",
                (owner, wid), fetch=True) or []
    return _row(rows[0]) if rows else None


def create(owner: str, name: str, titles: list[str], entity_type: str,
           slots: int | None = None, audience: dict | None = None,
           locked: list[str] | None = None) -> dict:
    titles = [t.strip() for t in titles if t.strip()][:MAX_TITLES]
    wid = uuid.uuid4().hex
    now = time.time()
    old = listing(owner)
    for extra in old[MAX_WORKSPACES - 1:]:
        remove(owner, extra["id"])
    kept = json.dumps(audience) if audience else None
    held = [t for t in (locked or []) if t in titles]
    _run("INSERT INTO workspaces "
         "(id, owner, name, entity_type, slots, titles, versions, touched, "
         "audience, locked) "
         "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
         (wid, owner, name[:120] or "Workspace", entity_type,
          slots or len(titles), json.dumps(titles), json.dumps([]), now,
          kept, json.dumps(held) if held else None))
    return {"id": wid, "name": name[:120] or "Workspace",
            "entity_type": entity_type, "slots": slots or len(titles),
            "titles": titles, "versions": [], "touched": now,
            "placed": None, "audience": audience, "locked": held}


def update(owner: str, wid: str, **fields) -> dict | None:
    row = read(owner, wid)
    if row is None:
        return None
    if "titles" in fields:
        row["titles"] = [t.strip() for t in fields["titles"]
                         if t.strip()][:MAX_TITLES]
    if "name" in fields and isinstance(fields["name"], str):
        row["name"] = fields["name"][:120] or row["name"]
    if "slots" in fields and isinstance(fields["slots"], int):
        row["slots"] = max(1, min(fields["slots"], 200))
    if "versions" in fields:
        row["versions"] = list(fields["versions"])[:MAX_VERSIONS]
    if "placed" in fields:
        got = fields["placed"]
        row["placed"] = got if isinstance(got, int) and got >= 0 else None
    if "titles" in fields and "placed" not in fields:
        row["placed"] = None
    if "audience" in fields:
        row["audience"] = fields["audience"] or None
    if "locked" in fields:
        row["locked"] = list(fields["locked"] or [])
    row["locked"] = [t for t in row.get("locked") or []
                     if t in row["titles"]]
    row["touched"] = time.time()
    _run("UPDATE workspaces SET name = %s, slots = %s, titles = %s, "
         "versions = %s, touched = %s, placed = %s, audience = %s, "
         "locked = %s WHERE owner = %s AND id = %s",
         (row["name"], row["slots"], json.dumps(row["titles"]),
          json.dumps(row["versions"]), row["touched"], row["placed"],
          json.dumps(row["audience"]) if row.get("audience") else None,
          json.dumps(row["locked"]) if row["locked"] else None,
          owner, wid))
    return row


def add_version(owner: str, wid: str, titles: list[str],
                groups: int | None, sizes: list[int] | None = None) -> dict | None:
    row = read(owner, wid)
    if row is None:
        return None
    titles = [t for t in titles if t.strip()]
    kept = row["versions"]
    if kept and kept[0].get("titles") == titles:
        return row
    kept.insert(0, {"at": time.time(), "titles": titles, "groups": groups,
                    "sizes": list(sizes or [])})
    return update(owner, wid, versions=kept[:MAX_VERSIONS])


def remove(owner: str, wid: str) -> bool:
    if read(owner, wid) is None:
        return False
    _run("DELETE FROM workspaces WHERE owner = %s AND id = %s", (owner, wid))
    return True
