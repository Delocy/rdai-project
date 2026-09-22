import { useState } from "react";

function Card({ item, degraded }) {
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
      {item.image_url ? <img src={item.image_url} alt="" loading="lazy" /> : null}
      <div className="body">
        <div className="name">{item.title}</div>
        <div className="meta">
          <span className="price">{Number(item.price).toFixed(2)}</span>
          {item.colour ? <span>{item.colour}</span> : null}
          {item.category ? <span>{item.category}</span> : null}
        </div>
        {item.rationale ? <div className="why">{item.rationale}</div> : null}

        {open ? (
          <div className="card-detail">
            {!item.rationale ? (
              <p className="why-missing">
                {degraded
                  ? "No ranking model was reachable for this search - this is ordered by raw vector similarity only, not judged for fit."
                  : "The ranking model didn't return a reason for this one."}
              </p>
            ) : null}
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

export default function Results({ items, degraded }) {
  if (!items.length) {
    return <p className="muted">Nothing matched. Try relaxing the request.</p>;
  }
  return (
    <div className="grid">
      {items.map((item) => (
        <Card key={item.id} item={item} degraded={degraded} />
      ))}
    </div>
  );
}
