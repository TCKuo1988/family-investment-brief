#!/usr/bin/env python3
"""Manual LINE connectivity test. Sends no market or private financial data."""
import json
import os
import urllib.error
import urllib.request

token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
group = os.environ.get("LINE_GROUP_ID", "").strip()
if not token or not group:
    raise SystemExit("Missing LINE secrets in GitHub Actions")
message = "✅ TCK 投資晨報｜LINE 串接測試成功\n這是一則手動測試訊息，非正式市場晨報。"
payload = json.dumps({"to": group, "messages": [{"type": "text", "text": message}]}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    "https://api.line.me/v2/bot/message/push",
    data=payload,
    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status != 200:
            raise SystemExit("LINE returned unexpected status")
except urllib.error.HTTPError as exc:
    raise SystemExit(f"LINE API HTTP {exc.code}; response body suppressed") from None
print("LINE accepted test push; confirm delivery in LINE group.")
