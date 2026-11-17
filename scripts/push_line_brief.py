#!/usr/bin/env python3
"""Fail-closed public-market LINE group push. Never reads private portfolio."""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")

def fail(message):
    raise SystemExit("SKIP LINE: " + message)

def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def main():
    now = dt.datetime.now(TZ)
    if not (now.hour == 8 and 5 <= now.minute <= 35):
        fail("outside 08:05–08:35 Taiwan delivery window")
    if now.weekday() >= 5:
        fail("weekend: no new regular US/TW session")
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    group = os.environ.get("LINE_GROUP_ID", "")
    if not token or not group:
        fail("LINE secrets not configured")
    data = json.loads(Path("report.json").read_text(encoding="utf-8"))
    tw = data.get("quotes") or {}
    us = data.get("us_quotes") or {}
    fx = data.get("fx") or {}
    sig = data.get("market_signals") or {}
    outlook = data.get("market_outlook") or {}
    expected = now.date() - dt.timedelta(days=1 if now.weekday() != 0 else 3)
    day = expected.isoformat()
    if tw.get("date") != day or us.get("date") != day:
        fail(f"expected both verified market dates {day}")
    if not str(data.get("report-date", "")).startswith(now.strftime("%Y/%m/%d")):
        fail("report analysis date is not today")
    if not str(outlook.get("as_of", "")).startswith(now.date().isoformat()):
        fail("market outlook date is not today")
    if any(not number((tw.get(t) or {}).get("close")) for t in ("taiex", "2330", "006208", "0050")):
        fail("missing TWSE prices")
    if any(not number((us.get(t) or {}).get("close")) for t in ("VOO", "NVDA", "TSLA", "QQQ", "SPCX")):
        fail("missing required US prices")
    if any(not number((sig.get(t) or {}).get("close")) for t in ("sp500", "nasdaq", "sox", "tsm_adr")):
        fail("missing market indices or ADR")
    future = sig.get("night_futures") or {}
    if any(not number(future.get(k)) for k in ("close", "change", "percent")):
        fail("night futures not verified")
    if (fx.get("provider"), fx.get("pair"), fx.get("type")) != ("Bank of Taiwan", "USD/TWD", "spot_buy"):
        fail("invalid FX provenance")
    if not number(fx.get("rate")) or fx.get("date") != day or not fx.get("source"):
        fail("FX quote is missing or stale")
    if not str(data.get("summary", "")).strip() or not str(data.get("action", "")).strip():
        fail("missing investment analysis")
    # Explicit confirmation by data publisher; dates alone cannot prove verification.
    qa = data.get("line_publish_ready") or {}
    if qa.get("approved") is not True or qa.get("report_date") != now.date().isoformat():
        fail("today's market data has not been explicitly approved for LINE")
    def pct(obj):
        v = obj.get("percent")
        return f"{v:+.2f}%" if number(v) else "待核實"
    msg = (
        f"📊 TCK 台美股晨報｜{now:%m/%d}\n"
        f"🇹🇼 台股 {day}\n"
        f"加權 {pct(tw['taiex'])}｜台積電 {pct(tw['2330'])}\n"
        f"006208 {pct(tw['006208'])}｜0050 {pct(tw['0050'])}\n"
        f"🇺🇸 美股 {day}\n"
        f"Nasdaq {pct(sig['nasdaq'])}｜SOX {pct(sig['sox'])}\n"
        f"NVDA {pct(us['NVDA'])}｜TSLA {pct(us['TSLA'])}\n"
        f"🔎 {data['summary'].strip()[:180]}\n"
        f"💰 {data['action'].strip()[:180]}\n"
        "🔗 https://tckuo1988.github.io/family-investment-brief/"
    )
    if len(msg) > 4900:
        fail("message too long")
    payload = json.dumps({"to": group, "messages": [{"type": "text", "text": msg}]}, ensure_ascii=False).encode()
    request = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=payload,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                fail("LINE returned non-success status")
    except urllib.error.HTTPError as exc:
        fail(f"LINE API HTTP {exc.code} (body withheld)")
    print("LINE push accepted by LINE API (delivery not independently confirmed)")

if __name__ == "__main__":
    main()
