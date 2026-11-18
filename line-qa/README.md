# LINE 群組免費額度問答

這個 Cloudflare Worker 接收 LINE Webhook。只限兩個已綁定帳號，在指定的群組內用 LINE 的 @ 功能標註官方帳號。每天臺北時間共 10 次 AI 問答。免費額度耗盡、Gemini 回應失敗或尚未設定時，使用 LINE reply 回傳晨報連結。模型收到問題和選定的公開晨報欄位，Worker 不讀 Firebase 或私人持股。請勿在問題中輸入個資或私人財務，免費方案的模型資料使用依 Google 條款。

## 啟用

1. 使用 Cloudflare **Workers Free**。從這個目錄執行 `npx wrangler login` 和 `npx wrangler deploy`。
2. 在未啟用 Cloud Billing 的 Google AI Studio 專案建立 Gemini API key。確認所在地和所選 Gemini 模型有免費額度，維持該專案未啟用計費。程式沒有付費備援。LINE 訊息以同一個 Messaging API channel 的 Reply API 回覆。
3. 用 `npx wrangler secret put <名稱>` 設定下列值。憑證與配對碼只輸入設定提示，請勿提交到 GitHub 或貼到群組。

   | 名稱 | 值 |
   | --- | --- |
   | `LINE_CHANNEL_SECRET` | 原 LINE Developers Messaging API channel 的 Channel secret |
   | `LINE_CHANNEL_ACCESS_TOKEN` | 原 LINE 機器人的 Messaging API token |
   | `LINE_GROUP_ID` | 原群組 ID |
   | `GEMINI_API_KEY` | 第 2 步建立的 key |
   | `GEMINI_FREE_MODEL` | 已確認免費的模型 ID（不含 `models/`） |
   | `OWNER_PAIR_CODE`、`Q_PAIR_CODE` | 用 `openssl rand -hex 16` 各自產生不同的碼 |

4. 在原 LINE Developers channel 設定 Worker 網址加 `/line`，按 Verify，再開啟 Use webhook。若該 channel 已有 Webhook，先保留其用途並整合路由。每日晨報仍使用 GitHub Actions 原流程。
5. 將兩組配對碼分別私下交給本人和 Q。兩人各自在與官方帳號的一對一聊天室輸入 `/綁定 配對碼`。收到成功訊息後，在原群組用真正的 @ 提及機器人並接上問題。每個配對碼只能綁定一個帳號。

測試可在此目錄執行 `node --test worker.test.mjs`，使用模擬的 LINE 與 Gemini 回應。
