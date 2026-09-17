export function Constraints({ constraints }) {
  const pairs = [
    ["looking for", constraints.intent],
    ["category", constraints.category],
    ["colour", constraints.colour],
    ["max price", constraints.price_max],
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

export function Trace({ steps }) {
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
    </div>
  );
}
