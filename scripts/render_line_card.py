"""Render a mobile LINE preview from the public report."""
import argparse
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from validate_report import load_report, validate_report

FONT = Path("/usr/share/fonts/opentype/noto")
US = ("NVDA", "TSLA", "SPCX", "QQQ", "VOO", "SOXX", "TSM")
TW = ("2330", "006208")


def render(report, edition):
    published = report["edition_date"]
    issue = None
    if published != edition.isoformat():
        issue = f"網站目前為 {published} 版。"
    else:
        try:
            validate_report(report, edition)
        except (ValueError, KeyError, AttributeError, TypeError):
            issue = "本期晨報未通過資料驗證。"

    image = Image.new("RGB", (760, 1050), "#EDF2F6")
    draw = ImageDraw.Draw(image)

    def text(x, y, value, size=30, color="#152C40", bold=False, width=660):
        weight = "Bold" if bold else "Regular"
        font = ImageFont.truetype(str(FONT / f"NotoSansCJK-{weight}.ttc"), size, index=3)
        if font.getlength(value) > width:
            while font.getlength(value + "…") > width:
                value = value[:-1]
            value += "…"
        draw.text((x, y), value, fill=color, font=font, anchor="lt")

    def box(x, y, width, height, fill):
        draw.rounded_rectangle((x, y, x + width, y + height), radius=22, fill=fill)

    box(22, 22, 716, 190, "#142D43")
    text(48, 49, "TCK 家庭投資晨報", 45, "white", True)
    text(48, 114, f"{edition:%m/%d}  08:10 ｜ LINE 預覽", 28, "#BFD4E4")
    text(48, 163, "今日晨報待更新" if issue else "今日晨報已更新", 27, "#FBE5BA")

    box(22, 230, 716, 165, "white")
    text(48, 253, "今天市場在看什麼", 33, bold=True)
    summary = "等待今日已驗證的晨報。" if issue else report["summary"]
    text(48, 312, " ".join(summary.split()), 27)

    box(22, 413, 716, 323, "white")
    box(22, 754, 716, 190, "white")
    for top, title, group, symbols in (
        (413, "美股與半導體", "us_quotes", US),
        (754, "台股觀察", "quotes", TW),
    ):
        quotes = report.get(group) or {}
        text(48, top + 22, title, 33, bold=True)
        prefix = "網站最近資料" if issue else "交易日"
        text(48, top + 75, f"{prefix}  {quotes.get('date') or '未取得'}", 26)
        for index, symbol in enumerate(symbols):
            label = {"2330": "台積電", "TSM": "台積電 ADR"}.get(symbol, symbol)
            quote = quotes.get(symbol) or {}
            percent = None if issue else quote.get("percent")
            value = f"{percent:+.2f}%" if percent is not None else "—"
            x, y = 48 + index % 3 * 222, top + 124 + index // 3 * 55
            box(x, y, 205, 43, "#EDF2F6")
            text(x + 10, y + 8, f"{label}  {value}", 22, bold=True, width=185)

    text(48, 962, issue or "— 表示該標的行情尚未取得。", 27)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-day", type=date.fromisoformat)
    args = parser.parse_args()
    edition = args.report_day or datetime.now(ZoneInfo("Asia/Taipei")).date()
    report_path = Path(__file__).resolve().parents[1] / "report.json"
    render(load_report(report_path.read_bytes()), edition).save("line_preview.png")


if __name__ == "__main__":
    main()
