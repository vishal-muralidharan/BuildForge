import { getSessionKey, getThemeKey, findNoteById } from "./storage.js";

export function initApp() {
  return {
    sessionKey: getSessionKey(),
    themeKey: getThemeKey(),
    findNote: findNoteById,
  };
}
