"""Validate the publishable morning report and its dated quote evidence."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from market_sessions import TAIPEI, expected_sessions
from update_us import US_KEYS

REPORT = Path(__file__).resolve().parents[1] / "report.json"
TW_KEYS = ("taiex", "2330", "006208", "0050")
RESEARCH_KEYS = ("market_strength", "news", "NVDA", "TSLA", "SPCX",
                 "short_term", "medium_term", "etf_watch")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return type(value) in (float, int) and math.isfinite(value)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def source(value, allowed_hosts):
    if not text(value):
        return False
    url = urlparse(value)
    return url.scheme == "https" and url.hostname in allowed_hosts


US_HOSTS = {"api.nasdaq.com", "stockanalysis.com", "fred.stlouisfed.org",
            "apnews.com", "indexes.nasdaqomx.com", "www.investing.com", "finance.google.com"}


def validate_report(data, edition):
    require(isinstance(data, dict), "Report must be a JSON object")
    require(data.get("edition_date") == edition.isoformat(), "Research edition date mismatch")
    require(str(data.get("report-date", ""))[:10].replace("/", "-") == edition.isoformat(),
            "Displayed report date mismatch")
    for key in ("summary", "status", "action"):
        require(text(data.get(key)), f"Missing {key}")
    sections = data.get("analysis_sections")
    require(isinstance(sections, list) and len(sections) >= 3, "Analysis sections incomplete")
    for section in sections:
        require(isinstance(section, dict) and text(section.get("title"))
                and text(section.get("conclusion")) and isinstance(section.get("points"), list)
                and len(section["points"]) and all(text(point) for point in section["points"]),
                "Analysis section incomplete")
    notes = data.get("daily_research", {})
    for key in RESEARCH_KEYS:
        require(text(notes.get(key)), f"Missing daily_research.{key}")

    sessions = expected_sessions(edition)
    for market, key, tickers in (("us", "us_quotes", US_KEYS), ("tw", "quotes", TW_KEYS)):
        quotes = data.get(key, {})
        day, previous_day = sessions[market]
        require(quotes.get("date") == day.isoformat(), f"{key}: expected {day}")
        as_of = datetime.fromisoformat(quotes.get("updated_at", ""))
        now = datetime.now(timezone.utc)
        require(as_of.tzinfo and day <= as_of.date() and as_of <= now + timedelta(minutes=5),
                f"{key}: invalid verification timestamp")
        if market == "us":
            require(quotes.get("basis") == "regular_unadjusted", "US closing basis missing")
        else:
            require(source(quotes.get("source"), {"www.twse.com.tw"}), "TWSE source missing")
        for ticker in tickers:
            item = quotes.get(ticker)
            require(isinstance(item, dict), f"{key}.{ticker}: quote missing")
            close, change = item.get("close"), item.get("percent")
            if close is None:
                require(market == "us" and ticker not in ("sp500", "nasdaq")
                        and change is None and text(item.get("note")), f"{ticker}: close required")
                continue
            require(number(close) and 0 < close < 1e9, f"{ticker}: invalid close")
            if market == "us":
                prior = item.get("previous_close")
                require(item.get("previous_date") == previous_day.isoformat()
                        and number(prior) and prior > 0, f"{ticker}: prior session close invalid")
                require(number(change) and abs(change - 100 * (close / prior - 1)) <= 0.00501,
                        f"{ticker}: percent inconsistent with unadjusted closes")
                for field in ("source", "cross_checked_with"):
                    if field == "source" or field in item:
                        require(source(item.get(field), US_HOSTS), f"{ticker}: invalid {field}")
            elif change is None:
                require(text(item.get("note")), f"{ticker}: missing change reason")
            else:
                delta = item.get("change")
                require(number(delta) and close - delta > 0 and number(change)
                        and abs(change - 100 * delta / (close - delta)) <= 0.00501,
                        f"{ticker}: invalid TWSE change")


def load_report(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Invalid JSON constant {value}")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-day", type=date.fromisoformat, default=datetime.now(TAIPEI).date())
    args = parser.parse_args()
    validate_report(load_report(REPORT.read_bytes()), args.report_day)
    print(f"Validated research and market sessions for {args.report_day}")
