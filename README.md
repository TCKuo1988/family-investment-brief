# TCK 家庭投資晨報

公開網站保留最後發布的 `report.json` 供查閱。每日晨報只在 Codex 對話提供，網站資料更新與 LINE 推播已停用。私人持股由獨立網站管理。

## 舊版自動流程（已停用）

1. **07:35** Collect TCK market closes 蒐集並核對兩地預期交易日。當期結果寫入 [公開行情快照](https://raw.githubusercontent.com/TCKuo1988/family-investment-brief/tck-market-data/market-quotes.json)，同時保留 Actions artifact。研究前先核對快照的 `edition_date` 及兩地交易日。
2. **08:00** 依 [每日研究指令](daily-research-prompt.md) 研究一次。驗證通過後以授權 GitHub 帳號只更新 `report.json`。若 ChatGPT 排程無法寫入 GitHub，使用同一次研究生成的 JSON 交由授權帳號提交。
3. **08:10** LINE 使用通過驗證且已部署的晨報產圖。若當期研究尚未提交，使用當期行情快照產出狀態圖卡並附網站連結。Actions 另有 08:25 備援。相同日期使用同一 LINE retry key，API 接受後留下 `line-sent/YYYY-MM-DD`。已收到狀態圖卡的當期，若要額外補發完整圖卡，使用明確指定日期的 `correction`。

## 報價來源順序

- 臺股使用 TWSE MI_INDEX 當日價格指數與各證券行情表。特殊標記如 `X` 保留收盤價與說明，漲跌填缺值。歷史前日價差遇除息不直接視為經濟報酬。
- 美國個股、ETF 與 ADR 優先採 Nasdaq 歷史日線，使用 Stock Analysis 的 `Close` 備援並交叉核對。SPCX 是 Nasdaq 的 Space Exploration Technologies Corp. A 類普通股。
- S&P 500 優先採 FRED 的 S&P DJI 收盤序列。FRED 延遲時以 Google Finance 的 INDEXSP 收市後報價備援，並檢查時間戳及前收；也可採當日 AP 收盤報導與前一正式收盤人工覆核。Nasdaq Composite 優先採 FRED，其後採 Nasdaq 歷史收盤、已收市且日期吻合的 Nasdaq 官方頁與 Investing.com 歷史行情。SOX 依序採 Nasdaq 歷史收盤、已收市且日期吻合的 Nasdaq 指數資料、Investing.com 歷史行情。
- 有兩個以上可用來源時，核對當日及前一交易日收盤。SOX 備援來源只公布到小數一位，按該精度比較。來源有明顯差異或單一來源出現大幅變動時，留空待核對。日漲跌用同來源的未調整收盤與前一交易日收盤計算。
- `history.json` 是原有圖表的歷史資料。圖表更新與晨報行情分開執行，其 Yahoo Finance 資料僅供歷史圖表。

## 驗證與預覽

```sh
python -m pip install -r scripts/requirements-market.txt
python -m unittest discover -s tests
python scripts/collect_market.py --report-day 2026-11-18 > market-quotes.json
python scripts/validate_report.py --report-day 2026-11-18
python scripts/push_line_verified.py --report-day 2026-11-18
```

手動 Actions `preview` 先從來源重新取得指定當期行情，再產出 `line_preview.png`。當期晨報通過驗證時也產出文字預覽。實際發送使用 GitHub Actions 的 `send`，需 `LINE_CHANNEL_ACCESS_TOKEN` 與 `LINE_GROUP_ID`。部署來源是 `main` 的根目錄。以授權帳號正常提交研究檔案，Pages 部署成功後才具備推播條件。
