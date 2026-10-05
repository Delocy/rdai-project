import { useEffect, useRef, useState } from "react";

import { search } from "./api.js";
import Composer from "./components/Composer.jsx";
import Results from "./components/Results.jsx";
import { Constraints, Relaxed, Trace } from "./components/Trace.jsx";

// matched to the sample catalogue: the first group has real matches, the others don't
// (no red sports shoes under 40, no blue jackets) to show the repair and the "no" answer
const EXAMPLES = [
  { label: "Try:", queries: ["black watch", "white sneakers", "brown handbag", "pink top under 30"] },
  { label: "Watch it repair:", queries: ["red running shoes under 40"] },
  { label: "Watch it say no:", queries: ["blue denim jacket"] },
];

export default function App() {
  const [query, setQuery] = useState("");
  const [image, setImage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [liveTrace, setLiveTrace] = useState([]);
  const started = useRef(0);

  useEffect(() => {
    if (!busy) return;
    started.current = Date.now();
    setElapsed(0);
    const id = setInterval(() => setElapsed((Date.now() - started.current) / 1000), 100);
    return () => clearInterval(id);
  }, [busy]);

  async function run(text = query) {
    if (!text.trim() && !image) {
      setError("Type a request, add an image, or both.");
      return;
    }
    setBusy(true);
    setError(null);
    setData(null);
    setLiveTrace([]);
    try {
      const result = await search({
        query: text,
        image,
        onStep: (step) => setLiveTrace((prev) => [...prev, step]),
      });
      setData(result);
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setBusy(false);
    }
  }

  function runExample(text) {
    setQuery(text);
    run(text);
  }

  // data.trace once a search finishes; liveTrace while running, or as the
  // last-known progress if it errored out partway through
  const trace = data?.trace ?? liveTrace;
  const showTrace = busy || trace.length > 0;

  return (
    <main className="page">
      <div className="page-inner">
        <h1>Visual Product Search</h1>
        <p className="subtitle">
          Describe what you want, drop in a reference image, or both. This is a demo catalogue
          with invented prices, not a shop, it is to show an agent that checks its own
          results, rewrites the query when they fall short, and says so when nothing
          matches instead of faking a good answer.
        </p>

        <Composer
          query={query}
          setQuery={setQuery}
          image={image}
          setImage={setImage}
          onSubmit={run}
          busy={busy}
          elapsed={elapsed}
        />

        <div className="examples">
          {EXAMPLES.map(({ label, queries }) => (
            <div className="examples-group" key={label}>
              <span className="examples-label">{label}</span>
              {queries.map((example) => (
                <button
                  key={example}
                  type="button"
                  className="chip pick"
                  onClick={() => runExample(example)}
                  disabled={busy}
                >
                  {example}
                </button>
              ))}
            </div>
          ))}
        </div>

        {error ? <div className="callout">{error}</div> : null}

        {showTrace ? (
          <>
            <h2>{busy ? "Thinking" : "How it got there"}</h2>
            <Trace steps={trace} live={busy} />
          </>
        ) : null}

        {data ? (
          <>
            {data.degraded ? (
              <div className="callout">
                The LLM didn't answer this time, so this search fell back to reading the request
                with rules and ranking by visual similarity.
              </div>
            ) : null}

            <h2>Understood as</h2>
            <Constraints constraints={data.requested ?? data.constraints} />
            <Relaxed requested={data.requested} applied={data.constraints} />

            <h2>Results ({data.results.length})</h2>
            {data.ranker === "similarity" && !data.degraded ? (
              <p className="muted mode">
                Ranked by visual similarity (CLIP). No LLM involved - an optional one can re-rank
                by looking at the photos.
              </p>
            ) : null}
            <Results items={data.results} ranker={data.ranker} degraded={data.degraded} />
          </>
        ) : null}
      </div>
    </main>
  );
}
