export default function Sidebar({ history, onPick }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="mark">V</span>
        Visual Search
      </div>

      <div className="side-label">Recent</div>
      {history.length === 0 ? (
        <div className="side-empty">Nothing yet</div>
      ) : (
        history.map((entry, i) => (
          <button
            key={`${entry.query}-${i}`}
            className={`side-item${i === 0 ? " active" : ""}`}
            onClick={() => onPick(entry.query)}
            title={entry.query}
          >
            <span>{entry.query || "image only"}</span>
            <span className="count">{entry.count}</span>
          </button>
        ))
      )}
    </aside>
  );
}
