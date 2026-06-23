/**
 * Contract tests for the FreeModel Worker proxy.
 *
 * Uses Node's built-in test runner (`node --test`) and stubs the global
 * `fetch` so the tests run without network or a deployed Worker.
 *
 * Run with:  npm test   (from cloudflare/freemodel-proxy/)
 */

import { test } from "node:test";
import assert from "node:assert/strict";

// Capture the outbound request the Worker made to the origin.
let lastOriginRequest = null;
let lastOriginInit = null;
// Scripted upstream response returned to the Worker.
let scriptedUpstream = null;

// Stub the Worker's `fetch(originUrl, init)` BEFORE importing the Worker
// module (the Worker calls the global `fetch` at request time, not import
// time, so stubbing here is sufficient).
globalThis.fetch = async (url, init) => {
  lastOriginRequest = url;
  lastOriginInit = init;
  if (typeof scriptedUpstream === "function") return scriptedUpstream();
  return scriptedUpstream;
};

const workerUrl = new URL("../worker.js", import.meta.url);
const workerModule = await import(workerUrl);
const worker = workerModule.default;

function makeInbound({ method = "POST", path = "/v1/responses", token, body = '{"hello":"world"}', headers = {} }) {
  const h = new Headers(headers);
  if (token) h.set("x-worker-token", token);
  return new Request(`https://freemodel-proxy.example.workers.dev${path}`, {
    method,
    headers: h,
    body: method === "GET" || method === "HEAD" ? undefined : body,
  });
}

function reset() {
  lastOriginRequest = null;
  lastOriginInit = null;
  scriptedUpstream = null;
}

test("returns 401 when WORKER_PROXY_TOKEN is set and X-Worker-Token is missing", async () => {
  reset();
  const env = { FREEMODEL_ORIGIN: "https://api.freemodel.dev", WORKER_PROXY_TOKEN: "secret" };
  const res = await worker.fetch(makeInbound({ token: null }), env, {});
  assert.equal(res.status, 401);
  const json = await res.json();
  assert.equal(json.error, "unauthorized");
  assert.equal(lastOriginRequest, null, "origin must not be called on auth failure");
});

test("returns 401 when X-Worker-Token does not match", async () => {
  reset();
  const env = { FREEMODEL_ORIGIN: "https://api.freemodel.dev", WORKER_PROXY_TOKEN: "secret" };
  const res = await worker.fetch(makeInbound({ token: "wrong" }), env, {});
  assert.equal(res.status, 401);
  assert.equal(lastOriginRequest, null);
});

test("forwards method, path, query, body and headers to the origin when token matches", async () => {
  reset();
  scriptedUpstream = () =>
    new Response('{"ok":true}', {
      status: 200,
      headers: { "content-type": "application/json", "x-upstream": "yes" },
    });
  const env = { FREEMODEL_ORIGIN: "https://api.freemodel.dev", WORKER_PROXY_TOKEN: "secret" };
  const res = await worker.fetch(
    makeInbound({
      method: "POST",
      path: "/v1/responses?stream=true",
      token: "secret",
      body: '{"prompt":"hi"}',
      headers: { authorization: "Bearer sk-test", "content-type": "application/json" },
    }),
    env,
    {},
  );

  assert.equal(res.status, 200);
  assert.equal(lastOriginRequest, "https://api.freemodel.dev/v1/responses?stream=true");
  assert.equal(lastOriginInit.method, "POST");
  assert.equal(lastOriginInit.headers.get("authorization"), "Bearer sk-test");
  assert.equal(lastOriginInit.headers.get("host"), "api.freemodel.dev");
  // The inbound token must NOT be forwarded to the origin.
  assert.equal(lastOriginInit.headers.get("x-worker-token"), null);
  // Hop-by-hop header (connection) must be stripped.
  // (Not set here, but the strip logic is exercised by copyHeaders; this
  // assertion documents the contract.)
});

test("strips hop-by-hop and CF- inbound headers before forwarding", async () => {
  reset();
  scriptedUpstream = () => new Response("{}", { status: 200 });
  const env = { FREEMODEL_ORIGIN: "https://api.freemodel.dev", WORKER_PROXY_TOKEN: "secret" };
  await worker.fetch(
    makeInbound({
      token: "secret",
      headers: {
        connection: "keep-alive",
        "cf-connecting-ip": "203.0.113.9",
        "cf-ray": "abc",
        "x-forwarded-for": "203.0.113.9",
        "x-real-ip": "203.0.113.9",
      },
    }),
    env,
    {},
  );
  assert.equal(lastOriginInit.headers.get("connection"), null);
  assert.equal(lastOriginInit.headers.get("cf-connecting-ip"), null);
  assert.equal(lastOriginInit.headers.get("cf-ray"), null);
  assert.equal(lastOriginInit.headers.get("x-forwarded-for"), null);
  assert.equal(lastOriginInit.headers.get("x-real-ip"), null);
});

test("streams the upstream response body through unbuffered", async () => {
  reset();
  // A ReadableStream body on the upstream response must be passed through
  // as a ReadableStream on the Worker response (no buffering into a string).
  const upstreamBody = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("data: chunk1\n\n"));
      controller.enqueue(new TextEncoder().encode("data: chunk2\n\n"));
      controller.close();
    },
  });
  scriptedUpstream = () =>
    new Response(upstreamBody, {
      status: 200,
      headers: { "content-type": "text/event-stream" },
    });
  const env = { FREEMODEL_ORIGIN: "https://api.freemodel.dev", WORKER_PROXY_TOKEN: "secret" };
  const res = await worker.fetch(makeInbound({ token: "secret" }), env, {});
  assert.equal(res.status, 200);
  assert.ok(res.body instanceof ReadableStream, "response body must be a stream");
  assert.equal(res.headers.get("content-type"), "text/event-stream");
  assert.equal(res.headers.get("x-freemodel-proxy"), "1");

  const text = await res.text();
  assert.equal(text, "data: chunk1\n\ndata: chunk2\n\n");
});

test("returns 502 JSON when the origin fetch throws", async () => {
  reset();
  globalThis.fetch = async () => {
    throw new Error("network down");
  };
  const env = { FREEMODEL_ORIGIN: "https://api.freemodel.dev", WORKER_PROXY_TOKEN: "secret" };
  const res = await worker.fetch(makeInbound({ token: "secret" }), env, {});
  assert.equal(res.status, 502);
  const json = await res.json();
  assert.equal(json.error, "bad_gateway");

  // Restore the default stub for subsequent tests.
  globalThis.fetch = async (url, init) => {
    lastOriginRequest = url;
    lastOriginInit = init;
    if (typeof scriptedUpstream === "function") return scriptedUpstream();
    return scriptedUpstream;
  };
});

test("token gate disabled when WORKER_PROXY_TOKEN is unset (local dev)", async () => {
  reset();
  scriptedUpstream = () => new Response("{}", { status: 200 });
  const env = { FREEMODEL_ORIGIN: "https://api.freemodel.dev" };
  const res = await worker.fetch(makeInbound({ token: null }), env, {});
  assert.equal(res.status, 200);
  assert.ok(lastOriginRequest, "origin must be called when gate is disabled");
});
