#!/usr/bin/env python3
"""Automatic public-market LINE briefing. No private portfolio or AI-generated claims."""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")
REQUIRED = ("TAIEX", "006208", "0050", "VOO", "QQQ", "NVDA", "TSLA", "SPCX")

def stop(reason):
    raise SystemExit("SKIP LINE: " + reason)

def weekdays_since(session, today):
    d = session + dt.timedelta(days=1)
    n = 0
    while d < today:
        if d.weekday() < 5:
            n += 1
        d += dt.timedelta(days=1)
    return n

def latest_two(series, symbol):
    rows = series.get(symbol) or []
    if len(rows) < 2:
        stop(symbol + ": fewer than two closing prices")
    pair = rows[-2:]
    try:
        days = [dt.date.fromisoformat(row["date"]) for row in pair]
        prices = [float(row["close"]) for row in pair]
    except (KeyError, ValueError, TypeError):
        stop(symbol + ": invalid quote")
    if days[0] >= days[1] or any(not (0 < x < 1e9) for x in prices):
        stop(symbol + ": invalid quote order/value")
    return days[1], prices[1], (prices[1] / prices[0] - 1) * 100

def push(message):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    group = os.environ.get("LINE_GROUP_ID", "").strip()
    if not token or not group:
        stop("missing GitHub LINE secrets")
    payload = json.dumps({"to": group, "messages": [{"type": "text", "text": message}]}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=payload,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                stop("LINE API returned unexpected status")
    except urllib.error.HTTPError as exc:
        stop(f"LINE API HTTP {exc.code}; body withheld")
    print("LINE API accepted automated brief; verify receipt in group.")

def main():
    now = dt.datetime.now(TZ)
    if now.weekday() >= 5:
        stop("weekend")
    if os.environ.get("LINE_MANUAL_TODAY", "").strip().lower() not in ("true", "1", "yes") and (now.hour != 8 or not (5 <= now.minute <= 35)):
        stop("outside 08:05–08:35 Asia/Taipei window")
    data = json.loads(Path("history.json").read_text(encoding="utf-8"))
    series = data.get("series") or {}
    quotes = {symbol: latest_two(series, symbol) for symbol in REQUIRED}
    today = now.date()
    tw_day = quotes["TAIEX"][0]
    us_day = quotes["QQQ"][0]
    for market, day in (("Taiwan", tw_day), ("US", us_day)):
        if day >= today or weekdays_since(day, today) > 1:
            stop(f"{market} market session {day} not recent/complete")
    for symbol in ("006208", "0050"):
        if quotes[symbol][0] != tw_day:
            stop(f"{symbol} date does not match TAIEX")
    for symbol in ("VOO", "NVDA", "TSLA", "SPCX"):
        if quotes[symbol][0] != us_day:
            stop(f"{symbol} date does not match QQQ")
    def fmt(symbol, digits=2):
        _, price, pct = quotes[symbol]
        return f"{price:,.{digits}f}（{pct:+.2f}%）"
    tai_pct = quotes["TAIEX"][2]
    qqq_pct = quotes["QQQ"][2]
    if tai_pct <= -2 and qqq_pct <= -2:
        observation = "台美股同步承壓；額外投入先確認備用金與資金配置。"
    elif tai_pct <= -2:
        observation = "台股跌幅較大；定期定額與額外加碼應分開評估。"
    elif qqq_pct <= -2:
        observation = "美股科技股波動較大；避免僅憑單日跌幅追價。"
    elif tai_pct >= 2 and qqq_pct >= 2:
        observation = "台美股同步走強；仍依長期配置與現金流執行。"
    else:
        observation = "維持長期配置紀律；額外加碼須考量現金流與風險承受度。"
    message = (
        f"📊 TCK 台美股精簡晨報｜{now:%m/%d} 08:10\n"
        f"🇹🇼 臺股收盤 {tw_day:%m/%d}\n"
        f"加權 {fmt('TAIEX')}\n"
        f"006208 {fmt('006208')}｜0050 {fmt('0050')}\n"
        f"🇺🇸 美股收盤 {us_day:%m/%d}（美元）\n"
        f"VOO {fmt('VOO')}｜QQQ {fmt('QQQ')}\n"
        f"NVDA {fmt('NVDA')}｜TSLA {fmt('TSLA')}\n"
        f"SPCX {fmt('SPCX')}\n"
        f"🔎 {observation}\n"
        "📌 以上為行情規則式觀察，非個別投資建議。\n"
        "資料：Yahoo Finance 歷史日線（可能與交易所官方收盤價有差異）\n"
        "🔗 https://tckuo1988.github.io/family-investment-brief/"
    )
    if len(message) > 4900:
        stop("message too long")
    push(message)

if __name__ == "__main__":
    main()
