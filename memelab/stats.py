"""Results and the verdict fixed in advance (README, "The verdict")."""
from __future__ import annotations

import math

from . import config as C


def stats(rows: list[dict]) -> dict:
    p = [float(r["pnl"]) for r in rows]
    n = len(p)
    if not n:
        return {"n": 0, "pnl": 0.0, "avg_pct": None, "win": None, "t": None, "pnl_ex_best": 0.0}
    pct = [float(r["pct"]) for r in rows]
    mean = sum(pct) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in pct) / (n - 1)) if n > 1 else 0.0
    t = mean / (sd / math.sqrt(n)) if sd > 0 else None
    return {"n": n, "pnl": round(sum(p), 2), "avg_pct": round(mean, 2), "win": round(sum(1 for x in p if x > 0) / n, 3),
            "t": round(t, 2) if t is not None else None, "pnl_ex_best": round(sum(p) - max(p), 2),
            "best": round(max(p), 2), "worst": round(min(p), 2)}


def verdict(f: dict, c: dict, days: float) -> str:
    """PASS needs ALL: 14+ days, 100+ filter trades, net > 0 after costs, still > 0 without the best trade,
    t-stat > 2, and the filter beating 'buy every graduate' (control) per trade."""
    if days < C.VERDICT_DAYS or f["n"] < C.VERDICT_MIN_TRADES:
        return f"measuring ({f['n']} of {C.VERDICT_MIN_TRADES:.0f} trades, {days:.1f} of {C.VERDICT_DAYS:.0f} days)"
    fails = []
    if f["pnl"] <= 0:
        fails.append("loses after costs")
    if f["pnl_ex_best"] <= 0:
        fails.append("only one lucky trade")
    if not f["t"] or f["t"] <= 2:
        fails.append(f"not significant (t {f['t']})")
    if c["n"] and f["avg_pct"] is not None and c["avg_pct"] is not None and f["avg_pct"] <= c["avg_pct"]:
        fails.append("no better than buying every graduate")
    return "PASS" if not fails else "FAIL: " + "; ".join(fails)
