import assert from "node:assert/strict";
import { test } from "node:test";

import {
  amount,
  missSentence,
  nothingFits,
  onlyNearMisses,
  rankingLabel,
  requestPhrase,
  resultDetail,
} from "../src/copy.js";

const pinkTops = { intent: "pink top", category: "Tops", colour: "Pink", price_max: 30, relative_cheaper: false };

test("amounts drop zero cents in sentences", () => {
  assert.equal(amount(30), "$30");
  assert.equal(amount("62.50"), "$62.50");
});

test("amounts round like the server, so the trace and the banners agree", () => {
  // 50 raised twice by 25% is 78.125, which the server's "{:.2f}" prints as 78.12 (halves go to even)
  assert.equal(amount(78.125), "$78.12");
  assert.equal(amount(46.875), "$46.88");
});

test("the request phrase reads like a shopper wrote it", () => {
  assert.equal(requestPhrase(pinkTops), "pink tops under $30");
  assert.equal(requestPhrase({ colour: "Red", category: "Sports Shoes", price_max: 40 }), "red sports shoes under $40");
  assert.equal(requestPhrase({ price_max: 50 }), "items under $50");
  assert.equal(requestPhrase({ category: "Watches" }), "watches");
});

test("the ranking label names how results were ordered", () => {
  assert.equal(rankingLabel("similarity"), "Ranked by visual similarity");
  assert.equal(rankingLabel("llm"), "Ranked by a vision model");
});

test("misses become plain sentences", () => {
  assert.equal(missSentence("Beige, not Pink"), "Beige rather than pink.");
  assert.equal(missSentence("Sweatshirts, not Jackets"), "Sweatshirts rather than jackets.");
  assert.equal(missSentence("over budget by 4.50"), "$4.50 over your budget.");
});

test("a result opens to the model's reason, why it's shown, or that it fits", () => {
  const item = (fields) => ({ rationale: null, misses: [], ...fields });
  assert.equal(resultDetail(item({ rationale: "Same checked pattern." }), pinkTops), "Same checked pattern.");
  assert.equal(
    resultDetail(item({ misses: ["Beige, not Pink"] }), pinkTops),
    "Beige rather than pink. Shown because there aren't enough pink tops under $30.",
  );
  assert.equal(resultDetail(item({}), pinkTops), "Matches everything you asked for.");
});

test("nothing-fits explains a raised budget, otherwise suggests broadening", () => {
  const sunglasses = { category: "Sunglasses", price_max: 50 };
  assert.equal(
    nothingFits(sunglasses, { ...sunglasses, price_max: 78.125 }),
    "There are no sunglasses under $50 - even raising the budget to $78.12 found none. Try a higher budget.",
  );
  assert.equal(nothingFits({ category: "Jackets" }, { category: null }), "Try a broader request.");
});

test("only near-misses when every result misses something", () => {
  assert.equal(onlyNearMisses([{ misses: ["Beige, not Pink"] }]), true);
  assert.equal(onlyNearMisses([{ misses: [] }, { misses: ["Beige, not Pink"] }]), false);
  assert.equal(onlyNearMisses([]), false);
});
