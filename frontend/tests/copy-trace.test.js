import assert from "node:assert/strict";
import { test } from "node:test";

import { describeSteps, liveLabel } from "../src/copy.js";

const trace = [
  { action: "read request (rules)", detail: "category Tops, colour Pink, under 30.00", kept: 0 },
  { action: "retrieve + check", detail: "24 retrieved, rejected {'wrong_colour': 18, 'wrong_category': 3}", kept: 3 },
  { action: "repair", detail: "colour filter -> query text", kept: 3 },
  { action: "retrieve + check", detail: "24 retrieved, rejected {'wrong_colour': 0, 'wrong_category': 15}", kept: 9 },
];

test("the trace reads as plain steps", () => {
  assert.deepEqual(describeSteps(trace), [
    { kind: "read", label: "Read your request", detail: "Tops · Pink · under $30" },
    { kind: "search", label: "Searched", detail: "24 closest products · 3 fit" },
    { kind: "repair", label: "Relaxed colour", detail: "also looking at other colours" },
    { kind: "search", label: "Searched again", detail: "24 closest products · 9 fit" },
  ]);
});

test("every kind of repair and fallback has its own wording", () => {
  const rows = describeSteps([
    { action: "repair", detail: "category filter -> query text" },
    { action: "repair", detail: "price ceiling -> 62.50" },
    { action: "derive budget", detail: "top match 45.00, cap 36.00" },
    { action: "dropped weak matches", detail: "2 nearest neighbour(s) didn't actually match the request" },
    { action: "no match", detail: "nothing in the catalogue fit this request" },
    { action: "parse unavailable", detail: "no text model available - read with rules instead" },
    { action: "ranking unavailable", detail: "no vision model available - kept similarity order" },
    { action: "image embedding unavailable", detail: "onnx error" },
    { action: "retrieve + check", detail: "24 retrieved, rejected {}", kept: 0 },
  ]);
  assert.deepEqual(
    rows.map(({ label, detail }) => [label, detail]),
    [
      ["Relaxed category", "also looking at other kinds of product"],
      ["Raised the budget", "now up to $62.50"],
      ["Set a budget", "cheaper than the closest match: under $36"],
      ["Removed weak matches", "2 didn't really fit"],
      ["Nothing fit", ""],
      ["Couldn't use the AI to read your request", "used the built-in rules instead"],
      ["Smart ranking unavailable", "sorted by visual similarity instead"],
      ["Couldn't read your photo", "searched with your words only"],
      ["Searched", "24 closest products · none fit"],
    ],
  );
});

test("a request with no filters, or cheaper than a photo, still reads well", () => {
  assert.equal(describeSteps([{ action: "read request (rules)", detail: "no filters - similarity only" }])[0].detail, "No filters");
  const cheaper = [{ action: "read request (rules)", detail: "cheaper than the closest match" }];
  assert.equal(describeSteps(cheaper, { withPhoto: true })[0].detail, "cheaper than your photo");
  assert.equal(describeSteps(cheaper)[0].detail, "cheaper than the closest match");
});

test("unknown steps pass through as sent", () => {
  assert.deepEqual(describeSteps([{ action: "rerank", detail: "by price" }]), [
    { kind: "other", label: "rerank", detail: "by price" },
  ]);
});

test("the live row says searching, then searching again", () => {
  assert.equal(liveLabel(trace.slice(0, 1)), "Searching");
  assert.equal(liveLabel(trace.slice(0, 3)), "Searching again");
});
