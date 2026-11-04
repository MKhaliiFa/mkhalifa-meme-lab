"""The entry filter and the paper position. Pure functions: the tests hold them to the written rules."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config as C


def gate(age_min: float, mk: dict, sf: dict) -> tuple[bool, str]:
    """(passed, the first rule that failed). Missing data is a fail ("no data: ...")."""
    if age_min < C.MIN_AGE_MIN:
        return False, "too young"
    if not mk or mk.get("price") is None or mk.get("liq") is None:
        return False, "no data: market"
    if mk["liq"] < C.MIN_LIQ_USD:
        return False, f"liquidity ${mk['liq']:,.0f}"
    if mk.get("h1") is not None and mk["h1"] > C.MAX_H1_PCT:
        return False, f"+{mk['h1']:.0f}% in 1h (chasing)"
    if not sf or not sf.get("has_auth_keys"):
        return False, "no data: safety"
    if sf.get("mint_auth"):
        return False, "mint not revoked"
    if sf.get("freeze_auth"):
        return False, "freeze not revoked"
    if sf.get("top10") is None:
        return False, "no data: holders"
    if sf["top10"] > C.MAX_TOP10_PCT:
        return False, f"top 10 hold {sf['top10']:.0f}%"
    if sf.get("dev") is None:
        return False, "no data: creator"
    if sf["dev"] > C.MAX_DEV_PCT:
        return False, f"dev holds {sf['dev']:.1f}%"
    if (sf.get("danger") or 0) > C.MAX_DANGER_RISKS:
        return False, "danger: " + ", ".join(sf.get("danger_names") or ["risk"])
    return True, ""


def impact(ticket: float, liq: float | None) -> float:
    """Price impact of a market order of `ticket` USD into a constant-product pool holding `liq` USD in all."""
    if not liq or liq <= 0:
        return 0.5
    side = liq / 2
    return ticket / (side + ticket)


@dataclass
class Position:
    mint: str
    opened: float
    entry: float                 # what the paper buy really paid per token (impact included)
    signal: float                # the price seen when the decision was taken
    liq0: float
    kind: str = "filter"         # "filter" = passed the rules; "control" = every coin at 10 min, no rules
    peak: float = 0.0
    trail: bool = False
    closed: float | None = None
    exit: float | None = None
    why: str = ""
    pnl: float = 0.0
    pct: float = 0.0
    meta: dict = field(default_factory=dict)

    @classmethod
    def open(cls, mint: str, ts: float, price: float, liq: float, kind: str = "filter", meta: dict | None = None):
        fill = price * (1 + impact(C.TICKET_USD, liq))
        return cls(mint, ts, fill, price, liq, kind, peak=price, meta=meta or {})

    def check(self, ts: float, price: float | None, liq: float | None) -> str | None:
        """Exit rules in a fixed order. Returns the reason when it closes (and fills the result)."""
        if self.closed:
            return None
        if price is None or price <= 0:
            return None
        if liq is not None and self.liq0 and liq <= self.liq0 * (1 - C.PULLED_LIQ_DROP):
            return self._close(ts, price, liq, "liquidity pulled")
        self.peak = max(self.peak, price)
        if price <= self.signal * (1 - C.STOP_PCT / 100):
            return self._close(ts, price, liq, "stop")
        if price >= self.signal * (1 + C.TRAIL_START_PCT / 100):
            self.trail = True
        if self.trail and price <= self.peak * (1 - C.TRAIL_PCT / 100):
            return self._close(ts, price, liq, "trail")
        if ts - self.opened >= C.TIMEOUT_H * 3600 and price < self.signal * (1 + C.TIMEOUT_MIN_GAIN_PCT / 100):
            return self._close(ts, price, liq, "timeout")
        return None

    def _close(self, ts: float, price: float, liq: float | None, why: str) -> str:
        sell = price * (1 - impact(C.TICKET_USD, liq if liq else self.liq0 * 0.2))
        tokens = C.TICKET_USD / self.entry
        gross = tokens * sell
        fees = C.TICKET_USD * C.FEE_PCT / 100 + gross * C.FEE_PCT / 100 + 2 * C.GAS_USD
        self.pnl = round(gross - C.TICKET_USD - fees, 4)
        self.pct = round(100 * self.pnl / C.TICKET_USD, 2)
        self.closed, self.exit, self.why = ts, sell, why
        return why
