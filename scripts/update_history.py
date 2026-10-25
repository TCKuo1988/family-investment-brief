#!/usr/bin/env python3
"""Fetch recent daily closes for public market cards. No private portfolio data."""
import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT=pathlib.Path(__file__).resolve().parents[1]
PATH=ROOT/"history.json"
SYMBOLS={
    "TAIEX":"%5ETWII",
    "006208":"006208.TW",
    "0050":"0050.TW",
    "VOO":"VOO",
    "QQQ":"QQQ",
    "NVDA":"NVDA",
    "TSLA":"TSLA",
    "SPCX":"SPCX",
}
def yahoo_history(ticker):
    url="https://query1.finance.yahoo.com/v8/finance/chart/"+ticker+"?"+urllib.parse.urlencode({"range":"8mo","interval":"1d"})
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; TCK-public-market-history/1.0)","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=18) as response:
        data=json.load(response)
    result=(data.get("chart",{}).get("result") or [None])[0]
    if not result: raise ValueError("No chart data: "+str(data.get("chart",{}).get("error")))
    stamps=result.get("timestamp") or []
    candles=(result.get("indicators",{}).get("quote") or [{}])[0].get("close") or []
    zone=ZoneInfo(result.get("meta",{}).get("exchangeTimezoneName") or "UTC")
    rows={}
    now_local=dt.datetime.now(zone)
    # Exclude an unfinished current market session; chart values are closing prices only.
    min_close_hour=16 if "Taipei" in str(zone) else 17
    for ts,close in zip(stamps,candles):
        if close is None:continue
        value=round(float(close),4)
        if not (0<value<1_000_000_000):continue
        session_date=dt.datetime.fromtimestamp(ts,zone).date()
        if session_date==now_local.date() and now_local.hour<min_close_hour:continue
        if session_date>now_local.date():continue
        day=session_date.isoformat()
        rows[day]={"date":day,"close":value}
    return list(rows.values())[-165:]

def run():
    d=json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else {"series":{}}
    d.setdefault("series",{})
    today=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    successes=0
    for symbol,ticker in SYMBOLS.items():
        try:
            values=yahoo_history(ticker)
            if len(values)<95:raise ValueError("fewer than 95 closes; six-month history not verified")
            d["series"][symbol]=values
            successes+=1
            print(f"{symbol}: {len(values)} closes through {values[-1]['date']}")
        except (OSError,ValueError,TypeError,KeyError) as e:
            print(f"WARNING {symbol}: {e}; preserving any previous valid history")
        time.sleep(1)
    # TWSE-listed ETFs may carry forward stale prices on a market holiday.
    # Only retain dates when the TWSE benchmark itself has a trading session.
    benchmark=d["series"].get("TAIEX",[])
    if benchmark:
        trading_days={row["date"] for row in benchmark}
        for symbol in ("006208","0050"):
            rows=d["series"].get(symbol,[])
            if rows:
                clean=[row for row in rows if row["date"] in trading_days]
                if clean and len(clean)!=len(rows):
                    print(f"{symbol}: removed {len(rows)-len(clean)} non-trading-day quotes")
                    d["series"][symbol]=clean
    if successes:
        d["updated_at"]=today
        PATH.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    else:
        print("WARNING: No history updated; keeping previous JSON unchanged")

if __name__=="__main__":run()
