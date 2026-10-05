// Plain-language text for the UI: pure functions over the API's response shapes, so every
// sentence a shopper sees is unit-tested (`npm test`).

// "$30", "$62.50" - whole amounts lose their cents in sentences. Halves round to even, like the
// server's own two-decimal formatting, so the trace and the banners show the same budget.
export function amount(value) {
  const scaled = Number(value) * 100;
  let cents = Math.round(scaled);
  if (scaled % 1 === 0.5 && cents % 2 === 1) cents -= 1;
  return cents % 100 === 0 ? `$${cents / 100}` : `$${(cents / 100).toFixed(2)}`;
}

// "pink tops under $30" - the request in a shopper's words
export function requestPhrase(requested) {
  const words = [];
  if (requested.colour) words.push(requested.colour.toLowerCase());
  words.push(requested.category ? requested.category.toLowerCase() : "items");
  if (requested.price_max != null) words.push(`under ${amount(requested.price_max)}`);
  return words.join(" ");
}

export function rankingLabel(ranker) {
  return ranker === "llm" ? "Ranked by a vision model" : "Ranked by visual similarity";
}

function capitalise(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// "Beige, not Pink" -> "Beige rather than pink."; "over budget by 4.50" -> "$4.50 over your budget."
export function missSentence(miss) {
  const budget = miss.match(/^over budget by ([\d.]+)$/);
  if (budget) return `${amount(budget[1])} over your budget.`;
  const swap = miss.match(/^(.+), not (.+)$/);
  if (swap) return `${capitalise(swap[1])} rather than ${swap[2].toLowerCase()}.`;
  return `${capitalise(miss)}.`;
}

// what an opened result says: the model's reason, why a near-miss is shown at all, or that it fits
export function resultDetail(item, requested) {
  if (item.rationale) return item.rationale;
  if (item.misses.length) {
    const misses = item.misses.map(missSentence).join(" ");
    return `${misses} Shown because there aren't enough ${requestPhrase(requested)}.`;
  }
  return "Matches everything you asked for.";
}

export function nothingFits(requested, applied) {
  const raised =
    requested.price_max != null && applied.price_max != null && applied.price_max > requested.price_max;
  if (raised) {
    return `There are no ${requestPhrase(requested)} - even raising the budget to ${amount(applied.price_max)} found none. Try a higher budget.`;
  }
  return "Try a broader request.";
}

// every result misses something, so the Results card says so up front
export function onlyNearMisses(results) {
  return results.length > 0 && results.every((item) => item.misses.length > 0);
}

function step(kind, label, detail = "") {
  return { kind, label, detail };
}

// "category Tops, colour Pink, under 30.00" -> "Tops · Pink · under $30"
function readPart(part, withPhoto) {
  if (part.startsWith("category ")) return part.slice("category ".length);
  if (part.startsWith("colour ")) return part.slice("colour ".length);
  if (part.startsWith("under ")) return `under ${amount(part.slice("under ".length))}`;
  if (part.startsWith("cheaper than")) return withPhoto ? "cheaper than your photo" : "cheaper than the closest match";
  return part;
}

function readDetail(detail, withPhoto) {
  if (!detail || detail.startsWith("no filters")) return "No filters";
  return detail
    .split(", ")
    .map((part) => readPart(part, withPhoto))
    .join(" · ");
}

function repairStep(detail) {
  if (detail.startsWith("colour")) return step("repair", "Relaxed colour", "also looking at other colours");
  if (detail.startsWith("category")) {
    return step("repair", "Relaxed category", "also looking at other kinds of product");
  }
  const price = detail.match(/price ceiling -> ([\d.]+)/);
  if (price) return step("repair", "Raised the budget", `now up to ${amount(price[1])}`);
  return step("repair", "Relaxed the search", detail);
}

// the agent's steps in plain words; `kind` picks the icon and colour in the Trace card.
// The backend's step names stay technical (its tests and the eval rely on them).
export function describeSteps(steps, { withPhoto = false } = {}) {
  let searches = 0;
  return steps.map(({ action, detail = "", kept = 0 }) => {
    if (action.startsWith("read request")) return step("read", "Read your request", readDetail(detail, withPhoto));
    if (action === "retrieve + check") {
      searches += 1;
      const retrieved = Number.parseInt(detail, 10);
      const found = kept ? `${kept} fit` : "none fit";
      const label = searches === 1 ? "Searched" : "Searched again";
      return step("search", label, Number.isNaN(retrieved) ? found : `${retrieved} closest products · ${found}`);
    }
    if (action === "repair") return repairStep(detail);
    if (action === "derive budget") {
      const cap = detail.match(/cap ([\d.]+)/);
      return step("repair", "Set a budget", cap ? `cheaper than the closest match: under ${amount(cap[1])}` : detail);
    }
    if (action === "dropped weak matches") {
      const dropped = Number.parseInt(detail, 10);
      return step("stop", "Removed weak matches", `${Number.isNaN(dropped) ? "Some" : dropped} didn't really fit`);
    }
    if (action === "no match") return step("stop", "Nothing fit");
    if (action === "parse unavailable") {
      return step("warn", "Couldn't use the AI to read your request", "used the built-in rules instead");
    }
    if (action === "ranking unavailable") {
      return step("warn", "Smart ranking unavailable", "sorted by visual similarity instead");
    }
    if (action === "image embedding unavailable") {
      return step("warn", "Couldn't read your photo", "searched with your words only");
    }
    return step("other", action, detail);
  });
}

export function liveLabel(steps) {
  return steps.some(({ action }) => action === "retrieve + check") ? "Searching again" : "Searching";
}

// how many fit in the search just before the repair whose note starts with `prefix`
function keptBefore(steps, prefix) {
  let kept = 0;
  for (const { action, detail = "", kept: count = 0 } of steps) {
    if (action === "retrieve + check") kept = count;
    else if (action === "repair" && detail.startsWith(prefix)) return kept;
  }
  return 0;
}

// what the search relaxed to find anything, for the "Understood as" banner; null when nothing was.
// pointAtResults is false when there are no results, or the Results card already says each is marked
export function relaxedNote(requested, applied, steps, pointAtResults = true) {
  const sentences = [];
  const kind = requested.category ? requested.category.toLowerCase() : "items";
  if (requested.colour && !applied.colour) {
    const kept = keptBefore(steps, "colour");
    const found = kept === 1 ? "Only one match for" : kept ? `Only ${kept}` : "No";
    sentences.push(`${found} ${requestPhrase(requested)}, so the closest ${kind} in other colours are included too.`);
  }
  if (requested.price_max != null && applied.price_max != null && applied.price_max !== requested.price_max) {
    const kept = keptBefore(steps, "price");
    const found = kept ? `Only ${kept} fit` : "Nothing fit";
    sentences.push(`${found} under ${amount(requested.price_max)}, so the budget was raised to ${amount(applied.price_max)}.`);
  }
  if (requested.category && !applied.category) {
    const kept = keptBefore(steps, "category");
    const found = kept ? `Only ${kept} fit` : "Nothing fit";
    sentences.push(`${found} as ${kind}, so similar items of other kinds are included too.`);
  }
  if (!sentences.length) return null;
  if (pointAtResults) sentences.push("Each one says how it's different.");
  return sentences.join(" ");
}

const FALLBACKS = [
  ["parse unavailable", "The AI couldn't read your request, so the built-in rules were used."],
  ["ranking unavailable", "Smart ranking isn't available right now, so results are sorted by how similar they look."],
  ["image embedding unavailable", "Your photo couldn't be read, so this searched with your words only."],
];

// one sentence per fallback a degraded search took
export function fallbackNotes(steps) {
  return FALLBACKS.filter(([action]) => steps.some((step) => step.action === action)).map(([, text]) => text);
}

export function errorMessage(error) {
  const status = error?.status ?? 0;
  if (status === 429) {
    const seconds = error.retryAfter ?? 60;
    return { tone: "warning", text: `Too many searches this minute. Try again in ${seconds} ${seconds === 1 ? "second" : "seconds"}.` };
  }
  if (status === 413) {
    const text =
      error.detail === "image dimensions too large"
        ? "That photo has too many pixels - try a smaller one."
        : "That photo is over 5 MB - try a smaller one.";
    return { tone: "critical", text };
  }
  if (status === 415) return { tone: "critical", text: "That file isn't a JPEG, PNG or WebP image." };
  if (status === 0) {
    return { tone: "critical", text: "Search failed. The server didn't respond - check that the app is still running." };
  }
  return { tone: "critical", text: `Search failed: ${error.detail}.` };
}
