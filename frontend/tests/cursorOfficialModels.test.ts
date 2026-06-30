import { describe, expect, it } from "vitest";

import {
  CURSOR_OFFICIAL_MODEL_PRESET_ID,
  cursorOfficialModelSelection,
  cursorOfficialModelValue,
  isCursorOfficialModelSelection
} from "../src/cursorOfficialModels";

describe("cursorOfficialModels", () => {
  it("builds and recognizes cursor official model selections", () => {
    const selection = cursorOfficialModelSelection("composer-2.5");
    expect(selection.preset_id).toBe(CURSOR_OFFICIAL_MODEL_PRESET_ID);
    expect(isCursorOfficialModelSelection(selection)).toBe(true);
    expect(cursorOfficialModelValue(selection)).toBe("composer-2.5");
  });
});
