const USER_SESSION_KEY = "invented_notes_user_session";
const APP_THEME_KEY = "invented_notes_app_theme";

export function getSessionKey() {
  return USER_SESSION_KEY;
}

export function getThemeKey() {
  return APP_THEME_KEY;
}

export function findNoteById(notes, id) {
  // Buggy implementation: strict equality with string ID fails when note.id is a number
  return notes.find((note) => note.id === id) || null;
}

