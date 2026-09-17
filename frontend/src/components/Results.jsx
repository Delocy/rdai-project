function Card({ item }) {
  return (
    <div className="card">
      {item.image_url ? <img src={item.image_url} alt="" loading="lazy" /> : null}
      <div className="body">
        <div className="name">{item.title}</div>
        <div className="meta">
          <span className="price">{Number(item.price).toFixed(2)}</span>
          {item.colour ? <span>{item.colour}</span> : null}
          {item.category ? <span>{item.category}</span> : null}
        </div>
        {item.rationale ? <div className="why">{item.rationale}</div> : null}
      </div>
    </div>
  );
}

export default function Results({ items }) {
  if (!items.length) {
    return <p className="muted">Nothing matched. Try relaxing the request.</p>;
  }
  return (
    <div className="grid">
      {items.map((item) => (
        <Card key={item.id} item={item} />
      ))}
    </div>
  );
}
