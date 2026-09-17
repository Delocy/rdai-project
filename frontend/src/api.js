export async function search({ query, image, apiKey }) {
  const body = new FormData();
  body.append("query", query);
  if (image) body.append("image", image);

  const response = await fetch("/search", {
    method: "POST",
    headers: { "X-API-Key": apiKey },
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
  return response.json();
}

export function loadKey() {
  try {
    return localStorage.getItem("apiKey") ?? "";
  } catch {
    return "";
  }
}

export function saveKey(value) {
  try {
    localStorage.setItem("apiKey", value);
  } catch {
    /* storage unavailable */
  }
}
