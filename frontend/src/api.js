// Vite replaces import.meta.env at build time; under `node --test` it doesn't exist
const env = import.meta.env ?? {};
const API_URL = env.VITE_API_URL ?? "";
const API_KEY = env.VITE_API_KEY ?? "";

const STOPPED = "the search stopped partway through";

// what went wrong talking to the API; status 0 means no response came back at all
export class ApiError extends Error {
  constructor(status, detail, retryAfter = null) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.retryAfter = retryAfter;
  }
}

// /search streams newline-delimited JSON: a {"type":"step",...} line per
// agent step as it happens, then a final {"type":"done","response":...}.
// onStep fires for each step so the caller can show live progress.
export async function search({ query, image, onStep }) {
  const body = new FormData();
  body.append("query", query);
  if (image) body.append("image", image);

  let response;
  try {
    response = await fetch(`${API_URL}/search`, {
      method: "POST",
      headers: { "X-API-Key": API_KEY },
      body,
    });
  } catch {
    throw new ApiError(0, "no response");
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const error = await response.json();
      // FastAPI's validation errors put a list here; keep the status text for those
      if (typeof error.detail === "string") detail = error.detail;
    } catch {
      /* non-json error body */
    }
    const retryAfter = Number.parseInt(response.headers.get("Retry-After") ?? "", 10);
    throw new ApiError(response.status, detail, Number.isNaN(retryAfter) ? null : retryAfter);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;

  try {
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
        else if (event.type === "error") throw new ApiError(500, STOPPED);
      }
    }
  } catch (error) {
    // the server answered, then the stream broke off or went wrong
    throw error instanceof ApiError ? error : new ApiError(500, STOPPED);
  }

  if (!result) throw new ApiError(500, STOPPED);
  return result;
}
