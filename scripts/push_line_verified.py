#!/usr/bin/env python3
"""LINE brief: TWSE official OpenAPI + Stooq US daily CSV; never Yahoo."""
import csv
import datetime as dt
import io
import json
import math
import os
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

TW = ZoneInfo("Asia/Taipei")
STOOQ = {"VOO":"voo.us","QQQ":"qqq.us","NVDA":"nvda.us","TSLA":"tsla.us","SPCX":"spcx.us"}
TWSE = "https://openapi.twse.com.tw/v1"

def fail(message):
    raise SystemExit("SKIP LINE: " + message)

def get(url):
    request = urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; TCK-Investment-Brief/2.0)","Accept":"*/*"})
    with urllib.request.urlopen(request,timeout=25) as response:
        return response.read().decode("utf-8-sig")

def number(value):
    return float(str(value).replace(",","").replace("+","").strip())

def roc(value):
    value = str(value).replace("/","").replace("-","")
    if len(value)!=7 or not value.isdigit(): fail("invalid TWSE date")
    return dt.date(int(value[:3])+1911,int(value[3:5]),int(value[5:]))

def quote(close, change):
    if not math.isfinite(close) or not math.isfinite(change) or close<=0 or close-change<=0:
        fail("invalid market price")
    return (close,100*change/(close-change))

def taiwan():
    stocks=json.loads(get(TWSE+"/exchangeReport/STOCK_DAY_ALL"))
    indices=json.loads(get(TWSE+"/exchangeReport/MI_INDEX"))
    if not isinstance(stocks,list) or not isinstance(indices,list): fail("invalid TWSE response")
    out={}
    dates=[]
    for code in ("006208","0050","2330"):
        hits=[r for r in stocks if str(r.get("Code","")).strip()==code]
        if len(hits)!=1: fail("TWSE missing "+code)
        row=hits[0]
        dates.append(roc(row["Date"]))
        out[code]=quote(number(row["ClosingPrice"]),number(row["Change"]))
    hits=[r for r in indices if r.get("指數")=="發行量加權股價指數"]
    if len(hits)!=1: fail("TWSE index missing")
    row=hits[0]
    dates.append(roc(row["日期"]))
    change=number(row["漲跌點數"])*(-1 if row.get("漲跌")=="-" else 1)
    out["TAIEX"]=quote(number(row["收盤指數"]),change)
    if len(set(dates))!=1: fail("TWSE quote dates inconsistent")
    return dates[0],out

def us_market():
    end=dt.datetime.now(dt.timezone.utc).date()
    start=end-dt.timedelta(days=16)
    result={}
    dates=[]
    for symbol,ticker in STOOQ.items():
        url="https://stooq.com/q/d/l/?"+urllib.parse.urlencode({"s":ticker,"d1":start.strftime("%Y%m%d"),"d2":end.strftime("%Y%m%d"),"i":"d"})
        rows=list(csv.DictReader(io.StringIO(get(url))))
        valid=[]
        for row in rows:
            try:
                date=dt.date.fromisoformat(row["Date"])
                close=float(row["Close"])
                if math.isfinite(close) and close>0 and date<end+dt.timedelta(days=1):
                    valid.append((date,close))
            except (KeyError,ValueError,TypeError):
                continue
        valid.sort()
        if len(valid)<2 or valid[-2][0]>=valid[-1][0]: fail("US quote missing "+symbol)
        date,close=valid[-1]
        dates.append(date)
        result[symbol]=(close,100*(close/valid[-2][1]-1))
    if len(set(dates))!=1: fail("US symbols have different dates")
    return dates[0],result

def prior_weekday(day):
    day-=dt.timedelta(days=1)
    while day.weekday()>=5: day-=dt.timedelta(days=1)
    return day

def main():
    now=dt.datetime.now(TW)
    manual=os.environ.get("LINE_MANUAL_TODAY","").lower() in ("true","1","yes")
    if now.weekday()>=5: fail("weekend")
    if not manual and (now.hour!=8 or not 5<=now.minute<=35): fail("outside scheduled send window")
    tw_day,tw=taiwan()
    us_day,us=us_market()
    expected=prior_weekday(now.date())
    if tw_day!=expected or us_day!=expected:
        fail(f"not latest expected session: TWSE {tw_day}, US {us_day}, expected {expected}; holidays require separate verification")
    def fmt(name,data):
        price,pct=data
        sign="🔴" if pct>0 else "🟢" if pct<0 else "⚪"
        return f"{sign} {name}  {price:,.2f}（{pct:+.2f}%）"
    tai_pct=tw["TAIEX"][1]
    tech_pct=us["QQQ"][1]
    if tai_pct<=-2 or tech_pct<=-2:
        short="市場波動偏高；額外加碼採分批方式，優先保留家庭備用金。"
    elif tai_pct>=2 and tech_pct>=2:
        short="市場同步反彈；避免追高，按既定投入節奏執行。"
    else:
        short="依原定計畫投入；額外加碼須確認可動用資金。"
    message="\n".join([
        f"📊 TCK 台美股晨報｜{now:%m/%d}",
        "",
        f"🇹🇼 台股｜{tw_day:%m/%d} 收盤",
        fmt("加權",tw["TAIEX"]),
        fmt("台積電",tw["2330"]),
        fmt("006208",tw["006208"]),
        fmt("0050",tw["0050"]),
        "",
        f"🇺🇸 美股｜{us_day:%m/%d} 收盤",
        *[fmt(symbol,us[symbol]) for symbol in ("NVDA","TSLA","VOO","QQQ","SPCX")],
        "",
        "💡 短期｜"+short,
        "🧭 中期｜以核心 ETF 為主，檢視科技股集中度及教育、車貸等家庭現金需求。",
        "",
        "🔗 https://tckuo1988.github.io/family-investment-brief/",
    ])
    token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN","").strip()
    group=os.environ.get("LINE_GROUP_ID","").strip()
    if not token or not group: fail("LINE secrets missing")
    payload=json.dumps({"to":group,"messages":[{"type":"text","text":message}]},ensure_ascii=False).encode()
    request=urllib.request.Request("https://api.line.me/v2/bot/message/push",data=payload,method="POST",headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    with urllib.request.urlopen(request,timeout=20) as response:
        if response.status!=200: fail("LINE push failed")
    print(f"LINE sent; TWSE {tw_day}; Stooq {us_day}")

if __name__=="__main__":
    main()
