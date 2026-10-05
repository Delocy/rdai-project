import assert from "node:assert/strict";
import { test } from "node:test";

import { errorMessage, relaxedNote } from "../src/copy.js";

const search = (kept) => ({ action: "retrieve + check", detail: `${kept} matching products in the catalogue`, kept });
const repair = (detail) => ({ action: "repair", detail });
const pinkTops = { category: "Tops", colour: "Pink", price_max: 30 };

test("the relaxed banner says what was loosened, in plain words", () => {
  assert.equal(
    relaxedNote(pinkTops, { ...pinkTops, colour: null }, [search(3), repair("colour filter -> query text"), search(9)]),
    "Only 3 pink tops under $30, so the closest tops in other colours are included too. Each one says how it's different.",
  );
  const shoes = { category: "Sports Shoes", colour: "Red", price_max: 40 };
  assert.equal(
    relaxedNote(shoes, { ...shoes, colour: null, price_max: 50 }, [
      search(0),
      repair("colour filter -> query text"),
      search(0),
      repair("price ceiling -> 50.00"),
      search(2),
    ]),
    "No red sports shoes under $40, so the closest sports shoes in other colours are included too. " +
      "Nothing fit under $40, so the budget was raised to $50. Each one says how it's different.",
  );
  assert.equal(
    relaxedNote({ category: "Jackets" }, { category: null }, [search(0), repair("category filter -> query text"), search(8)]),
    "Nothing fit as jackets, so similar items of other kinds are included too. Each one says how it's different.",
  );
});

test("a relaxation that still found some says how many", () => {
  const watches = { category: "Watches", price_max: 50 };
  assert.equal(
    relaxedNote(watches, { ...watches, price_max: 62.5 }, [search(2), repair("price ceiling -> 62.50"), search(6)]),
    "Only 2 fit under $50, so the budget was raised to $62.50. Each one says how it's different.",
  );
  const jackets = { category: "Jackets", colour: "Blue" };
  assert.equal(
    relaxedNote(jackets, { category: null, colour: null }, [
      search(1),
      repair("colour filter -> query text"),
      search(2),
      repair("category filter -> query text"),
      search(9),
    ]),
    "Only one match for blue jackets, so the closest jackets in other colours are included too. " +
      "Only 2 fit as jackets, so similar items of other kinds are included too. Each one says how it's different.",
  );
});

test("nothing relaxed means no banner", () => {
  assert.equal(relaxedNote(pinkTops, pinkTops, [search(6)]), null);
});

test("the banner doesn't point at results that aren't there", () => {
  const sunglasses = { category: "Sunglasses", price_max: 50 };
  const trace = [search(0), repair("price ceiling -> 62.50"), search(0), repair("price ceiling -> 78.12"), search(0)];
  assert.equal(
    relaxedNote(sunglasses, { ...sunglasses, price_max: 78.125 }, trace, false),
    "Nothing fit under $50, so the budget was raised to $78.12.",
  );
});

test("errors read as plain sentences", () => {
  assert.deepEqual(errorMessage({ status: 0 }), {
    tone: "critical",
    text: "Search failed. The server didn't respond - check that the app is still running.",
  });
  assert.deepEqual(errorMessage({ status: 413, detail: "image too large" }), {
    tone: "critical",
    text: "That photo is over 5 MB - try a smaller one.",
  });
  assert.equal(
    errorMessage({ status: 413, detail: "image dimensions too large" }).text,
    "That photo has too many pixels - try a smaller one.",
  );
  assert.deepEqual(errorMessage({ status: 415, detail: "unsupported image type" }), {
    tone: "critical",
    text: "That file isn't a JPEG, PNG or WebP image.",
  });
  assert.deepEqual(errorMessage({ status: 500, detail: "the search stopped partway through" }), {
    tone: "critical",
    text: "Search failed: the search stopped partway through.",
  });
});

test("a rate limit says when to try again", () => {
  assert.deepEqual(errorMessage({ status: 429, retryAfter: 42 }), {
    tone: "warning",
    text: "Too many searches this minute. Try again in 42 seconds.",
  });
  assert.equal(errorMessage({ status: 429, retryAfter: 1 }).text, "Too many searches this minute. Try again in 1 second.");
  assert.equal(errorMessage({ status: 429, retryAfter: null }).text, "Too many searches this minute. Try again in 60 seconds.");
});
