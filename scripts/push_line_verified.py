#!/usr/bin/env python3
"""Render a compact LINE digest from the same published report.json; no Yahoo or paid AI API."""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request
from zoneinfo import ZoneInfo

def fail(message):
    raise SystemExit("SKIP LINE: "+message)

def main():
    now=dt.datetime.now(ZoneInfo("Asia/Taipei"))
    report=json.loads(Path("report.json").read_text(encoding="utf-8"))
    report_day=str(report.get("report-date",""))[:10].replace("/","-")
    if report_day!=now.date().isoformat(): fail("today's research report has not been published")
    sections=report.get("analysis_sections",[])
    if not report.get("summary") or not isinstance(sections,list) or len(sections)<3:
        fail("research sections incomplete")
    def fmt(value,kind="close"):
        return f"{value:,.2f}" if isinstance(value,(int,float)) else "待核實"
    def pct(value):
        return f"{value:+.2f}%" if isinstance(value,(int,float)) else "待核實"
    def line(label,item):
        if not isinstance(item,dict): item={}
        return f"{label}  {fmt(item.get('close'))}（{pct(item.get('percent'))}）"
    tw=report.get("quotes",{})
    us=report.get("us_quotes",{})
    if not tw.get("date") or not us.get("date"): fail("market dates missing")
    if tw["date"]!=us["date"]: fail("market dates inconsistent; do not blend sessions")
    if tw["date"]!=str(now.date()-dt.timedelta(days=1)):
        fail("market prices not from yesterday; holiday handling requires review")
    if not all(isinstance(tw.get(s,{}).get("close"),(int,float)) for s in ("taiex","2330","006208","0050")):
        fail("TWSE quotes incomplete")
    # US holdings may be missing; never fill from a different day.
    stocks={s.get("ticker"):s for s in report.get("stocks",[]) if isinstance(s,dict)}
    lines=[
        f"📊 TCK 台美股晨報｜{now:%m/%d}",
        f"🇺🇸 美股｜{us['date'][5:]} 收盤",
        *[line(t,{"close":stocks.get(t,{}).get("price"),"percent":stocks.get(t,{}).get("change_percent")}) for t in ("NVDA","TSLA","SPCX","VOO","QQQ")],
        "",
        f"🇹🇼 臺股｜{tw['date'][5:]} 收盤",
        *[line(label,tw.get(key)) for label,key in (("加權","taiex"),("台積電","2330"),("006208","006208"),("0050","0050"))],
        "",
        "📰 市場焦點｜"+str(report["summary"]),
        "📉 波動判讀｜"+str(sections[0].get("conclusion","")),
        "🎯 美股論點｜"+str(sections[1].get("conclusion","")),
        "⏱ 短中期｜"+str(sections[-1].get("conclusion","")),
        "🏠 投資策略｜"+str(report.get("action","")),
        "",
        "🔗 https://tckuo1988.github.io/family-investment-brief/"
    ]
    message="\n".join(lines)
    if len(message)>4500: fail("LINE digest too long")
    Path("line_preview.txt").write_text(message+"\n",encoding="utf-8")
    if os.environ.get("LINE_DRY_RUN","").lower() in ("true","1","yes"):
        print(message)
        print("PREVIEW ONLY: no LINE push")
        return
    if any(stocks.get(t,{}).get("price") is None for t in ("NVDA","TSLA","SPCX","VOO","QQQ")):
        fail("US quotes incomplete; preview available, live push withheld")
    token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN","").strip()
    group=os.environ.get("LINE_GROUP_ID","").strip()
    if not token or not group: fail("LINE credentials unavailable")
    req=urllib.request.Request("https://api.line.me/v2/bot/message/push",data=json.dumps({"to":group,"messages":[{"type":"text","text":message}]},ensure_ascii=False).encode(),method="POST",headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as response:
        if response.status!=200: fail("LINE push rejected")
    print("LINE sent from report.json for",report_day)

if __name__=="__main__":
    main()
