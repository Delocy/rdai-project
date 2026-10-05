import { BookOpenIcon, MagnifyingGlassIcon } from "@heroicons/react/20/solid";

import HowItWorksPage from "./pages/HowItWorksPage.jsx";
import SearchPage from "./pages/SearchPage.jsx";
import { ROUTES, useHashRoute } from "./router.js";

const PAGES = [
  ["search", ROUTES.search, MagnifyingGlassIcon, "Search"],
  ["how", ROUTES.how, BookOpenIcon, "How it works"],
];

export default function App() {
  const route = useHashRoute();

  return (
    <div className="app">
      <header className="topbar">
        <span className="wordmark">Visual Search</span>
        <span className="topbar-note">Demo catalogue · invented prices</span>
      </header>
      <div className="frame">
        <nav className="nav" aria-label="Pages">
          {PAGES.map(([key, href, Icon, label]) => (
            <a
              key={key}
              href={href}
              className={route === key ? "nav-item active" : "nav-item"}
              aria-current={route === key ? "page" : undefined}
            >
              <Icon className="icon" aria-hidden="true" />
              {label}
            </a>
          ))}
        </nav>
        <main className="page">
          {/* both stay mounted so a search survives visiting How it works */}
          <div hidden={route !== "search"}>
            <SearchPage />
          </div>
          <div hidden={route !== "how"}>
            <HowItWorksPage />
          </div>
        </main>
      </div>
    </div>
  );
}
