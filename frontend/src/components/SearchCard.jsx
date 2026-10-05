import { ArrowPathIcon, MagnifyingGlassIcon, PhotoIcon, XMarkIcon } from "@heroicons/react/20/solid";
import { useEffect, useRef, useState } from "react";

import { Button, Card } from "./ui.jsx";

// picked for the sample catalogue: "Repairs" and "No match" show the loop relaxing and giving up
export const EXAMPLES = [
  { label: "Try", queries: ["black watch", "white sneakers", "brown handbag", "pink top under 30"] },
  { label: "Repairs", queries: ["red running shoes under 40"] },
  { label: "No match", queries: ["sunglasses under 50"] },
];

export default function SearchCard({ query, setQuery, image, setImage, onSearch, busy }) {
  const fileRef = useRef(null);
  const [dropping, setDropping] = useState(false);
  // keep each preview URL with its file so a new photo never shows the old, revoked one
  const [thumb, setThumb] = useState(null);

  useEffect(() => {
    if (!image) return undefined;
    const url = URL.createObjectURL(image);
    setThumb({ file: image, url });
    return () => URL.revokeObjectURL(url);
  }, [image]);

  function take(file) {
    if (file && file.type.startsWith("image/")) setImage(file);
  }

  return (
    <Card>
      <div
        className={dropping ? "drop-area dropping" : "drop-area"}
        onDragOver={(event) => {
          event.preventDefault();
          setDropping(true);
        }}
        onDragLeave={(event) => {
          // dragleave also fires when moving onto a child
          if (!event.currentTarget.contains(event.relatedTarget)) setDropping(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDropping(false);
          // keep the current photo until the running search finishes
          if (!busy) take(event.dataTransfer.files[0]);
        }}
      >
        <form
          className="search-row"
          onSubmit={(event) => {
            event.preventDefault();
            onSearch();
          }}
        >
          <label className="field">
            <MagnifyingGlassIcon className="icon" aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="like this but cheaper, in blue"
              aria-label="Search request"
              autoComplete="off"
            />
          </label>
          {image ? (
            <span className="photo-chip">
              {thumb?.file === image ? <img src={thumb.url} alt="" /> : null}
              <span className="photo-name">{image.name}</span>
              <button
                type="button"
                className="chip-remove"
                onClick={() => setImage(null)}
                disabled={busy}
                aria-label="Remove photo"
              >
                <XMarkIcon className="icon" aria-hidden="true" />
              </button>
            </span>
          ) : (
            <Button icon={PhotoIcon} onClick={() => fileRef.current?.click()} disabled={busy}>
              Add photo
            </Button>
          )}
          <Button
            type="submit"
            variant="primary"
            icon={busy ? ArrowPathIcon : undefined}
            spinning={busy}
            disabled={busy || (!query.trim() && !image)}
          >
            {busy ? "Searching" : "Search"}
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(event) => {
              take(event.target.files[0]);
              event.target.value = "";
            }}
          />
        </form>
        <div className="examples">
          {EXAMPLES.map(({ label, queries }) => (
            <span className="example-group" key={label}>
              <span className="example-label">{label}</span>
              {queries.map((example) => (
                <button key={example} type="button" className="pill" disabled={busy} onClick={() => onSearch(example)}>
                  {example}
                </button>
              ))}
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}
