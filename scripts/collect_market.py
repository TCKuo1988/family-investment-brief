"""Write the quote inputs for one morning edition to stdout."""
import argparse
from datetime import date, datetime
import json
from urllib.error import URLError

from market_sessions import TAIPEI, expected_sessions
from update_twse import fetch_quotes as fetch_twse
from update_us import fetch_quotes as fetch_us


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-day", type=date.fromisoformat, default=datetime.now(TAIPEI).date())
    args = parser.parse_args()
    sessions = expected_sessions(args.report_day)
    try:
        tw_quotes = fetch_twse(sessions["tw"][0])
    except (ValueError, URLError, TimeoutError) as exc:
        tw_quotes = {"note": f"臺股來源更新失敗：{exc}"}
    print(json.dumps({
        "edition_date": args.report_day.isoformat(),
        "quotes": tw_quotes,
        "us_quotes": fetch_us(sessions["us"]),
    }, ensure_ascii=False, indent=2))
