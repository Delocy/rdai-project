// Every sentence the UI builds from a search, as pure functions covered by npm test.

// "$30", "$62.50". Halves round to even like Python does, so the trace and banners agree.
export function amount(value) {
  const scaled = Number(value) * 100;
  let cents = Math.round(scaled);
  if (scaled % 1 === 0.5 && cents % 2 === 1) cents -= 1;
  return cents % 100 === 0 ? `$${cents / 100}` : `$${(cents / 100).toFixed(2)}`;
}

// "pink tops under $30"
export function requestPhrase(requested) {
  const words = [];
  if (requested.colour) words.push(requested.colour.toLowerCase());
  words.push(requested.category ? requested.category.toLowerCase() : "items");
  if (requested.price_max != null) words.push(`under ${amount(requested.price_max)}`);
  return words.join(" ");
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

// the detail line of an opened result
export function resultDetail(item, requested) {
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

// true when every result misses something
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

// the search steps in plain words; `kind` picks the icon
export function describeSteps(steps, { withPhoto = false } = {}) {
  let searches = 0;
  return steps.map(({ action, detail = "", kept = 0 }) => {
    if (action.startsWith("read request")) return step("read", "Read your request", readDetail(detail, withPhoto));
    if (action === "retrieve + check") {
      searches += 1;
      // matches across the whole catalogue, which can be more than were retrieved
      const total = Number.parseInt(detail, 10);
      const fit = Number.isNaN(total) ? kept : total;
      const found = fit === 0 ? "none fit" : fit === 1 ? "1 product fits" : `${fit} products fit`;
      return step("search", searches === 1 ? "Searched" : "Searched again", found);
    }
    if (action === "repair") return repairStep(detail);
    if (action === "derive budget") {
      const cap = detail.match(/cap ([\d.]+)/);
      return step("repair", "Set a budget", cap ? `cheaper than the closest match: under ${amount(cap[1])}` : detail);
    }
    if (action === "no match") return step("stop", "Nothing fit");
    return step("other", action, detail);
  });
}

export function liveLabel(steps) {
  return steps.some(({ action }) => action === "retrieve + check") ? "Searching again" : "Searching";
}

// how many fit in the search before the repair named by `prefix`
function keptBefore(steps, prefix) {
  let kept = 0;
  for (const { action, detail = "", kept: count = 0 } of steps) {
    if (action === "retrieve + check") kept = count;
    else if (action === "repair" && detail.startsWith(prefix)) return kept;
  }
  return 0;
}

// what the search relaxed, for the Understood as banner (null if nothing). pointAtResults
// is false with no results, or when the Results card already says it
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
