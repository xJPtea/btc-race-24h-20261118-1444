#!/usr/bin/env python3
"""Synthetic-bar smoke test for main.py.

Feeds hand-built streams through the bot (hello, then batches of 1-minute
bars, then done) and checks that:
  * every batch gets exactly one reply with a matching seq,
  * every reply is valid JSON with an orders list,
  * the bot buys exactly once on a cross above its 240-bar mean and sells
    once on the take-profit, and never trades on a flat/sideways feed.

The second test drives the bot interactively so fills are honoured: once
the bot's sell is filled, later batches show no position.

Run: python3 test_synthetic.py
"""
import json
import subprocess
import sys

BOT = "main.py"


class BotSession:
    def __init__(self):
        self.proc = subprocess.Popen(
            [sys.executable, "-P", "-s", BOT],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, cwd=".",
        )
        self.replies = []

    def send_hello(self, msg):
        # hello gets no reply; only batches are answered
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def send(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        assert line, "bot closed stdout early"
        reply = json.loads(line)
        self.replies.append(reply)
        return reply

    def close(self, done_msg):
        self.proc.stdin.write(json.dumps(done_msg) + "\n")
        self.proc.stdin.flush()
        self.proc.stdin.close()
        rc = self.proc.wait(timeout=30)
        assert rc == 0, f"bot exited {rc}: {self.proc.stderr.read()[-2000:]}"


def hello():
    return {
        "type": "hello", "protocol": "agent-fun/bars-replay/v1",
        "seed": 12345,
        "symbols": [{"symbol": "CBBTC",
                     "mint": "cbbtcf3aa214zXHbiAZQwf4122FBYbraNdFqgw4iMij",
                     "price_scale": 5, "qty_scale": 8}],
        "capital": {"quote": "USDC", "quote_scale": 6,
                    "quote_units": "1000000000"},
        "bar_interval": "1m", "first_close_ms": 1_000_000_000_000,
        "caps": {"max_open_positions": 1, "max_orders_per_bar": 16,
                 "max_weight_bps": 10000, "shorts": False, "leverage": False},
        "fees": {"fee_bps": 4, "min_notional_quote_units": "1000000",
                 "slippage_bps": 2},
        "latency_bars": 1,
    }


def bar(seq, close, depth=None):
    # depth: [x1, y1, x2, y2] pool state; a deep pool keeps price impact tiny
    d = depth or ["100000000000000", "100000000000000000000",
                  "100000000000000", "100000000000000000000"]
    return {
        "seq": seq, "t": 1_000_000_000_000 + seq * 60_000, "symbol": "CBBTC",
        "o": str(close), "h": str(close), "l": str(close), "c": str(close),
        "v": "0", "o_depth": d, "c_depth": d,
    }


def batch(seq, close, cash=1_000_000_000, positions=None, fills=None):
    return {
        "type": "batch", "seq": seq, "t": 1_000_000_000_000 + seq * 60_000,
        "bars": [bar(seq, close)], "fills": fills or [],
        "account": {"cash_quote_units": str(cash),
                    "positions": positions or [],
                    "equity_quote_units": str(cash)},
    }


def done(seq, cash=1_000_000_000, positions=None):
    return {"type": "done", "seq": seq,
            "account": {"cash_quote_units": str(cash),
                        "positions": positions or [],
                        "equity_quote_units": str(cash)}}


def test_cross_and_take_profit():
    base = 6_000_000_000  # $60,000 at price_scale 5
    bot = BotSession()
    bot.send_hello(hello())
    buy_seq = None
    sell_seq = None
    buy_close = None
    pos = None
    for seq in range(340):
        if seq < 240:
            close = base
        else:
            close = int(base * (1 + 0.001 * (seq - 240 + 1)))
        cash = 0 if pos else 1_000_000_000
        r = bot.send(batch(seq, close, cash=cash, positions=pos or []))
        assert r["type"] == "reply" and r["seq"] == seq
        assert isinstance(r["orders"], list)
        buys = [o for o in r["orders"] if o["side"] == "buy"]
        sells = [o for o in r["orders"] if o["side"] == "sell"]
        if buys:
            assert buy_seq is None, f"second buy at seq {seq}"
            buy_seq = seq
            buy_close = close
            # the buy fills at the next bar's open; simulate the position.
            # qty for a $1,000 cost: value = qty*price/10**7 (micro-USDC),
            # so qty = cost * 10**7 // price.
            qty = 1_000_000_000 * 10**7 // close
            pos = [{"symbol": "CBBTC", "qty": str(qty),
                    "cost_quote_units": "1000000000"}]
        if sells:
            assert sell_seq is None, f"second sell at seq {seq}"
            assert buy_seq is not None, "sell before buy"
            assert len(sells) == 1 and sells[0]["qty"] == pos[0]["qty"]
            sell_seq = seq
            pos = None  # the sell fills: no position from the next bar on
        assert not (buys and sells), f"buy and sell in one reply at seq {seq}"
    assert buy_seq is not None, "no buy on the rising ramp"
    print(f"  buy at seq {buy_seq} (cross above 240-bar mean) -- ok")
    assert sell_seq is not None, "no sell on the rising ramp"
    # value at the sell bar must be >= +1.5% vs the $1,000 cost
    qty = 1_000_000_000 * 10**7 // buy_close
    sell_close = int(base * (1 + 0.001 * (sell_seq - 240 + 1)))
    value = qty * sell_close // 10**7
    assert value >= 1_015_000_000, f"sell too early, value {value}"
    print(f"  sell at seq {sell_seq} (take-profit, value ${value/1e6:.2f}) -- ok")
    bot.close(done(340, cash=1_015_000_000))
    assert len(bot.replies) == 340, f"expected 340 replies, got {len(bot.replies)}"


def test_flat_market_never_trades():
    bot = BotSession()
    bot.send_hello(hello())
    for seq in range(300):
        r = bot.send(batch(seq, 6_000_000_000))
        assert r["type"] == "reply" and r["seq"] == seq
        assert r["orders"] == [], f"flat market traded at seq {seq}: {r}"
    bot.close(done(300))
    print("  flat market: 0 orders in 300 bars -- ok")


if __name__ == "__main__":
    print("test_cross_and_take_profit:")
    test_cross_and_take_profit()
    print("test_flat_market_never_trades:")
    test_flat_market_never_trades()
    print("ALL TESTS PASSED")
