export function PageHeader({ title, subtitle }) {
  return (
    <header className="page-header">
      <h1>{title}</h1>
      {subtitle ? <p>{subtitle}</p> : null}
    </header>
  );
}

export function Card({ title, aside, children }) {
  return (
    <section className="card">
      {title || aside ? (
        <div className="card-head">
          {title ? <h2>{title}</h2> : null}
          {aside ? <div className="card-aside">{aside}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Badge({ tone = "neutral", icon: Icon, children }) {
  return (
    <span className={`badge badge-${tone}`}>
      {Icon ? <Icon className="icon" aria-hidden="true" /> : null}
      {children}
    </span>
  );
}

export function Banner({ tone = "warning", icon: Icon, className = "", children }) {
  return (
    <div className={`banner banner-${tone} ${className}`.trim()} role={tone === "critical" ? "alert" : "status"}>
      {Icon ? <Icon className="icon" aria-hidden="true" /> : null}
      <div>{children}</div>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon className="icon" aria-hidden="true" />
      </span>
      <strong>{title}</strong>
      <p>{children}</p>
    </div>
  );
}

export function Button({ variant = "secondary", icon: Icon, spinning = false, children, ...props }) {
  return (
    <button type="button" className={`button button-${variant}`} {...props}>
      {Icon ? <Icon className={spinning ? "icon spin" : "icon"} aria-hidden="true" /> : null}
      {children}
    </button>
  );
}
