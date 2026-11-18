#!/usr/bin/env python3
"""Preview or publish the validated report.json edition through LINE."""
import argparse
from datetime import date, datetime, time
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5

from market_sessions import TAIPEI
from validate_report import REPORT, load_report, validate_report

SITE = "https://tckuo1988.github.io/family-investment-brief/"
US_LABELS = (("sp500", "S&P 500"), ("nasdaq", "Nasdaq Composite"), ("sox", "費半 SOX"),
             ("NVDA", "NVDA"), ("TSLA", "TSLA"), ("SPCX", "SPCX"),
             ("VOO", "VOO"), ("QQQ", "QQQ"), ("TSM", "台積電 ADR"))
TW_LABELS = (("taiex", "加權"), ("2330", "台積電"), ("006208", "006208"), ("0050", "0050"))


def quote_lines(quotes, labels):
    for ticker, label in labels:
        item = quotes[ticker]
        close, change = item["close"], item["percent"]
        if close is None:
            yield f"{label}  {item['note']}"
        elif change is None:
            yield f"{label}  {close:,.2f}（漲跌待核實）"
        else:
            yield f"{label}  {close:,.2f}（{change:+.2f}%）"


def render(report):
    us, tw, notes = report["us_quotes"], report["quotes"], report["daily_research"]
    return "\n".join([
        f"📊 TCK 台美股晨報｜{report['edition_date']}",
        f"📉 市場強弱｜{notes['market_strength']}",
        *[f"🎯 {symbol}｜{notes[symbol]}" for symbol in ("NVDA", "TSLA", "SPCX")],
        f"🏠 家庭策略｜{report['action']}",
        f"🔗 完整晨報 {SITE}", "",
        f"📰 產業與新聞｜{notes['news']}",
        f"⏱ 1～4 週｜{notes['short_term']}",
        f"📅 3～12 個月｜{notes['medium_term']}",
        f"📌 006208／0050｜{notes['etf_watch']}", "",
        f"🇺🇸 美股｜{us['date']} 美東正規盤",
        *quote_lines(us, US_LABELS), "",
        f"🇹🇼 臺股｜{tw['date']} 正式收盤",
        *quote_lines(tw, TW_LABELS),
    ]).replace("\\r\\n", "\n").replace("\\n", "\n")


def send(message, edition):
    token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"].strip()
    group = os.environ["LINE_GROUP_ID"].strip()
    if not token or not group:
        raise ValueError("LINE credentials unavailable")
    key = uuid5(NAMESPACE_URL, f"{SITE}LINE/{edition}/{group}")
    request = Request(
        "https://api.line.me/v2/bot/message/push",
        data=json.dumps({"to": group, "messages": [{"type": "text", "text": message}]},
                        ensure_ascii=False).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "X-Line-Retry-Key": str(key)},
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise ValueError(f"Unexpected LINE HTTP {response.status}")
            result = f"LINE accepted HTTP 200 request_id={response.headers.get('X-Line-Request-Id')}"
    except HTTPError as exc:
        accepted = exc.headers.get("X-Line-Accepted-Request-Id")
        if exc.code == 409 and accepted:
            result = f"LINE already accepted HTTP 409 request_id={accepted}"
        else:
            raise ValueError(f"LINE HTTP {exc.code} request_id={exc.headers.get('X-Line-Request-Id')}") from None
    print(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--report-day", type=date.fromisoformat)
    args = parser.parse_args()
    now = datetime.now(TAIPEI)
    edition = args.report_day or now.date()
    if args.send and (edition != now.date() or now.time() < time(8, 10)):
        parser.error("Live delivery requires today's edition from 08:10 Asia/Taipei")
    checks = {
        "報告日期": edition.isoformat(),
        "研究與行情驗證": "未檢查",
        "Pages": "未檢查" if args.send else "預覽模式",
        "LINE": "未呼叫" if args.send else "預覽模式",
    }
    stage = "研究與行情驗證"
    try:
        raw = REPORT.read_bytes()
        report = load_report(raw)
        validate_report(report, edition)
        checks["臺股交易日"] = report["quotes"]["date"]
        checks["美股交易日"] = report["us_quotes"]["date"]
        message = render(report)
        if len(message.encode("utf-16-le")) // 2 > 5000:
            raise ValueError("LINE message exceeds 5000 UTF-16 units")
        Path("line_preview.txt").write_text(message + "\n", encoding="utf-8")
        checks[stage] = "通過"
        if not args.send:
            print(message)
            return
        stage = "Pages"
        with urlopen(Request(SITE + "report.json", headers={"Cache-Control": "no-cache"}), timeout=20) as response:
            if response.read() != raw:
                raise ValueError("GitHub Pages has not published this report revision")
        checks[stage] = "已發布相同報告"
        stage = "LINE"
        checks[stage] = send(message, edition)
    except (ValueError, OSError, KeyError, AttributeError, TypeError) as exc:
        checks[stage] = f"失敗：{exc}"
        raise SystemExit(f"LINE withheld or unsuccessful: {exc}") from None
    finally:
        if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as output:
                for label, value in checks.items():
                    value = " ".join(str(value).split())
                    print(f"- **{label}**　{value[:300]}", file=output)


if __name__ == "__main__":
    main()
