#!/usr/bin/env python3
"""Collect dated US regular closes without using Yahoo or adjusted prices."""
import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import unescape
import json
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import exchange_calendars as calendars

SECURITIES = {
    "NVDA": ("NVDA", "stocks", "stocks"), "TSLA": ("TSLA", "stocks", "stocks"),
    "SPCX": ("SPCX", "stocks", "stocks"), "VOO": ("VOO", "etf", "etf"),
    "QQQ": ("QQQ", "etf", "etf"), "TSM": ("TSM", "stocks", "stocks"),
}
INDEXES = {"sp500": ("SPX", "SP500"), "nasdaq": ("COMP", "NASDAQCOM"), "sox": ("SOX", None)}
US_KEYS = tuple(INDEXES) + tuple(SECURITIES)


def download(url, referrer=None):
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/132 Safari/537.36"}
    if referrer:
        headers.update({"Referer": referrer, "Accept": "application/json"})
    with urlopen(Request(url, headers=headers), timeout=12) as response:
        return response.read().decode("utf-8")


def number(value):
    price = float(value.replace("$", "").replace(",", ""))
    if not 0 < price < 1e9:
        raise ValueError("Invalid US closing price")
    return price


def nasdaq(symbol, asset, dates):
    query = urlencode({"assetclass": asset, "fromdate": dates[1] - timedelta(days=1),
                       "todate": dates[0] + timedelta(days=1)})
    url = f"https://api.nasdaq.com/api/quote/{symbol}/historical?{query}"
    data = json.loads(download(url, "https://www.nasdaq.com/"))["data"]
    if not data or data["symbol"].upper() != symbol:
        raise ValueError("Nasdaq symbol unavailable")
    prices = {
        datetime.strptime(row["date"], "%m/%d/%Y").date(): row["close"]
        for row in data["tradesTable"]["rows"]
    }
    return tuple(number(prices[day]) for day in dates), url


def nasdaq_index_close(symbol, dates):
    url = f"https://api.nasdaq.com/api/quote/{symbol}/info?assetclass=index"
    data = json.loads(download(url, "https://www.nasdaq.com/"))["data"]
    primary = data["primaryData"]
    stamp = datetime.strptime(primary["lastTradeTimestamp"], "%b %d, %Y").date()
    if data["symbol"] != symbol or data["marketStatus"] != "Closed" or stamp != dates[0]:
        raise ValueError("Nasdaq index close not for the requested session")
    return (number(primary["lastSalePrice"]),
            number(data["keyStats"]["previousclose"]["value"])), url


def stockanalysis(symbol, asset, dates):
    url = f"https://stockanalysis.com/{asset}/{symbol.lower()}/history/"
    html = download(url)
    rows = re.findall(r"<tr\b[^>]*>.*?</tr>", html, re.S)
    headers = re.findall(r"<th\b[^>]*>([^<]*)</th>", rows[0])
    date_column, close_column = headers.index("Date"), headers.index("Close")
    prices = {}
    for row in rows[1:]:
        columns = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S)
        if len(columns) != len(headers):
            continue
        day = datetime.strptime(columns[date_column], "%b %d, %Y").date()
        prices[day] = columns[close_column]
    return tuple(number(prices[day]) for day in dates), url


def investing(slug, dates):
    url = f"https://www.investing.com/indices/{slug}-historical-data"
    html = download(url)
    prices = {}
    for row in re.findall(r"<tr\b[^>]*>.*?</tr>", html, re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S)
        if len(cells) != 7 or "<time " not in cells[0]:
            continue
        raw_date, price = (unescape(re.sub(r"<[^>]*>", "", cell)) for cell in cells[:2])
        day = datetime.strptime(raw_date, "%b %d, %Y").date()
        prices[day] = price
    return tuple(number(prices[day]) for day in dates), url


def fred(series, dates):
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urlencode(
        {"id": series, "cosd": dates[1], "coed": dates[0]}
    )
    rows = csv.reader(download(url).splitlines())
    if next(rows)[1] != series:
        raise ValueError("FRED series unavailable")
    prices = dict(rows)
    return tuple(number(prices[day.isoformat()]) for day in dates), url


def google_sp500(dates):
    url = "https://finance.google.com/finance/quote/.INX:INDEXSP"
    html = download(url)
    match = re.search(
        r'\["[^"]+",\["\.INX","INDEXSP"\],"[^"]+",1,null,'
        r'\[([0-9.]+),[^\]]+\],null,([0-9.]+),null,null,null,\[(\d+)\],"America/New_York"',
        html,
    )
    if not match:
        raise ValueError("Google Finance index response changed")
    close, previous, timestamp = match.groups()
    as_of = datetime.fromtimestamp(int(timestamp), timezone.utc)
    calendar = calendars.get_calendar("XNYS")
    session_close = calendar.session_close(dates[0])
    if as_of.astimezone(calendar.tz).date() != dates[0] or not session_close <= as_of <= session_close + timedelta(hours=5):
        raise ValueError("Google Finance quote is not a dated closing value")
    return (number(close), number(previous)), url


def resolve(key, dates):
    if key in INDEXES:
        symbol, series = INDEXES[key]
        providers = [(nasdaq, (symbol, "index"))] if key != "sp500" else [(google_sp500, ())]
        if key in ("sox", "nasdaq"):
            providers.append((nasdaq_index_close, (symbol,)))
        if key == "sox":
            providers.append((investing, ("phlx-semiconductor",)))
        elif key == "nasdaq":
            providers.append((investing, ("nasdaq-composite",)))
        if series:
            providers.insert(0, (fred, (series,)))
    else:
        symbol, asset, path = SECURITIES[key]
        providers = [(nasdaq, (symbol, asset)), (stockanalysis, (symbol, path))]

    results = []
    for provider, arguments in providers:
        try:
            results.append(provider(*arguments, dates))
        except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration) as exc:
            print(f"{key} {provider.__name__}: {type(exc).__name__}: {exc}", file=sys.stderr)

    if not results:
        return {"close": None, "percent": None, "note": "預期交易日收盤價未核實"}
    prices, source = results[0]
    if any(abs(a - b) > (0.051 if key == "sox" and "investing.com" in other_url else 0.011)
           for other, other_url in results[1:] for a, b in zip(prices, other)):
        return {"close": None, "percent": None, "note": "來源報價不一致",
                "candidate_sources": [url for _, url in results]}
    close, prior = prices
    result = {"close": close, "previous_close": prior, "previous_date": dates[1].isoformat(),
              "percent": round(100 * (close / prior - 1), 2), "source": source}
    if "investing.com/indices/phlx-semiconductor" in source:
        result["note"] = "來源以小數 1 位公布"
    if len(results) > 1:
        result["cross_checked_with"] = results[1][1]
    if abs(result["percent"]) >= 35 and len(results) == 1:
        return {"close": None, "percent": None, "note": "價格大幅變動，等待第二來源確認"}
    return result


def fetch_quotes(dates):
    with ThreadPoolExecutor(max_workers=5) as executor:
        rows = dict(zip(US_KEYS, executor.map(lambda key: resolve(key, dates), US_KEYS)))
    return {"date": dates[0].isoformat(), "currency": "USD", "basis": "regular_unadjusted",
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **rows}
