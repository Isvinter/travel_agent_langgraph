import { writable, derived } from "svelte/store";

export type Route =
  | { page: "pipeline" }
  | { page: "articles" }
  | { page: "article"; id: number };

function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, "") || "/";

  if (path === "/" || path === "" || path === "pipeline") {
    return { page: "pipeline" };
  }

  const articlesMatch = path.match(/^articles\/(\d+)$/);
  if (articlesMatch) {
    return { page: "article", id: parseInt(articlesMatch[1], 10) };
  }

  if (path === "articles") {
    return { page: "articles" };
  }

  return { page: "pipeline" };
}

function currentHash(): string {
  return typeof window !== "undefined" ? window.location.hash : "";
}

export const route = writable<Route>(parseHash(currentHash()));

export function navigateTo(route: Route) {
  let hash: string;
  switch (route.page) {
    case "pipeline":
      hash = "#/";
      break;
    case "articles":
      hash = "#/articles";
      break;
    case "article":
      hash = `#/articles/${route.id}`;
      break;
  }
  window.location.hash = hash;
}

// Listen for hash changes (back/forward browser buttons)
if (typeof window !== "undefined") {
  window.addEventListener("hashchange", () => {
    route.set(parseHash(window.location.hash));
  });
}
