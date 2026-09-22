const API_URL = import.meta.env.VITE_API_URL ?? "";
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

// /search streams newline-delimited JSON: a {"type":"step",...} line per
// agent step as it happens, then a final {"type":"done","response":...}.
// onStep fires for each step so the caller can show live progress.
export async function search({ query, image, onStep }) {
  const body = new FormData();
  body.append("query", query);
  if (image) body.append("image", image);

  const response = await fetch(`${API_URL}/search`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY },
    body,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* non-json error body */
    }
    throw new Error(`${response.status} — ${detail}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let newlineAt;
    while ((newlineAt = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newlineAt).trim();
      buffer = buffer.slice(newlineAt + 1);
      if (!line) continue;

      const event = JSON.parse(line);
      if (event.type === "step") onStep?.(event.step);
      else if (event.type === "done") result = event.response;
      else if (event.type === "error") throw new Error(event.detail);
    }
  }

  if (!result) throw new Error("search stream ended without a result");
  return result;
}
