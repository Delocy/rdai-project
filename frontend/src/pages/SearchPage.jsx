import { ClockIcon, ExclamationTriangleIcon, MagnifyingGlassIcon, XCircleIcon } from "@heroicons/react/20/solid";
import { useEffect, useRef, useState } from "react";

import { ApiError, search } from "../api.js";
import ResultsCard from "../components/ResultsCard.jsx";
import SearchCard from "../components/SearchCard.jsx";
import TraceCard from "../components/TraceCard.jsx";
import UnderstoodCard from "../components/UnderstoodCard.jsx";
import { Banner, Card, EmptyState, PageHeader } from "../components/ui.jsx";
import { errorMessage, fallbackNotes } from "../copy.js";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [image, setImage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const [response, setResponse] = useState(null);
  const [steps, setSteps] = useState([]);
  const [withPhoto, setWithPhoto] = useState(false);
  const started = useRef(0);
  const running = useRef(false);

  useEffect(() => {
    if (!busy) return undefined;
    const id = setInterval(() => setElapsed((Date.now() - started.current) / 1000), 100);
    return () => clearInterval(id);
  }, [busy]);

  async function run(text = query) {
    // a ref, not state: two clicks in the same tick must not start two searches
    if (running.current || (!text.trim() && !image)) return;
    running.current = true;
    started.current = Date.now();
    setQuery(text);
    setBusy(true);
    setElapsed(0);
    setError(null);
    setResponse(null);
    setSteps([]);
    setWithPhoto(Boolean(image));
    try {
      const result = await search({
        query: text,
        image,
        onStep: (step) => setSteps((previous) => [...previous, step]),
      });
      setResponse(result);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : new ApiError(0, String(caught)));
    } finally {
      setElapsed((Date.now() - started.current) / 1000);
      setBusy(false);
      running.current = false;
    }
  }

  const message = error ? errorMessage(error) : null;
  const messageIcon = error?.status === 429 ? ClockIcon : message?.tone === "critical" ? XCircleIcon : ExclamationTriangleIcon;
  const fallbacks = response?.degraded ? fallbackNotes(response.trace) : [];
  const begun = busy || response !== null || steps.length > 0;

  return (
    <div className="page-body">
      <PageHeader
        title="Search"
        subtitle="Describe a product, add a photo, or both. The agent checks its own results and says when nothing fits."
      />
      <SearchCard query={query} setQuery={setQuery} image={image} setImage={setImage} onSearch={run} busy={busy} />
      {message ? (
        <Banner tone={message.tone} icon={messageIcon}>
          {message.text}
        </Banner>
      ) : null}
      {fallbacks.length ? (
        <Banner tone="warning" icon={ExclamationTriangleIcon}>
          {fallbacks.join(" ")}
        </Banner>
      ) : null}
      {begun ? (
        <div className="columns">
          <div className="column-wide">{busy || response ? <ResultsCard response={response} /> : null}</div>
          <div className="column-narrow">
            {response ? <UnderstoodCard response={response} withPhoto={withPhoto} /> : null}
            <TraceCard steps={response ? response.trace : steps} live={busy} elapsed={elapsed} withPhoto={withPhoto} />
          </div>
        </div>
      ) : error ? null : (
        <Card>
          <EmptyState icon={MagnifyingGlassIcon} title="Search the catalogue">
            300 fashion products with photos. Try an example above, or add a photo of something you like.
          </EmptyState>
        </Card>
      )}
    </div>
  );
}
