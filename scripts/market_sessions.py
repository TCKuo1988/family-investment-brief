"""Regular sessions expected in the 08:00 Asia/Taipei edition."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import exchange_calendars as calendars

TAIPEI = ZoneInfo("Asia/Taipei")


def expected_sessions(report_day: date):
    cutoff = datetime.combine(report_day, time(8), TAIPEI)
    result = {}
    for market, exchange in (("us", "XNYS"), ("tw", "XTAI")):
        calendar = calendars.get_calendar(exchange)
        day = cutoff.astimezone(calendar.tz).date()
        session = calendar.date_to_session(day, direction="previous")
        if calendar.session_close(session) > cutoff:
            session = calendar.previous_session(session)
        result[market] = (session.date(), calendar.previous_session(session).date())
    return result
