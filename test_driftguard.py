"""DriftGuard test suite — 10 test cases covering core detection engine."""
import os, tempfile, sqlite3, json, csv
import pytest
from driftguard import Column, Schema, Drift, snapshot_sqlite, snapshot_csv, snapshot_json, diff_schemas, save_snapshot, load_snapshot


@pytest.fixture
def tmp(tmp_path):
    return str(tmp_path)


def _make_db(path, table, ddl, rows=None):
    conn = sqlite3.connect(path)
    conn.execute(f"CREATE TABLE {table} ({ddl})")
    for r in (rows or []):
        conn.execute(f"INSERT INTO {table} VALUES ({','.join('?' * len(r))})", r)
    conn.commit()
    conn.close()


def test_sqlite_snapshot(tmp):
    db = os.path.join(tmp, "t.db")
    _make_db(db, "users", "id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER")
    s = snapshot_sqlite(db, "users")
    assert s.table == "users" and len(s.columns) == 3
    assert s.columns[0].dtype == "INTEGER" and s.columns[1].dtype == "TEXT"
    assert s.fingerprint and len(s.fingerprint) == 16


def test_csv_snapshot_type_inference(tmp):
    p = os.path.join(tmp, "data.csv")
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "score"])
        w.writerows([["1", "alice", "95.5"], ["2", "bob", "87.0"]])
    s = snapshot_csv(p)
    assert s.columns[0].dtype == "INTEGER"
    assert s.columns[1].dtype == "TEXT"
    assert s.columns[2].dtype == "REAL"


def test_json_snapshot(tmp):
    p = os.path.join(tmp, "d.json")
    with open(p, "w") as f:
        json.dump([{"id": 1, "name": "alice", "active": True, "score": 3.14}], f)
    s = snapshot_json(p)
    types = {c.name: c.dtype for c in s.columns}
    assert types == {"id": "INTEGER", "name": "TEXT", "active": "BOOLEAN", "score": "REAL"}


def test_diff_no_drift():
    s = Schema("x", "t", [Column("id", "INTEGER", False, 0), Column("name", "TEXT", True, 1)])
    assert diff_schemas(s, s) == []


def test_diff_column_removed_is_breaking():
    old = Schema("x", "orders", [Column("id", "INTEGER", False, 0), Column("amount", "REAL", True, 1)])
    new = Schema("x", "orders", [Column("id", "INTEGER", False, 0)])
    drifts = diff_schemas(old, new)
    assert len(drifts) == 1
    assert drifts[0].kind == "column_removed" and drifts[0].severity == "breaking"
    assert "ALTER TABLE" in drifts[0].fix


def test_diff_int_to_text_is_silent_corruption():
    old = Schema("x", "t", [Column("amount", "INTEGER", True, 0)])
    new = Schema("x", "t", [Column("amount", "TEXT", True, 0)])
    drifts = diff_schemas(old, new)
    assert drifts[0].severity == "silent_corruption"
    assert "CAST" in drifts[0].fix


def test_diff_column_reorder_is_silent_corruption():
    old = Schema("x", "t", [Column("email", "TEXT", True, 0), Column("phone", "TEXT", True, 1)])
    new = Schema("x", "t", [Column("email", "TEXT", True, 1), Column("phone", "TEXT", True, 0)])
    drifts = diff_schemas(old, new)
    reorders = [d for d in drifts if d.kind == "column_reordered"]
    assert len(reorders) == 2
    assert all(d.severity == "silent_corruption" for d in reorders)


def test_diff_nullable_change():
    old = Schema("x", "t", [Column("id", "INTEGER", False, 0)])
    new = Schema("x", "t", [Column("id", "INTEGER", True, 0)])
    drifts = diff_schemas(old, new)
    assert any(d.kind == "nullable_changed" and d.severity == "silent_corruption" for d in drifts)


def test_save_load_roundtrip(tmp):
    s = Schema("sqlite://test.db", "users", [Column("id", "INTEGER", False, 0), Column("name", "TEXT", True, 1)])
    save_snapshot(s, store=tmp)
    loaded = load_snapshot("users", store=tmp)
    assert loaded is not None
    assert loaded.fingerprint == s.fingerprint
    assert len(loaded.columns) == 2 and loaded.columns[0].name == "id"


def test_severity_sort_order():
    old = Schema("x", "t", [Column("a", "INTEGER", True, 0), Column("b", "TEXT", True, 1), Column("c", "REAL", True, 2)])
    new = Schema("x", "t", [Column("a", "TEXT", True, 0), Column("d", "TEXT", True, 1)])
    drifts = diff_schemas(old, new)
    severities = [d.severity for d in drifts]
    assert severities.index("breaking") < severities.index("silent_corruption")
