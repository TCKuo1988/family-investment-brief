"""Render a mobile LINE preview from the public report."""
import argparse
from datetime import date, datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from market_sessions import expected_sessions
from validate_report import load_report, validate_report

FONT = Path("/usr/share/fonts/opentype/noto")
US = ("NVDA", "TSLA", "SPCX", "QQQ", "VOO", "SOXX", "TSM")
TW = ("2330", "006208")


def render(report, edition, market=None, *, preview=True):
    published = report["edition_date"]
    issue = None
    if published != edition.isoformat():
        issue = f"網站目前為 {published} 版。"
    else:
        try:
            validate_report(report, edition)
        except (ValueError, KeyError, AttributeError, TypeError):
            issue = "本期晨報未通過資料驗證。"

    market = market or {}
    if market.get("edition_date") != edition.isoformat():
        market = {}
    sessions = expected_sessions(edition) if market else {}

    image = Image.new("RGB", (760, 1670 if not issue else 810), "#F0F3F6")
    draw = ImageDraw.Draw(image)
    ink, muted, accent, navy = "#14293D", "#486075", "#116464", "#10263A"

    def font(size, bold=False):
        weight = "Bold" if bold else "Regular"
        return ImageFont.truetype(str(FONT / f"NotoSansCJK-{weight}.ttc"), size, index=3)

    def text(x, y, value, size=30, color=ink, bold=False):
        draw.text((x, y), value, fill=color, font=font(size, bold), anchor="lt")

    def paragraph(x, y, value, *, lines=3, size=27, width=650):
        face = font(size)
        rows, row = [], ""
        for part in re.findall(r"[A-Za-z0-9.+%/−-]+|.", " ".join(value.split())):
            if row and face.getlength(row + part) > width:
                rows.append(row.rstrip())
                row = part.lstrip()
            else:
                row += part
        if row:
            rows.append(row.rstrip())
        if len(rows) > lines:
            tail = rows[lines - 1]
            while face.getlength(tail + "…") > width:
                tail = tail[:-1]
            rows[lines - 1] = tail.rstrip() + "…"
        for index, line in enumerate(rows[:lines]):
            text(x, y + index * (size + 10), line, size, muted)

    def panel(top, height):
        draw.rounded_rectangle((24, top, 736, top + height), radius=20, fill="white")

    def quote_group(group, market_key):
        original = report.get(group) or {}
        current = market.get(group) or {}
        session = sessions.get(market_key)
        if not issue:
            return original, original.get("date")
        if session and current.get("date") == session[0].isoformat():
            return current, current["date"]
        return {}, None

    def change(quotes, symbol):
        percent = (quotes.get(symbol) or {}).get("percent")
        if percent is None:
            return "—", muted
        color = "#A13B42" if percent > 0 else "#116464" if percent < 0 else muted
        return f"{percent:+.2f}%", color

    us, us_day = quote_group("us_quotes", "us")
    tw, tw_day = quote_group("quotes", "tw")

    draw.rectangle((0, 0, 760, 150), fill=navy)
    draw.rectangle((0, 148, 760, 153), fill="#408F86")
    text(42, 27, "TCK 家庭投資晨報", 45, "white", True)
    text(44, 93, f"{edition:%Y/%m/%d}" + ("  ｜  LINE 預覽" if preview else ""), 26, "#BFD4E4")

    notes = report.get("daily_research") or {}
    panel(175, 405 if not issue else 135)
    text(48, 196, "市場解讀", 33, accent, True)
    if issue:
        paragraph(48, 249, "研究待更新。" + issue, lines=1)
    else:
        paragraph(48, 245, report["summary"], lines=2)
        paragraph(48, 329, notes["news"], lines=2)
        text(48, 414, "對台股大盤的影響", 30, accent, True)
        outlook = report.get("market_outlook") or {}
        analysis = report["analysis_sections"][0]["points"]
        impact = analysis[1] if len(analysis) > 1 else outlook.get("summary") or notes["short_term"]
        paragraph(48, 457, impact, lines=3)

    top = 600 if not issue else 330
    panel(top, 430)
    text(48, top + 22, "台美股主要行情", 33, accent, True)
    for row, (quotes, day, market_name, symbols) in enumerate((
        (us, us_day, "美股", (("sp500", "S&P 500"), ("nasdaq", "Nasdaq"), ("TSM", "台積電 ADR"),
                           ("QQQ", "QQQ"), ("VOO", "VOO"), ("SOXX", "SOXX"))),
        (tw, tw_day, "台股", (("taiex", "加權指數"), ("2330", "台積電"), ("006208", "006208"))),
    )):
        y = top + (77 if row == 0 else 280)
        text(48, y, f"{market_name}交易日  {day or '資料待取得'}", 25, muted, True)
        for index, (symbol, label) in enumerate(symbols):
            x, line_y = 48 + index % 3 * 222, y + 43 + index // 3 * 71
            draw.rounded_rectangle((x, line_y, x + 211, line_y + 62), radius=10, fill="#EDF2F6")
            value, color = change(quotes, symbol)
            text(x + 10, line_y + 8, label, 20, muted)
            text(x + 10, line_y + 32, value, 23, color, True)

    if not issue:
        panel(1050, 545)
        text(48, 1071, "美股個股觀察", 33, accent, True)
        for index, symbol in enumerate(("NVDA", "TSLA", "SPCX")):
            y = 1130 + index * 143
            if index:
                draw.line((48, y - 15, 712, y - 15), fill="#DCE5EA", width=2)
            value, color = change(us, symbol)
            text(48, y, symbol, 29, bold=True)
            text(190, y, value, 29, color, True)
            # The headline already shows the close-to-close move.
            observation = re.sub(r"^收盤[^。]*。\s*", "", notes[symbol], count=1)
            paragraph(48, y + 45, observation, lines=2)
        text(48, 1620, "漲跌為收盤比較 ｜ — 表示當期行情待核實", 23, muted)
    else:
        text(48, 777, "— 表示當期行情待核實", 23, muted)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-day", type=date.fromisoformat)
    parser.add_argument("--market-quotes", type=Path)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    edition = args.report_day or datetime.now(ZoneInfo("Asia/Taipei")).date()
    report_path = Path(__file__).resolve().parents[1] / "report.json"
    market = load_report(args.market_quotes.read_bytes()) if args.market_quotes else None
    render(load_report(report_path.read_bytes()), edition, market, preview=not args.live).save("line_preview.png")


if __name__ == "__main__":
    main()
