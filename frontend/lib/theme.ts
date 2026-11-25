export type ThemeChoice = "light" | "dark" | "system";

export const THEME_KEY = "nexus-theme";
const CHANGE_EVENT = "nexus-theme-change";

// Runs in <head> before paint; "system" leaves data-theme unset so prefers-color-scheme decides.
export const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;

// The <html> attribute is the source of truth: the head script seeds it from storage.
export function readTheme(): ThemeChoice {
  const current = document.documentElement.getAttribute("data-theme");
  return current === "light" || current === "dark" ? current : "system";
}

export function applyTheme(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
  try {
    if (choice === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, choice);
  } catch {
    // Private mode / blocked storage: the choice still applies for this page view.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function subscribeTheme(onChange: () => void) {
  window.addEventListener(CHANGE_EVENT, onChange);
  return () => window.removeEventListener(CHANGE_EVENT, onChange);
}
