// Storage and session helper
const THEME_KEY = "pocket_theme_mode";

export function loadUserTheme() {
  return localStorage.getItem(THEME_KEY) || "light";
}

export function saveSessionState(sessionId) {
  sessionStorage.setItem("pocket_session_id", sessionId);
}
