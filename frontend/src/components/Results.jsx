import { useState } from "react";

import { money } from "../format.js";

function noReason(ranker, degraded) {
  if (ranker === "llm") return "The ranking model didn't give a reason for this one.";
  if (degraded) {
    return "The ranking model didn't answer this time, so this is in visual-similarity order, not judged for fit.";
  }
  return "Ranked by visual similarity to your request - no LLM is set up to judge fit.";
}

function Card({ item, ranker, degraded }) {
  const [open, setOpen] = useState(false);

  return (
    <div
      className="card"
      role="button"
      tabIndex={0}
      aria-expanded={open}
      onClick={() => setOpen((v) => !v)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setOpen((v) => !v);
        }
      }}
    >
      {item.image_url ? <img src={item.image_url} alt={item.title} loading="lazy" /> : null}
      <div className="body">
        <div className="name">{item.title}</div>
        <div className="meta">
          <span className="price">{money(item.price)}</span>
          {item.colour ? <span>{item.colour}</span> : null}
          {item.category ? <span>{item.category}</span> : null}
        </div>
        {item.misses?.length ? (
          <div className="misses">
            {item.misses.map((miss) => (
              <span className="miss" key={miss}>
                {miss}
              </span>
            ))}
          </div>
        ) : null}
        {item.rationale ? <div className="why">{item.rationale}</div> : null}

        {open ? (
          <div className="card-detail">
            {!item.rationale ? <p className="why-missing">{noReason(ranker, degraded)}</p> : null}
            <p className="score-line">
              similarity {item.score.toFixed(3)} - a relative signal from the embedding, not a
              percentage match
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function Results({ items, ranker, degraded }) {
  if (!items.length) {
    return <p className="muted">Nothing matched. Try relaxing the request.</p>;
  }
  return (
    <div className="grid">
      {items.map((item) => (
        <Card key={item.id} item={item} ranker={ranker} degraded={degraded} />
      ))}
    </div>
  );
}
