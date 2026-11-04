"""The free public sources. Plain HTTPS (stdlib); only the PumpPortal stream needs the `websockets` package."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from . import config as C

UA = {"User-Agent": "mkhalifa-meme-lab/1.0 (paper research)", "Accept": "application/json"}


class Health:
    def __init__(self):
        self.ok: dict[str, int] = {}
        self.err: dict[str, int] = {}
        self.last_err: dict[str, str] = {}
        self.ws_last = 0.0
        self.ws_reconnects = 0
        self.ws_msgs = 0

    def good(self, name: str) -> None:
        self.ok[name] = self.ok.get(name, 0) + 1

    def bad(self, name: str, e: Exception | str) -> None:
        self.err[name] = self.err.get(name, 0) + 1
        self.last_err[name] = (f"{type(e).__name__}: {e}" if isinstance(e, Exception) else str(e))[:120]

    def snapshot(self, now: float) -> dict:
        return {"ok": dict(self.ok), "err": dict(self.err), "last_err": dict(self.last_err),
                "ws_last_msg_age_s": round(now - self.ws_last) if self.ws_last else None,
                "ws_reconnects": self.ws_reconnects, "ws_msgs": self.ws_msgs}


H = Health()


def get_json(url: str, name: str, timeout: float = 15):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
        H.good(name)
        return d
    except urllib.error.HTTPError as e:
        H.bad(name, f"HTTP {e.code}")
        if e.code == 429:
            time.sleep(30)
        return None
    except Exception as e:  # network, JSON
        H.bad(name, e)
        return None


def dexscreener(mints: list[str]) -> list:
    out = []
    for i in range(0, len(mints), 30):
        d = get_json(C.DEXSCREENER + ",".join(mints[i:i + 30]), "dexscreener")
        if isinstance(d, list):
            out.extend(d)
        elif isinstance(d, dict) and isinstance(d.get("pairs"), list):
            out.extend(d["pairs"])
    return out


def rugcheck(mint: str):
    return get_json(C.RUGCHECK.format(mint=mint), "rugcheck", timeout=25)


def save_raw(name: str, data) -> None:
    """One raw sample of every source, kept so the key mapping can be checked by a human."""
    p = os.path.join(C.DATA_DIR, "raw", name + ".json")
    if os.path.exists(p) or data is None:
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(data, f, indent=1, default=str)
