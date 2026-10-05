import assert from "node:assert/strict";
import { test } from "node:test";

import { ROUTES, routeFor } from "../src/router.js";

test("the how-it-works hash shows that page", () => {
  assert.equal(routeFor(ROUTES.how), "how");
});

test("any other hash shows search", () => {
  for (const hash of ["", "#", "#/", "#/nope", ROUTES.search]) assert.equal(routeFor(hash), "search");
});
