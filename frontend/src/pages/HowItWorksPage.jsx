import {
  ArrowsUpDownIcon,
  CircleStackIcon,
  DocumentTextIcon,
  FunnelIcon,
  WrenchScrewdriverIcon,
} from "@heroicons/react/20/solid";

import { Card, PageHeader } from "../components/ui.jsx";

const LOOP = [
  [DocumentTextIcon, "1 · Read", "Rules pull a budget, a colour and a category out of the request, using the catalogue's own labels."],
  [FunnelIcon, "2 · Match", "The category and colour become the catalogue labels they name, matched word by word."],
  [
    CircleStackIcon,
    "3 · Retrieve",
    "CLIP embeds the text and/or photo; Qdrant returns the 24 nearest products that pass every filter.",
  ],
  [
    WrenchScrewdriverIcon,
    "4 · Repair",
    "With fewer than five matches: colour becomes a soft preference, then the budget widens, then the category goes.",
  ],
  [ArrowsUpDownIcon, "5 · Rank", "By visual similarity: how close CLIP places each product's photo to the request."],
];

// from scripts/evaluate.py; update with the README when it's rerun
const SCORES = [
  ["CLIP alone", "63%", "0%", "37%"],
  ["This search loop", "88%", "100%", "95%"],
];

export default function HowItWorksPage() {
  return (
    <div className="page-body">
      <PageHeader title="How it works" subtitle="What happens between typing a request and seeing results." />
      <div className="columns">
        <div className="column-wide">
          <Card title="The search loop">
            <ol className="loop">
              {LOOP.map(([Icon, title, text]) => (
                <li key={title} className="step">
                  <span className="step-icon">
                    <Icon className="icon" aria-hidden="true" />
                  </span>
                  <span>
                    <strong>{title}</strong>
                    <small>{text}</small>
                  </span>
                </li>
              ))}
            </ol>
          </Card>
          <Card title="How well it works">
            <table className="scores">
              <thead>
                <tr>
                  <th scope="col">
                    <span className="sr-only">Approach</span>
                  </th>
                  <th scope="col">Recall@5</th>
                  <th scope="col">Impossible requests handled</th>
                  <th scope="col">Correctly labelled</th>
                </tr>
              </thead>
              <tbody>
                {SCORES.map(([name, ...values], n) => (
                  <tr key={name} className={n === SCORES.length - 1 ? "ours" : undefined}>
                    <th scope="row">{name}</th>
                    {values.map((value, i) => (
                      <td key={i}>{value}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="subdued note">50 hand-labelled queries, scripts/evaluate.py</p>
          </Card>
        </div>
        <div className="column-narrow">
          <Card title="What's served">
            <dl className="facts">
              <dt>Model</dt>
              <dd>CLIP ViT-B/32, ONNX on CPU</dd>
              <dt>Database</dt>
              <dd>Qdrant · 300 products</dd>
              <dt>Endpoints</dt>
              <dd>
                POST /search
                <br />
                POST /embed
                <br />
                GET /ready
              </dd>
            </dl>
          </Card>
        </div>
      </div>
    </div>
  );
}
