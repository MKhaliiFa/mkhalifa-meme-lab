"""Reading the free sources defensively: a key that is not there is None, never a guess."""
from __future__ import annotations


def num(x) -> float | None:
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def dig(d, *path):
    for k in path:
        if isinstance(d, dict):
            d = d.get(k)
        elif isinstance(d, list) and isinstance(k, int) and -len(d) <= k < len(d):
            d = d[k]
        else:
            return None
    return d


def migration_mint(msg: dict) -> str | None:
    """PumpPortal subscribeMigration message -> the token mint (None for the subscribe ack and others)."""
    if not isinstance(msg, dict):
        return None
    m = msg.get("mint")
    return m if isinstance(m, str) and 30 <= len(m) <= 50 else None


def best_pair(pairs: list, mint: str) -> dict | None:
    """DexScreener /tokens/v1: the pair of this token with the most liquidity (PumpSwap first)."""
    mine = [p for p in pairs or [] if dig(p, "baseToken", "address") == mint]
    if not mine:
        return None
    mine.sort(key=lambda p: ((p.get("dexId") == "pumpswap"), num(dig(p, "liquidity", "usd")) or 0), reverse=True)
    return mine[0]


def market(p: dict | None) -> dict:
    """The numbers the lab uses from one DexScreener pair."""
    if not p:
        return {}
    return {"price": num(p.get("priceUsd")), "liq": num(dig(p, "liquidity", "usd")), "mcap": num(p.get("marketCap")),
            "h1": num(dig(p, "priceChange", "h1")), "m5": num(dig(p, "priceChange", "m5")),
            "vol_h1": num(dig(p, "volume", "h1")), "buys_h1": num(dig(p, "txns", "h1", "buys")),
            "sells_h1": num(dig(p, "txns", "h1", "sells")), "name": dig(p, "baseToken", "name"),
            "symbol": dig(p, "baseToken", "symbol"), "pair": p.get("pairAddress"), "dex": p.get("dexId")}


def _strings(x, out: set) -> set:
    if isinstance(x, str):
        out.add(x)
    elif isinstance(x, dict):
        for v in x.values():
            _strings(v, out)
    elif isinstance(x, list):
        for v in x:
            _strings(v, out)
    return out


def safety(rep: dict | None) -> dict:
    """RugCheck report -> mint/freeze authority, top-10 share (pools excluded), creator share, danger risks.
    Anything not found is None (the filter treats None as a fail and the health line counts it)."""
    if not isinstance(rep, dict):
        return {}
    pools = _strings(rep.get("markets") or [], set())
    holders = [h for h in rep.get("topHolders") or [] if isinstance(h, dict)]
    real = [h for h in holders if h.get("address") not in pools and h.get("owner") not in pools]
    top10 = sum(num(h.get("pct")) or 0 for h in real[:10]) if holders else None
    creator = rep.get("creator")
    dev = None
    if creator:
        dev = sum(num(h.get("pct")) or 0 for h in holders if h.get("owner") == creator or h.get("address") == creator)
        if not dev:
            bal, sup = num(rep.get("creatorBalance")), num(dig(rep, "token", "supply"))
            dev = 100 * bal / sup if bal is not None and sup else (0.0 if bal == 0 else None)
    risks = [r for r in rep.get("risks") or [] if isinstance(r, dict)]
    return {"mint_auth": rep.get("mintAuthority"), "freeze_auth": rep.get("freezeAuthority"),
            "has_auth_keys": "mintAuthority" in rep and "freezeAuthority" in rep,
            "top10": top10, "dev": dev, "danger": sum(1 for r in risks if str(r.get("level")).lower() == "danger"),
            "danger_names": [str(r.get("name"))[:40] for r in risks if str(r.get("level")).lower() == "danger"][:3],
            "holders": num(rep.get("totalHolders"))}
