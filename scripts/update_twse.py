#!/usr/bin/env python3
"""Fetch the dated TWSE closing bulletin for the morning edition."""
import argparse
from datetime import date, datetime, timezone
import json
import re
from urllib.request import Request, urlopen

from market_sessions import TAIPEI, expected_sessions

CODES = ("2330", "006208", "0050")


def fetch_quotes(day):
    url = ("https://www.twse.com.tw/exchangeReport/MI_INDEX"
           f"?response=json&date={day:%Y%m%d}&type=ALLBUT0999")
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25) as response:
        bulletin = json.load(response)
    if bulletin.get("stat") != "OK" or bulletin.get("date") != day.strftime("%Y%m%d"):
        raise ValueError(f"TWSE did not return the requested session {day}")

    def table(first_column):
        prefix = f"{day.year - 1911}年{day:%m月%d日}"
        match, = [t for t in bulletin["tables"] if t.get("title", "").startswith(prefix)
                  and (t.get("fields") or [""])[0] == first_column]
        return {row[0]: dict(zip(match["fields"], row)) for row in match["data"]}

    def number(value):
        return float(value.replace(",", ""))

    def quote(row, close_column, change_column):
        close = number(row[close_column])
        sign = re.sub("<[^>]*>", "", row["漲跌(+/-)"]).strip()
        if not 0 < close < 1e9:
            raise ValueError("Invalid TWSE closing price")
        if sign not in ("+", "-", ""):
            return {"close": close, "change": None, "percent": None,
                    "note": "交易所未列可比較漲跌（例如除息或參考價重設）"}
        change = number(row[change_column]) * (-1 if sign == "-" else 1)
        if close - change <= 0:
            raise ValueError("Invalid TWSE reference price")
        return {"close": close, "change": change,
                "percent": round(100 * change / (close - change), 2)}

    stocks = table("證券代號")
    index = table("指數")["發行量加權股價指數"]
    return {
        "date": day.isoformat(), "source": url,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "taiex": quote(index, "收盤指數", "漲跌點數"),
        **{code: quote(stocks[code], "收盤價", "漲跌價差") for code in CODES},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-day", type=date.fromisoformat, default=datetime.now(TAIPEI).date())
    args = parser.parse_args()
    print(json.dumps(fetch_quotes(expected_sessions(args.report_day)["tw"][0]), ensure_ascii=False, indent=2))
