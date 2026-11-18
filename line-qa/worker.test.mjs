import assert from "node:assert/strict";
import test from "node:test";
import worker, { QuestionState } from "./worker.mjs";

const encoded = new TextEncoder();
const secret = "mock-channel-secret";
const token = "mock-channel-token";
const ownerCode = "a".repeat(32);
const qCode = "b".repeat(32);

function fixture() {
  const store = new Map();
  const state = new QuestionState({ storage: {
    transaction: callback => callback({
      get: async key => structuredClone(store.get(key)),
      put: async (key, value) => store.set(key, structuredClone(value)),
    }),
  } });
  const env = {
    LINE_CHANNEL_SECRET: secret, LINE_CHANNEL_ACCESS_TOKEN: token,
    LINE_GROUP_ID: "family-group", OWNER_PAIR_CODE: ownerCode, Q_PAIR_CODE: qCode,
    GEMINI_FREE_MODEL: "gemini-test", GEMINI_API_KEY: "mock-ai-key",
    QA_STATE: { idFromName: value => value, get: () => ({
      fetch: (url, options) => state.fetch(new Request(url, options)),
    }) },
  };
  return env;
}

async function deliver(events, env, valid = true) {
  const body = JSON.stringify({ events });
  const key = await crypto.subtle.importKey(
    "raw", encoded.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const tag = await crypto.subtle.sign("HMAC", key, encoded.encode(body));
  const signature = valid ? Buffer.from(tag).toString("base64") : "invalid";
  let pending;
  const response = await worker.fetch(new Request("https://worker.example/line", {
    method: "POST", body, headers: { "x-line-signature": signature },
  }), env, { waitUntil: work => { pending = work; } });
  await pending;
  return response;
}

function pair(userId, code) {
  return {
    type: "message", timestamp: Date.now(), webhookEventId: `bind-${userId}`, replyToken: "reply",
    source: { type: "user", userId }, message: { type: "text", text: `/綁定 ${code}` },
  };
}

function ask(userId, eventId, groupId = "family-group", tagged = true) {
  return {
    type: "message", timestamp: Date.now(), webhookEventId: eventId, replyToken: "reply",
    source: { type: "group", userId, groupId },
    message: {
      type: "text", text: "@晨報 費半為什麼上漲？",
      mention: { mentionees: [{ type: "user", index: 0, length: 3, isSelf: tagged }] },
    },
  };
}

test("signature, binding, group and tag checks gate Gemini, and daily quota stops requests", async mocks => {
  const replies = [];
  let aiCalls = 0;
  let quotaRefused = false;
  mocks.mock.method(globalThis, "fetch", async (url, options) => {
    if (url.includes("api.line.me")) {
      replies.push(JSON.parse(options.body).messages[0].text);
      return Response.json({});
    }
    if (url.endsWith("report.json")) {
      return Response.json({ edition_date: "2026-11-18", action: "private sentinel" });
    }
    aiCalls++;
    assert.match(options.body, /費半為什麼上漲/);
    assert.doesNotMatch(options.body, /private sentinel|family-group|mock-channel-token|owner-id/);
    if (quotaRefused) return new Response(null, { status: 429 });
    return Response.json({ candidates: [{ content: { parts: [{ text: "測試答案" }] } }] });
  });
  const env = fixture();
  assert.equal((await deliver([pair("intruder", ownerCode)], env, false)).status, 401);
  assert.equal((await deliver([], env)).status, 200);
  await deliver([pair("owner-id", ownerCode)], env);
  await deliver([pair("q-id", qCode)], env);
  await deliver([pair("intruder", ownerCode)], env);
  assert.equal(replies.length, 2);
  await deliver([ask("intruder", "x"), ask("owner-id", "y", "other"), ask("q-id", "z", "family-group", false)], env);
  assert.equal(aiCalls, 0);
  await deliver([ask("q-id", "question-1")], env);
  await deliver([ask("q-id", "question-1")], env);
  assert.equal(aiCalls, 1);
  assert.match(replies.at(-1), /測試答案/);
  quotaRefused = true;
  await deliver([ask("owner-id", "question-2")], env);
  assert.match(replies.at(-1), /暫時無法使用/);
  for (let number = 3; number <= 11; number++) {
    await deliver([ask("owner-id", `question-${number}`)], env);
  }
  assert.equal(aiCalls, 10);
  assert.match(replies.at(-1), /額度已用完/);
});
