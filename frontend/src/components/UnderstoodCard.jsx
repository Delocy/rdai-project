import { ExclamationTriangleIcon } from "@heroicons/react/20/solid";
import { Fragment } from "react";

import { onlyNearMisses, relaxedNote } from "../copy.js";
import { money } from "../format.js";
import { Badge, Banner, Card } from "./ui.jsx";

export default function UnderstoodCard({ response, withPhoto }) {
  const { requested, constraints, trace, results } = response;
  const rows = [
    ["Looking for", requested.intent || (withPhoto ? "your photo" : null)],
    ["Category", requested.category ? <Badge>{requested.category}</Badge> : null],
    ["Colour", requested.colour ? <Badge tone="info">{requested.colour}</Badge> : null],
    ["Max price", requested.price_max != null ? money(requested.price_max) : null],
    ["Cheaper than", requested.relative_cheaper ? (withPhoto ? "your photo" : "the closest match") : null],
  ].filter(([, value]) => value);
  // no pointer when the Results card already says it
  const note = relaxedNote(requested, constraints, trace, results.length > 0 && !onlyNearMisses(results));

  return (
    <Card title="Understood as">
      {rows.length ? (
        <dl className="facts">
          {rows.map(([label, value]) => (
            <Fragment key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </Fragment>
          ))}
        </dl>
      ) : (
        <p className="subdued">No filters - these are the closest matches.</p>
      )}
      {note ? (
        <Banner tone="warning" icon={ExclamationTriangleIcon}>
          {note}
        </Banner>
      ) : null}
    </Card>
  );
}
