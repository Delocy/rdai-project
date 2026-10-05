import assert from "node:assert/strict";
import { test } from "node:test";

import { describeSteps, liveLabel } from "../src/copy.js";

const trace = [
  { action: "read request (rules)", detail: "category Tops, colour Pink, under 30.00", kept: 0 },
  { action: "retrieve + check", detail: "3 matching products in the catalogue", kept: 3 },
  { action: "repair", detail: "colour filter -> query text", kept: 3 },
  { action: "retrieve + check", detail: "37 matching products in the catalogue", kept: 24 },
];

test("the trace reads as plain steps", () => {
  assert.deepEqual(describeSteps(trace), [
    { kind: "read", label: "Read your request", detail: "Tops · Pink · under $30" },
    { kind: "search", label: "Searched", detail: "3 products fit" },
    { kind: "repair", label: "Relaxed colour", detail: "also looking at other colours" },
    { kind: "search", label: "Searched again", detail: "37 products fit" },
  ]);
});

test("wording for each step type", () => {
  const rows = describeSteps([
    { action: "repair", detail: "category filter -> query text" },
    { action: "repair", detail: "price ceiling -> 62.50" },
    { action: "derive budget", detail: "top match 45.00, cap 36.00" },
    { action: "no match", detail: "nothing in the catalogue fit this request" },
    { action: "retrieve + check", detail: "0 matching products in the catalogue", kept: 0 },
    { action: "retrieve + check", detail: "1 matching products in the catalogue", kept: 1 },
  ]);
  assert.deepEqual(
    rows.map(({ label, detail }) => [label, detail]),
    [
      ["Relaxed category", "also looking at other kinds of product"],
      ["Raised the budget", "now up to $62.50"],
      ["Set a budget", "cheaper than the closest match: under $36"],
      ["Nothing fit", ""],
      ["Searched", "none fit"],
      ["Searched again", "1 product fits"],
    ],
  );
});

test("no filters and cheaper requests", () => {
  assert.equal(describeSteps([{ action: "read request (rules)", detail: "no filters" }])[0].detail, "No filters");
  const cheaper = [{ action: "read request (rules)", detail: "cheaper than the closest match" }];
  assert.equal(describeSteps(cheaper, { withPhoto: true })[0].detail, "cheaper than your photo");
  assert.equal(describeSteps(cheaper)[0].detail, "cheaper than the closest match");
});

test("unknown steps pass through as sent", () => {
  assert.deepEqual(describeSteps([{ action: "rerank", detail: "by price" }]), [
    { kind: "other", label: "rerank", detail: "by price" },
  ]);
});

test("live row label", () => {
  assert.equal(liveLabel(trace.slice(0, 1)), "Searching");
  assert.equal(liveLabel(trace.slice(0, 3)), "Searching again");
});
