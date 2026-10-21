#!/usr/bin/env python3
"""從臺灣證券交易所 OpenAPI 更新公開市場價格，不碰私人持股資料。"""
import json, urllib.request, datetime, pathlib, sys

BASE='https://openapi.twse.com.tw/v1'
ROOT=pathlib.Path(__file__).resolve().parents[1]

def fetch(path):
    req=urllib.request.Request(BASE+path, headers={'User-Agent':'TCK-Investment-Brief/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as r: return json.load(r)

def num(s): return float(str(s).replace(',','').replace('+','').strip())

def date_roc(s):
    s=str(s).replace('/','').replace('-','')
    if len(s)!=7 or not s.isdigit(): raise ValueError('日期格式異常: '+s)
    return f'{int(s[:3])+1911:04d}-{s[3:5]}-{s[5:7]}'

def main():
    stocks=fetch('/exchangeReport/STOCK_DAY_ALL')
    index=fetch('/exchangeReport/MI_INDEX')
    if not isinstance(stocks,list) or not isinstance(index,list): raise ValueError('API資料格式異常')
    quotes={}
    for code in ['006208','0050']:
        hits=[r for r in stocks if str(r.get('Code','')).strip()==code]
        if len(hits)!=1: raise ValueError('ETF報價缺漏: '+code)
        r=hits[0]; close=num(r['ClosingPrice']); change=num(r.get('Change','0'))
        if close<=0: raise ValueError('ETF價格異常: '+code)
        quotes[code]={'close':close,'change':change,'percent':round(change/(close-change)*100,2) if close!=change else None}
        quotes.setdefault('date',date_roc(r['Date']))
        if date_roc(r['Date'])!=quotes['date']: raise ValueError('ETF日期不一致')
    hits=[r for r in index if r.get('指數')=='發行量加權股價指數']
    if len(hits)!=1: raise ValueError('加權指數缺漏')
    market=hits[0]; market_date=date_roc(market['日期'])
    if market_date!=quotes['date']: raise ValueError('指數和ETF資料日期不一致')
    today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
    dt=datetime.date.fromisoformat(quotes['date'])
    if dt>today or (today-dt).days>5: raise ValueError('行情日期已過期，不更新')
    datafile=ROOT/'report.json'; report=json.loads(datafile.read_text(encoding='utf8'))
    old=report.get('quotes',{}).get('date','')
    if old and old>quotes['date']: raise ValueError('新行情日期早於既有資料')
    if old==quotes['date']:
        print('最新交易日未改變，略過'); return
    quote_change=num(market['漲跌點數']) * (-1 if market.get('漲跌')=='-' else 1)
    quotes['taiex']={'close':num(market['收盤指數']),'change':quote_change,'percent':round(quote_change/(num(market['收盤指數'])-quote_change)*100,2)}
    report['quotes']=quotes
    # 不覆蓋既有晨報分析日期與策略評論，以免假裝當日分析
    report['market-value']=f"{quotes['taiex']['close']:,.2f}"
    report['market-change']=f"{quote_change:+,.2f}（{quotes['taiex']['percent']:+.2f}%）"
    report['status']=f"最新官方行情：{quotes['date']} 收盤｜晨報分析仍為 {report.get('report-date','歷史日期')}，尚未自動更新"
    report['market-note']=f"以上為 {quotes['date']} 官方收盤行情。下方趨勢結論屬既有歷史分析，不得視為當日最新判斷。"
    datafile.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('已更新官方行情至',quotes['date'])

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('行情更新失敗，保留既有報價與標示:',exc,file=sys.stderr)
        sys.exit(1)
