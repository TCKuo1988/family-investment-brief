# TCK 家庭投資晨報

`report.json` 是 GitHub Pages 與 LINE 的共用晨報。臺股和美股分別列交易日。公開研究與行情檔案只放可公開資料，私人持股仍由 Firebase 帳號與規則管理。乖寶寶入口在首頁導覽。

## 每日更新（臺北時間）

1. **07:35 每日** GitHub Actions 的 Collect TCK market closes 將臺美股報價寫入當次執行的 `market-quotes` artifact。手動執行可指定晨報日期。收盤行情採臺證所指定日期的公告、美股正規盤日線的未調整 Close。報價程式獨立依交易所日曆判定上一個已收盤的交易日，核對資料日期，保留缺值與分歧原因。臺股遇到休市或颱風等臨時停市，若套件日曆尚未反映、或交易所沒有該日公告，蒐集會失敗，請確認交易所公告後修正日曆再執行。
2. **08:00 研究** 既有「TCK 每日台美股晨報」排程已更新發布指令。排程自動寫入 GitHub 的能力需由下一次成功的排程提交確認。現行無額外付費 AI API 路徑是以授權的 GitHub 帳號把一次研究與行情 artifact 合成 `report.json` 後提交 `main`。把 `edition_date`、`report-date`、全文 `analysis_sections`、`daily_research`、來源連結、行情及策略一起更新。保留 `quotes`、`us_quotes` 與臺銀 `fx` 的欄位以相容私人持股估值。缺值保留 `null` 並填 `note`。S&P 500 和 Nasdaq Composite 為正式推播必要行情。採用其他當日可驗證來源時記錄正規盤收盤、上一交易日收盤及來源，再執行驗證。
3. **08:10 每日** LINE 工作流程驗證今天的研究與兩地市場交易日，確認部署中的 Pages `report.json` 與 GitHub checkout 位元組一致，再以現有 LINE secrets 推播。Actions 排程可能延遲。臺北 08:10～09:00 之間，Pages 成功部署事件會再檢查一次，另有 08:25 排程備援。Pages 尚未就緒時留存預覽並在 Actions 摘要標示原因。資料確認後可在當天手動執行 `send`。手動預設 `preview`，推送程式碼或報告只執行測試與預覽。正式推播使用每日固定的 LINE retry key，API 確認接受後建立 `line-sent/YYYY-MM-DD` tag。LINE HTTP 200 或帶已接受請求 ID 的 409 代表 API 同意處理。

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

預覽寫到 `line_preview.txt`；Actions 執行可下載同名 artifact。實際發送使用 GitHub Actions 的 `send`，需 `LINE_CHANNEL_ACCESS_TOKEN` 與 `LINE_GROUP_ID`。部署來源是 `main` 的根目錄。以授權帳號正常提交研究檔案，Pages 部署成功後才具備推播條件。
