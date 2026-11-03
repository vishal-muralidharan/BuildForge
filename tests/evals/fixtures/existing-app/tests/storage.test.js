import test from "node:test";
import assert from "node:assert/strict";
import { getSessionKey, getThemeKey } from "../src/storage.js";

test("storage keys are defined", () => {
  assert.equal(getSessionKey(), "invented_notes_user_session");
  assert.equal(getThemeKey(), "invented_notes_app_theme");
});

