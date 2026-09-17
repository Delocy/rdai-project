import { useEffect, useRef, useState } from "react";

import { loadKey, saveKey, search } from "./api.js";
import Composer from "./components/Composer.jsx";
import Results from "./components/Results.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { Constraints, Trace } from "./components/Trace.jsx";

export default function App() {
  const [query, setQuery] = useState("");
  const [image, setImage] = useState(null);
  const [apiKey, setApiKey] = useState(loadKey);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const started = useRef(0);

  useEffect(() => saveKey(apiKey), [apiKey]);

  useEffect(() => {
    if (!busy) return;
    started.current = Date.now();
    setElapsed(0);
    const id = setInterval(() => setElapsed((Date.now() - started.current) / 1000), 100);
    return () => clearInterval(id);
  }, [busy]);

  async function run() {
    if (!query.trim() && !image) {
      setError("Type a request, add an image, or both.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await search({ query, image, apiKey });
      setData(result);
      setHistory((prev) => [{ query, count: result.results.length }, ...prev].slice(0, 12));
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <Sidebar history={history} onPick={setQuery} />

      <main className="page">
        <div className="page-inner">
          <h1>Visual Product Search</h1>
          <p className="subtitle">
            Describe what you want, drop in a reference image, or both. The agent checks its own
            results and rewrites the query when they fall short.
          </p>

          <Composer
            query={query}
            setQuery={setQuery}
            image={image}
            setImage={setImage}
            apiKey={apiKey}
            setApiKey={setApiKey}
            onSubmit={run}
            busy={busy}
            elapsed={elapsed}
          />

          {error ? <div className="callout">{error}</div> : null}

          {busy ? (
            <div className="callout plain">
              Searching. Ranking runs a vision model, so this can take a while.
            </div>
          ) : null}

          {data ? (
            <>
              {data.degraded ? (
                <div className="callout">
                  No language model was reachable, so these results come from vector search alone,
                  without query parsing or ranking.
                </div>
              ) : null}

              <h2>Understood as</h2>
              <Constraints constraints={data.constraints} />

              <h2>Results ({data.results.length})</h2>
              <Results items={data.results} />

              {data.trace.length ? (
                <>
                  <h2>How it got there</h2>
                  <Trace steps={data.trace} />
                </>
              ) : null}
            </>
          ) : null}
        </div>
      </main>
    </div>
  );
}
