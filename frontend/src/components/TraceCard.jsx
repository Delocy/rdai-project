import {
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ClockIcon,
  DocumentTextIcon,
  FunnelIcon,
  NoSymbolIcon,
  WrenchScrewdriverIcon,
} from "@heroicons/react/20/solid";
import { useState } from "react";

import { describeSteps, liveLabel } from "../copy.js";
import { Card } from "./ui.jsx";

const ICONS = {
  read: DocumentTextIcon,
  search: FunnelIcon,
  repair: WrenchScrewdriverIcon,
  stop: NoSymbolIcon,
  other: DocumentTextIcon,
};

// open on desktop, closed on phones
function startsOpen() {
  return !window.matchMedia("(max-width: 767px)").matches;
}

export default function TraceCard({ steps, live, elapsed, withPhoto }) {
  const [open, setOpen] = useState(startsOpen);
  const rows = describeSteps(steps, { withPhoto });

  const toggle = (
    <button
      type="button"
      className="icon-button"
      aria-expanded={open}
      aria-label={open ? "Hide trace" : "Show trace"}
      onClick={() => setOpen((value) => !value)}
    >
      {open ? <ChevronUpIcon className="icon" aria-hidden="true" /> : <ChevronDownIcon className="icon" aria-hidden="true" />}
    </button>
  );

  return (
    <Card title="Trace" aside={toggle}>
      {open ? (
        <>
          <ol className="trace">
            {rows.map((row, n) => {
              const Icon = ICONS[row.kind];
              return (
                <li key={n} className={`step step-${row.kind}`}>
                  <span className="step-icon">
                    <Icon className="icon" aria-hidden="true" />
                  </span>
                  <span>
                    <strong>{row.label}</strong>
                    {row.detail ? <small>{row.detail}</small> : null}
                  </span>
                </li>
              );
            })}
            {live ? (
              <li className="step step-live">
                <span className="step-icon">
                  <ArrowPathIcon className="icon spin" aria-hidden="true" />
                </span>
                <span>
                  <strong>{liveLabel(steps)}</strong>
                  <small>{elapsed.toFixed(1)}s</small>
                </span>
              </li>
            ) : null}
          </ol>
          {live ? null : (
            <p className="trace-foot">
              <ClockIcon className="icon" aria-hidden="true" />
              Took {elapsed.toFixed(1)}s
            </p>
          )}
        </>
      ) : null}
    </Card>
  );
}
