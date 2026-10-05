import { money } from "../format.js";

export function Constraints({ constraints }) {
  const pairs = [
    ["looking for", constraints.intent],
    ["category", constraints.category],
    ["colour", constraints.colour],
    ["max price", constraints.price_max == null ? null : money(constraints.price_max)],
    ["cheaper than reference", constraints.relative_cheaper || null],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "" && value !== false);

  if (!pairs.length) return <p className="muted">No constraints were extracted.</p>;

  return (
    <div className="chips">
      {pairs.map(([label, value]) => (
        <span className="chip" key={label}>
          <b>{label}: </b>
          {String(value)}
        </span>
      ))}
    </div>
  );
}

// what the repair loop loosened to find anything; results that miss the original
// request carry their own badges in Results
export function Relaxed({ requested, applied }) {
  if (!requested) return null;
  const notes = [];
  if (requested.price_max != null && applied.price_max !== requested.price_max) {
    notes.push(`max price ${money(requested.price_max)} → ${money(applied.price_max)}`);
  }
  for (const field of ["colour", "category"]) {
    if (requested[field] && !applied[field]) {
      notes.push(`${field} "${requested[field]}" → a soft preference`);
    }
  }
  if (!notes.length) return null;

  return (
    <p className="relaxed">
      Nothing matched exactly, so it relaxed {notes.join(", ")}. Results that miss what you
      asked for are marked.
    </p>
  );
}

export function Trace({ steps, live = false }) {
  return (
    <div className="trace">
      {steps.map((step, i) => {
        const kind = step.action.includes("repair")
          ? " repair"
          : step.action.includes("unavailable")
            ? " fail"
            : "";
        return (
          <div className={`trace-row${kind}`} key={i}>
            <span className="n">{step.iteration || ""}</span>
            <span className="act">{step.action}</span>
            <span className="det">{step.detail}</span>
            <span className="kept">{step.kept ? `kept ${step.kept}` : ""}</span>
          </div>
        );
      })}
      {live ? (
        <div className="trace-row pulse">
          <span className="n" />
          <span className="act">
            <span className="thinking-dot" />
            {steps.length ? "Working" : "Thinking"}
          </span>
          <span className="det" />
          <span className="kept" />
        </div>
      ) : null}
    </div>
  );
}
