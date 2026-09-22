import { useEffect, useRef, useState } from "react";

export default function Composer({
  query,
  setQuery,
  image,
  setImage,
  apiKey,
  setApiKey,
  onSubmit,
  busy,
  elapsed,
}) {
  const fileRef = useRef(null);
  const [over, setOver] = useState(false);
  const [thumb, setThumb] = useState(null);

  useEffect(() => {
    if (!image) {
      setThumb(null);
      return;
    }
    const url = URL.createObjectURL(image);
    setThumb(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  function take(file) {
    if (file && file.type.startsWith("image/")) setImage(file);
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <div className="composer">
        <input
          className="query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="like this but cheaper, in blue"
          autoComplete="off"
        />

        <div className="composer-bar">
          <button
            type="button"
            className={`dropzone${over ? " over" : ""}`}
            onClick={() => fileRef.current?.click()}
            onDragEnter={(e) => {
              e.preventDefault();
              setOver(true);
            }}
            onDragOver={(e) => e.preventDefault()}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setOver(false);
              take(e.dataTransfer.files[0]);
            }}
          >
            {thumb ? <img src={thumb} alt="" /> : null}
            <span>{image ? image.name : "Add a reference image"}</span>
          </button>

          {image ? (
            <button type="button" className="btn quiet" onClick={() => setImage(null)}>
              Remove
            </button>
          ) : null}

          <span className="spacer" />
          {busy ? <span className="elapsed">{elapsed.toFixed(1)}s</span> : null}
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Searching" : "Search"}
          </button>
        </div>

        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => take(e.target.files[0])}
        />
      </div>

      <div className="keyline">
        <label htmlFor="key">Backend API key</label>
        <input
          id="key"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="paste the API_KEY set on the backend"
          autoComplete="off"
        />
        <span className="key-hint">
          Shared secret the backend requires on every search (its <code>API_KEY</code> env var) —
          not an OpenAI/OpenRouter key. Ask whoever deployed this for it. Stored only in this
          browser.
        </span>
      </div>
    </form>
  );
}
