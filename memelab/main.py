"""The lab's one process: stream -> waiting room -> one decision at 10 min -> paper positions -> summary.

  python -m memelab.main            run (systemd: mkhalifa-meme-lab.service)
  python -m memelab.main --check    one call to every source, print what came back, exit
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from . import config as C
from . import fields as F
from . import report, sources as S
from .rules import Position, gate
from .store import Store


class Lab:
    def __init__(self, store: Store, clock=time.time):
        self.store, self.clock = store, clock
        self.open = {(p.mint, p.kind): p for p in store.open_positions()}
        self.rug: dict[str, dict] = {}

    # ------------------------------------------------------------ the waiting room (every 60 s)
    def decide(self, pairs: list, rug_fn) -> int:
        now = self.clock()
        opened = 0
        for mint, seen in self.store.waiting():
            age = (now - seen) / 60
            if age < C.MIN_AGE_MIN:
                continue
            mk = F.market(F.best_pair(pairs, mint))
            if not mk.get("price") or not mk.get("liq"):
                if age >= C.MAX_WAIT_MIN:
                    self.store.set_coin(mint, "dropped", "never on DexScreener")
                continue
            if mint not in self.rug:
                rep = rug_fn(mint)
                S.save_raw("rugcheck", rep)
                self.rug[mint] = F.safety(rep)
            sf = self.rug.pop(mint)
            ok, why = gate(age, mk, sf)
            self.store.decision(mint, now, ok, why, {"market": mk, "safety": sf, "age_min": round(age, 1)})
            # control: every graduate that reached 10 min with a price, bought with no rules at all
            ctrl = Position.open(mint, now, mk["price"], mk["liq"], "control", {"symbol": mk.get("symbol")})
            self.open[(mint, "control")] = ctrl
            self.store.save(ctrl)
            if ok:
                p = Position.open(mint, now, mk["price"], mk["liq"], "filter",
                                  {"symbol": mk.get("symbol"), "name": mk.get("name"), "market": mk, "safety": sf})
                self.open[(mint, "filter")] = p
                self.store.save(p)
                opened += 1
            self.store.set_coin(mint, "bought" if ok else "rejected", why, mk.get("name"), mk.get("symbol"))
        return opened

    # ------------------------------------------------------------ open paper positions (every 15 s)
    def manage(self, pairs: list) -> list[Position]:
        now, done = self.clock(), []
        for key, p in list(self.open.items()):
            mk = F.market(F.best_pair(pairs, p.mint))
            if p.check(now, mk.get("price"), mk.get("liq")):
                done.append(p)
                self.open.pop(key, None)
            self.store.save(p)
        return done

    def mints_open(self) -> list[str]:
        return sorted({p.mint for p in self.open.values()})


async def stream(lab: Lab) -> None:
    import websockets
    back = 1
    while True:
        try:
            async with websockets.connect(C.PUMPPORTAL_WS, ping_interval=30, open_timeout=20) as ws:
                await ws.send(json.dumps({"method": "subscribeMigration"}))
                back = 1
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=900)
                    S.H.ws_last, S.H.ws_msgs = time.time(), S.H.ws_msgs + 1
                    try:
                        msg = json.loads(raw)
                    except ValueError:
                        continue
                    mint = F.migration_mint(msg)
                    if mint:
                        S.save_raw("pumpportal", msg)
                        if not lab.store.seen(mint):
                            lab.store.add_coin(mint, time.time())
        except Exception as e:  # dropped, silent, refused: back off and reconnect
            S.H.bad("pumpportal", e)
            S.H.ws_reconnects += 1
            await asyncio.sleep(back)
            back = min(60, back * 2)


async def loop(lab: Lab) -> None:
    last_wait = last_sum = 0.0
    while True:
        now = time.time()
        try:
            if now - last_wait >= C.WAIT_POLL_S:
                last_wait = now
                w = [m for m, _ in lab.store.waiting()]
                if w:
                    pairs = await asyncio.to_thread(S.dexscreener, w)
                    S.save_raw("dexscreener", pairs[:1] if pairs else None)
                    await asyncio.to_thread(lab.decide, pairs, S.rugcheck)
            if lab.open:
                pairs = await asyncio.to_thread(S.dexscreener, lab.mints_open())
                lab.manage(pairs)
            if now - last_sum >= C.SUMMARY_S:
                last_sum = now
                report.write(report.build(lab.store, S.H.snapshot(now), now, len(lab.open)))
        except Exception as e:
            S.H.bad("loop", e)
        await asyncio.sleep(C.OPEN_POLL_S)


def check() -> int:
    """One call to every source (install-time proof). Never writes positions."""
    ok = True
    pairs = S.dexscreener(["So11111111111111111111111111111111111111112"])
    print("OK dexscreener" if pairs else "FAIL dexscreener", len(pairs or []), "pairs")
    ok &= bool(pairs)
    rep = S.rugcheck("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")       # BONK: a long-graduated token
    sf = F.safety(rep)
    print("OK rugcheck" if sf.get("has_auth_keys") else "FAIL rugcheck", {k: sf.get(k) for k in ("top10", "dev", "danger")})
    ok &= bool(sf.get("has_auth_keys"))
    try:
        import websockets  # noqa: F401

        async def one():
            async with websockets.connect(C.PUMPPORTAL_WS, open_timeout=20) as ws:
                await ws.send(json.dumps({"method": "subscribeMigration"}))
                return await asyncio.wait_for(ws.recv(), timeout=20)
        print("OK pumpportal", str(asyncio.run(one()))[:80])
    except Exception as e:
        print("FAIL pumpportal", type(e).__name__, str(e)[:80])
        ok = False
    print("ALL OK" if ok else "SOME SOURCES FAILED")
    return 0 if ok else 1


def main() -> None:
    if "--check" in sys.argv:
        sys.exit(check())
    os.makedirs(C.DATA_DIR, exist_ok=True)
    lab = Lab(Store(os.path.join(C.DATA_DIR, "lab.sqlite")))
    report.write(report.build(lab.store, S.H.snapshot(time.time()), time.time(), len(lab.open)))

    async def run():
        await asyncio.gather(stream(lab), loop(lab))
    asyncio.run(run())


if __name__ == "__main__":
    main()
