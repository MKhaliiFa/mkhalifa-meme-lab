"""SQLite (WAL): coins seen, every decision, every paper position."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import asdict

from .rules import Position

SCHEMA = """
CREATE TABLE IF NOT EXISTS coins (mint TEXT PRIMARY KEY, seen REAL, name TEXT, symbol TEXT, state TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, mint TEXT, ts REAL, passed INTEGER, reason TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS positions (id INTEGER PRIMARY KEY, mint TEXT, kind TEXT, opened REAL, closed REAL,
  entry REAL, signal REAL, exit REAL, why TEXT, pnl REAL, pct REAL, data TEXT);
"""


class Store:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    def seen(self, mint: str) -> bool:
        return self.db.execute("SELECT 1 FROM coins WHERE mint=?", (mint,)).fetchone() is not None

    def add_coin(self, mint: str, ts: float) -> None:
        self.db.execute("INSERT OR IGNORE INTO coins (mint, seen, state) VALUES (?,?,'waiting')", (mint, ts))
        self.db.commit()

    def set_coin(self, mint: str, state: str, reason: str = "", name: str | None = None, symbol: str | None = None) -> None:
        self.db.execute("UPDATE coins SET state=?, reason=?, name=COALESCE(?,name), symbol=COALESCE(?,symbol) WHERE mint=?",
                        (state, reason, name, symbol, mint))
        self.db.commit()

    def waiting(self) -> list[tuple[str, float]]:
        return self.db.execute("SELECT mint, seen FROM coins WHERE state='waiting'").fetchall()

    def decision(self, mint: str, ts: float, passed: bool, reason: str, data: dict) -> None:
        self.db.execute("INSERT INTO decisions (mint, ts, passed, reason, data) VALUES (?,?,?,?,?)",
                        (mint, ts, int(passed), reason, json.dumps(data, default=str)[:4000]))
        self.db.commit()

    def save(self, p: Position) -> None:
        d = asdict(p)
        row = self.db.execute("SELECT id FROM positions WHERE mint=? AND kind=? AND opened=?", (p.mint, p.kind, p.opened)).fetchone()
        vals = (p.mint, p.kind, p.opened, p.closed, p.entry, p.signal, p.exit, p.why, p.pnl, p.pct, json.dumps(d, default=str))
        if row:
            self.db.execute("UPDATE positions SET mint=?, kind=?, opened=?, closed=?, entry=?, signal=?, exit=?, why=?, pnl=?, pct=?, data=? "
                            "WHERE id=?", vals + (row[0],))
        else:
            self.db.execute("INSERT INTO positions (mint, kind, opened, closed, entry, signal, exit, why, pnl, pct, data) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?)", vals)
        self.db.commit()

    def open_positions(self) -> list[Position]:
        out = []
        for (data,) in self.db.execute("SELECT data FROM positions WHERE closed IS NULL"):
            try:
                out.append(Position(**json.loads(data)))
            except (TypeError, ValueError):
                pass
        return out

    def closed(self, kind: str, since: float = 0.0) -> list[dict]:
        rows = self.db.execute("SELECT mint, opened, closed, pnl, pct, why FROM positions WHERE kind=? AND closed IS NOT NULL "
                               "AND closed>=? ORDER BY closed", (kind, since)).fetchall()
        return [dict(zip(("mint", "opened", "closed", "pnl", "pct", "why"), r)) for r in rows]

    def counts(self, since: float = 0.0) -> dict:
        seen = self.db.execute("SELECT COUNT(*) FROM coins WHERE seen>=?", (since,)).fetchone()[0]
        rej = self.db.execute("SELECT reason, COUNT(*) FROM decisions WHERE passed=0 AND ts>=? GROUP BY reason "
                              "ORDER BY 2 DESC LIMIT 5", (since,)).fetchall()
        return {"seen": seen, "top_rejects": rej}

    def first_seen(self) -> float | None:
        r = self.db.execute("SELECT MIN(seen) FROM coins").fetchone()
        return r[0] if r else None
