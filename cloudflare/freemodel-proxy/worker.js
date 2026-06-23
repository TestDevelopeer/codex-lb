/**
 * FreeModel Cloudflare Worker reverse proxy.
 *
 * Forwards inbound requests to the FreeModel origin (default
 * https://api.freemodel.dev) preserving method, path, query, body and
 * headers, while:
 *   - gating access behind a shared secret (X-Worker-Token) so the
 *     Worker cannot be used as an open proxy,
 *   - stripping hop-by-hop headers on both legs (RFC 7230),
 *   - streaming the upstream response body back unbuffered so SSE /
 *     chunked responses (/v1/responses?stream=true) keep working.
 *
 * Configuration (wrangler):
 *   - vars.FREEMODEL_ORIGIN  upstream origin, default https://api.freemodel.dev
 *   - secret WORKER_PROXY_TOKEN  shared secret; when set, inbound
 *     X-Worker-Token MUST match or the Worker returns 401. When unset
 *     the token gate is disabled (use only for local dev).
 */

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
]);

// Header names that must never be forwarded to the origin.
const STRIP_TO_ORIGIN = new Set([
  "x-worker-token",
  "cf-connecting-ip",
  "cf-ipcountry",
  "cf-ray",
  "cf-visitor",
  "cf-worker",
  "x-forwarded-for",
  "x-forwarded-proto",
  "x-real-ip",
  "true-client-ip",
]);

function jsonResponse(status, payload, extraHeaders = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...extraHeaders,
    },
  });
}

/**
 * Copy headers from `src` into `dst`, dropping hop-by-hop headers and
 * any name in `extraStrip`. Header casing is normalized by Headers.
 */
function copyHeaders(src, dst, extraStrip) {
  for (const [key, value] of src.entries()) {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP.has(lower)) continue;
    if (extraStrip && extraStrip.has(lower)) continue;
    dst.set(key, value);
  }
}

/**
 * Constant-time string comparison to avoid timing oracles on the token.
 */
function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  const encoder = new TextEncoder();
  const ab = encoder.encode(a);
  const bb = encoder.encode(b);
  if (ab.length !== bb.length) return false;
  let diff = 0;
  for (let i = 0; i < ab.length; i++) diff |= ab[i] ^ bb[i];
  return diff === 0;
}

export default {
  async fetch(request, env, ctx) {
    const origin = (env.FREEMODEL_ORIGIN || "https://api.freemodel.dev").replace(/\/+$/, "");
    const workerToken = env.WORKER_PROXY_TOKEN;

    // --- Shared-secret gate -------------------------------------------------
    if (workerToken) {
      const inbound = request.headers.get("x-worker-token");
      if (!inbound || !safeEqual(inbound, workerToken)) {
        return jsonResponse(401, {
          error: "unauthorized",
          message: "Missing or invalid X-Worker-Token.",
        });
      }
    }

    const incomingUrl = new URL(request.url);
    const upstreamUrl = origin + incomingUrl.pathname + incomingUrl.search;

    // --- Build the outbound request ----------------------------------------
    const outboundHeaders = new Headers();
    copyHeaders(request.headers, outboundHeaders, STRIP_TO_ORIGIN);
    // Explicitly set the origin Host so the upstream vhost matches.
    outboundHeaders.set("host", new URL(origin).host);

    const init = {
      method: request.method,
      headers: outboundHeaders,
      redirect: "manual",
    };
    // GET / HEAD must not carry a body; everything else streams the body.
    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = request.body;
      // duplex: 'half' is required to stream a request body in the
      // Workers runtime.
      init.duplex = "half";
    }

    let upstream;
    try {
      upstream = await fetch(upstreamUrl, init);
    } catch (err) {
      return jsonResponse(502, {
        error: "bad_gateway",
        message: `Failed to reach FreeModel origin: ${String(err && err.message || err)}`,
      });
    }

    // --- Build the downstream response -------------------------------------
    const responseHeaders = new Headers();
    copyHeaders(upstream.headers, responseHeaders);
    // Preserve the Worker's own observability header for debugging.
    responseHeaders.set("x-freemodel-proxy", "1");

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  },
};
