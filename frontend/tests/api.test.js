import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { ApiError, search } from "../src/api.js";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

function stream(events) {
  return new Response(`${events.map((event) => JSON.stringify(event)).join("\n")}\n`, {
    headers: { "content-type": "application/x-ndjson" },
  });
}

test("a search streams its steps, then returns the response", async () => {
  globalThis.fetch = async () =>
    stream([{ type: "step", step: { action: "read request (rules)" } }, { type: "done", response: { results: [] } }]);
  const steps = [];
  const result = await search({ query: "black watch", onStep: (step) => steps.push(step) });
  assert.deepEqual(result, { results: [] });
  assert.deepEqual(steps, [{ action: "read request (rules)" }]);
});

test("a rate-limited search says when to retry", async () => {
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: "too many requests" }), { status: 429, headers: { "Retry-After": "42" } });
  await assert.rejects(search({ query: "x" }), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 429);
    assert.equal(error.retryAfter, 42);
    return true;
  });
});

test("a rejected photo keeps the server's status and message", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "image dimensions too large" }), { status: 413 });
  await assert.rejects(
    search({ query: "x" }),
    (error) => error.status === 413 && error.detail === "image dimensions too large" && error.retryAfter === null,
  );
});

test("an error without a readable message falls back to the status text", async () => {
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: [{ msg: "field required" }] }), { status: 422, statusText: "Unprocessable Entity" });
  await assert.rejects(search({ query: "x" }), (error) => error.status === 422 && error.detail === "Unprocessable Entity");
});

test("no response at all is status 0", async () => {
  globalThis.fetch = async () => {
    throw new TypeError("fetch failed");
  };
  await assert.rejects(search({ query: "x" }), (error) => error instanceof ApiError && error.status === 0);
});

test("a failure partway through the stream says the search stopped", async () => {
  globalThis.fetch = async () =>
    stream([{ type: "step", step: {} }, { type: "error", detail: "search failed - see the server log" }]);
  await assert.rejects(
    search({ query: "x" }),
    (error) => error.status === 500 && error.detail === "the search stopped partway through",
  );
});
