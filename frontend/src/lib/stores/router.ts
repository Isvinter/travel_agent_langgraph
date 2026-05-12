import { writable } from "svelte/store";

export type Route =
  | { page: "pipeline" }
  | { page: "articles" }
  | { page: "article"; id: number }
  | { page: "draft"; id: number }
  | { page: "photobooks" }
  | { page: "photobook"; id: number }
  | { page: "calendars" }
  | { page: "calendar"; id: number };

export function parseHash(hash: string): Route {
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

  const draftMatch = path.match(/^draft\/(\d+)$/);
  if (draftMatch) {
    return { page: "draft", id: parseInt(draftMatch[1], 10) };
  }

  const photobooksMatch = path.match(/^photobooks\/(\d+)$/);
  if (photobooksMatch) {
    return { page: "photobook", id: parseInt(photobooksMatch[1], 10) };
  }

  if (path === "photobooks") {
    return { page: "photobooks" };
  }

  const calendarsMatch = path.match(/^calendars\/(\d+)$/);
  if (calendarsMatch) {
    return { page: "calendar", id: parseInt(calendarsMatch[1], 10) };
  }

  if (path === "calendars") {
    return { page: "calendars" };
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
    case "draft":
      hash = `#/draft/${route.id}`;
      break;
    case "photobooks":
      hash = "#/photobooks";
      break;
    case "photobook":
      hash = `#/photobooks/${route.id}`;
      break;
    case "calendars":
      hash = "#/calendars";
      break;
    case "calendar":
      hash = `#/calendars/${route.id}`;
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
