# 臺北時間每日 08:00 晨報指令

以臺北日期為 `edition_date`。讀取 TCKuo1988/family-investment-brief 的 README、現行 report.json 和公開行情快照。
https://raw.githubusercontent.com/TCKuo1988/family-investment-brief/tck-market-data/market-quotes.json

先核對快照的期別及台美股各自預期交易日。只採用已核實的正規盤收盤與當期來源。尚未核實的資料保留 null 和缺漏說明。臺銀匯率使用美元即期買入牌告，標示實際牌告日。台指期夜盤標示交易時段及漲跌比較基準。

只研究一次。摘要先說今日最重要的一件事及為何重要。追蹤 NVDA、TSLA、SPCX、QQQ、VOO、SOXX、台積電 ADR，台股聚焦台積電、006208 及大型權值股。用原始財報、公司公告或具名分析師資料說明最新變化與投資論點，區分事實、觀點及推論。006208 維持定期定額，只在有明確依據時補充額外加碼觀察。股癌及 M 觀點只根據原始音訊或官方逐字稿整理，附集數及可用的時間點，無法取得原集內容則標示待整理。

以既有 report.json 格式更新公開欄位，保留 sources、daily_research、analysis_sections、quotes、us_quotes、fx。驗證後才發布，執行 `python scripts/validate_report.py --report-day YYYY-MM-DD`。有 GitHub 寫入權限時只提交 report.json，核對 commit 與 Pages 的期別。沒有寫入權限時交付同一份 JSON 並標明待提交，LINE 由 GitHub Actions 負責。私人持股與 Excel 檔留在私人流程。
