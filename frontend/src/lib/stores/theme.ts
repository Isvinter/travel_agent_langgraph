import { writable } from "svelte/store";

type Theme = "light" | "dark";

function getInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem("theme");
    if (stored === "light" || stored === "dark") return stored;
  } catch {}
  if (window.matchMedia("(prefers-color-scheme: light)").matches) return "light";
  return "dark";
}

function applyTheme(theme: Theme) {
  document.documentElement.className = theme;
}

export const theme = writable<Theme>(getInitialTheme());

theme.subscribe((value) => {
  applyTheme(value);
  try {
    localStorage.setItem("theme", value);
  } catch {}
});

export function toggleTheme() {
  theme.update((t) => (t === "dark" ? "light" : "dark"));
}
