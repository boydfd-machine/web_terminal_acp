import { createRequire } from "node:module";

import { describe, expect, it } from "vitest";

const require = createRequire(import.meta.url);
const { normalizePageCaptureRect } = require("../electron/pageCapture.cjs") as {
  normalizePageCaptureRect: (selection: unknown) => {
    x: number;
    y: number;
    left: number;
    top: number;
    width: number;
    height: number;
  } | null;
};

describe("Electron page capture helpers", () => {
  it("normalizes annotation selections into Electron capturePage rectangles", () => {
    expect(normalizePageCaptureRect({
      left: 10.4,
      top: 20.6,
      width: 30.2,
      height: 40.8
    })).toEqual({
      x: 10,
      y: 21,
      left: 10,
      top: 21,
      width: 30,
      height: 41
    });
  });

  it("rejects invalid selections and clamps the origin", () => {
    expect(normalizePageCaptureRect(null)).toBeNull();
    expect(normalizePageCaptureRect({ left: 0, top: 0, width: Number.NaN, height: 10 })).toBeNull();
    expect(normalizePageCaptureRect({ left: -4, top: -2, width: 0, height: 0 })).toEqual({
      x: 0,
      y: 0,
      left: 0,
      top: 0,
      width: 1,
      height: 1
    });
  });
});
