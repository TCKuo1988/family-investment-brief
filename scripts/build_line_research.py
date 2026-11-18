#!/usr/bin/env python3
"""Generate a source-grounded, non-Yahoo US-led LINE market analysis using OpenAI Responses web search."""
import datetime as dt
import json
import os
import pathlib
import urllib.request
from zoneinfo import ZoneInfo

OUT=pathlib.Path("line_research.json")
today=dt.datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()
key=os.environ.get("OPENAI_API_KEY","").strip()
if not key:
    raise SystemExit("RESEARCH NOT READY: OPENAI_API_KEY secret is required; no canned advice will be sent.")

instructions="""你是臺灣家庭長期投資市場研究員。以繁體中文撰寫可直接放入 LINE 的晨報分析。
重點：70% 美股市場、Nasdaq/S&P500/SOX、NVDA、TSLA、SPCX、VOO、QQQ；20% 臺股大盤、006208、0050；10% 家庭決策。
家庭既定投入：比比每月10000元、本人0050每月3000元；不要建議因日波動停止定投。額外加碼需考量家庭備用金。
特別注意 SPCX 的標的性質必須查證，不得未查證就當作個股或臆測其產業。
使用網路搜尋最近 72 小時的可靠報導與第一手資料（公司 IR、官方經濟數據、Reuters/AP 等），對比至少兩個不同來源。
必須區分：已核實事實、分析人士看法、你自己的推論；不得把行情相關性說成已證實的因果。
不要杜撰報價、百分比或投資機構看法；行情由另一套已驗證價格程式提供，此處不提供數字。
以「昨天主要事件及市場驅動因素」、「修正性質判讀（正常波動／估值重估／基本面風險／尚無法判斷）」、「NVDA/TSLA/SPCX 投資論點變化」、「接下來 1~4 週與 3~12 個月應觀察的具體指標」、「對既有長期持有的影響」為主。
不可泛泛說『逢低分批買』『避免追高』，每個判斷須對應具體新事件或可驗證指標。不得直接給個人化確定買賣指令。
輸出嚴格 JSON 物件，欄位 headline,drivers,regime,holdings,near_term,medium_term,portfolio,sources。
除 sources 外皆為簡短繁體中文文字；drivers 與 holdings 要有具體事實，單欄最多 140 字。
sources 是 2~5 個物件陣列，每個含 title,url,date，必須是實際搜尋查得的 https URL；日期 YYYY-MM-DD。
如果資料不足，請回傳 headline 為 '資料不足'，其餘欄位解釋不足原因，不要猜測。"""
payload={"model":os.environ.get("OPENAI_RESEARCH_MODEL","gpt-5.1"),"tools":[{"type":"web_search"}],"input":[{"role":"system","content":instructions},{"role":"user","content":f"請查證截至臺灣時間 {today} 早上的最新台美股市場重大事件及投資論點，回傳 JSON。"}],"max_output_tokens":2200}
req=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(payload,ensure_ascii=False).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
with urllib.request.urlopen(req,timeout=150) as response:
    result=json.load(response)
parts=[]
for item in result.get("output",[]):
    if item.get("type")=="message":
        for c in item.get("content",[]):
            if c.get("type")=="output_text": parts.append(c.get("text",""))
raw="\n".join(parts).strip()
if raw.startswith("```"):
    raw=raw.split("\n",1)[-1].rsplit("```",1)[0].strip()
analysis=json.loads(raw)
required=("headline","drivers","regime","holdings","near_term","medium_term","portfolio")
if any(not isinstance(analysis.get(k),str) or len(analysis[k].strip())<12 for k in required):
    raise SystemExit("RESEARCH INVALID: missing analysis fields")
if analysis["headline"]=="資料不足":
    raise SystemExit("RESEARCH INVALID: insufficient verified information")
sources=analysis.get("sources")
if not isinstance(sources,list) or len(sources)<2 or any(not isinstance(s,dict) or not str(s.get("url","")).startswith("https://") or not s.get("date") for s in sources):
    raise SystemExit("RESEARCH INVALID: insufficient source links")
analysis["generated_on"]=today
OUT.write_text(json.dumps(analysis,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Research generated with",len(sources),"source links; no LINE message sent by this step.")
