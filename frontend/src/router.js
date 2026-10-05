import { useEffect, useState } from "react";

export const ROUTES = { search: "#/", how: "#/how-it-works" };

export function routeFor(hash) {
  return hash === ROUTES.how ? "how" : "search";
}

// current page from the URL hash, so the back button works
export function useHashRoute() {
  const [route, setRoute] = useState(() => routeFor(window.location.hash));
  useEffect(() => {
    const update = () => setRoute(routeFor(window.location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
