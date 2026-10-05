import { CheckCircleIcon, ExclamationTriangleIcon, NoSymbolIcon } from "@heroicons/react/20/solid";
import { useState } from "react";

import { nothingFits, onlyNearMisses, rankingLabel, resultDetail } from "../copy.js";
import { money } from "../format.js";
import { Badge, Banner, Card, EmptyState } from "./ui.jsx";

// the whole row opens and closes; the title is a real button, so Enter and Space work too
function ResultRow({ item, requested }) {
  const [open, setOpen] = useState(false);

  return (
    <li className={open ? "result open" : "result"} onClick={() => setOpen((value) => !value)}>
      {item.image_url ? <img src={item.image_url} alt={item.title} loading="lazy" /> : <span className="no-photo" />}
      <div className="result-text">
        <button type="button" className="result-title" aria-expanded={open}>
          {item.title}
        </button>
        <span className="subdued">{[item.category, item.colour].filter(Boolean).join(" · ")}</span>
      </div>
      <span className="result-price">{money(item.price)}</span>
      <span className="result-fit">
        {item.misses.length ? (
          item.misses.map((miss) => (
            <Badge key={miss} tone="warning" icon={ExclamationTriangleIcon}>
              {miss}
            </Badge>
          ))
        ) : (
          <Badge tone="success" icon={CheckCircleIcon}>
            Match
          </Badge>
        )}
      </span>
      {open ? <p className="result-detail">{resultDetail(item, requested)}</p> : null}
    </li>
  );
}

function Placeholders() {
  return (
    <ul className="results" aria-busy="true" aria-label="Loading results">
      {[0, 1].map((n) => (
        <li key={n} className="result placeholder">
          <span className="ph-img" />
          <span className="ph-lines">
            <span />
            <span />
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function ResultsCard({ response }) {
  if (!response) {
    return (
      <Card title="Results">
        <Placeholders />
      </Card>
    );
  }

  const { results, requested, constraints, ranker } = response;
  const title = (
    <>
      Results <span className="count">{results.length}</span>
    </>
  );

  if (!results.length) {
    return (
      <Card title={title}>
        <EmptyState icon={NoSymbolIcon} title="Nothing in the catalogue fits">
          {nothingFits(requested, constraints)}
        </EmptyState>
      </Card>
    );
  }

  return (
    <Card title={title} aside={<span className="subdued">{rankingLabel(ranker)}</span>}>
      {onlyNearMisses(results) ? (
        <Banner tone="warning" icon={ExclamationTriangleIcon} className="results-banner">
          Nothing matches everything you asked for. These are the closest, and each one says how it's different.
        </Banner>
      ) : null}
      <ul className="results">
        {results.map((item) => (
          <ResultRow key={item.id} item={item} requested={requested} />
        ))}
      </ul>
    </Card>
  );
}
