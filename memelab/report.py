"""summary.json: the lab's state for the bot's 09:00 daily report and the dashboard (plain text lines)."""
from __future__ import annotations

import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

from . import config as C
from .stats import stats, verdict

CAIRO = ZoneInfo("Africa/Cairo")


def _money(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}${abs(x):.2f}"


def build(store, health: dict, now: float, open_n: int) -> dict:
    day = now - 86400
    first = store.first_seen() or now
    days = (now - first) / 86400
    f_all, c_all = stats(store.closed("filter")), stats(store.closed("control"))
    f_day, c_day = stats(store.closed("filter", day)), stats(store.closed("control", day))
    cnt = store.counts(day)
    v = verdict(f_all, c_all, days)
    rej = ", ".join(f"{r} {n}" for r, n in cnt["top_rejects"][:3]) or "none"
    ws_age = health.get("ws_last_msg_age_s")
    src = "sources ok" if not health.get("err") else "errors: " + ", ".join(f"{k} {v}" for k, v in health["err"].items())
    lines = [
        "🧪 Meme Lab (paper, no real money)",
        f"Last 24 h: {cnt['seen']} graduates seen · {f_day['n']} paper trades {_money(f_day['pnl'])}"
        + (f" · win {f_day['win'] * 100:.0f}%" if f_day["win"] is not None else ""),
        f"Buy-every-graduate (control): {c_day['n']} trades {_money(c_day['pnl'])}",
        f"Since start ({days:.1f} days): {f_all['n']} trades {_money(f_all['pnl'])}"
        + (f" · {f_all['avg_pct']:+.1f}% avg" if f_all["avg_pct"] is not None else "") + f" · open {open_n}",
        f"Most rejected: {rej}",
        f"Verdict: {v}",
        f"Health: stream {'live' if ws_age is not None and ws_age < 900 else 'quiet' if ws_age is not None else 'not connected'} · {src}",
    ]
    return {"ts": now, "updated": dt.datetime.fromtimestamp(now, CAIRO).strftime("%Y-%m-%d %H:%M Cairo"),
            "days": round(days, 2), "filter": f_all, "control": c_all, "filter_24h": f_day, "control_24h": c_day,
            "seen_24h": cnt["seen"], "top_rejects": cnt["top_rejects"], "verdict": v, "open": open_n,
            "health": health, "report_lines": lines,
            "rules": {k: getattr(C, k) for k in ("MIN_AGE_MIN", "MIN_LIQ_USD", "MAX_TOP10_PCT", "MAX_DEV_PCT", "MAX_H1_PCT",
                                                 "TICKET_USD", "FEE_PCT", "STOP_PCT", "TRAIL_START_PCT", "TRAIL_PCT", "TIMEOUT_H")}}


def write(summary: dict, path: str | None = None) -> None:
    path = path or C.SUMMARY_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(summary, f, indent=1, default=str)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
