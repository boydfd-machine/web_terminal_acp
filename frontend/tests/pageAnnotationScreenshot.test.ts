import { afterEach, describe, expect, it, vi } from "vitest";

import { canCapturePageAnnotationScreenshot, capturePageAnnotationScreenshot } from "../src/pageAnnotationScreenshot";

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  delete window.electronAPI;
});

describe("page annotation screenshots", () => {
  it("captures from the Electron bridge and crops the selected viewport area", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-08T12:34:56.789Z"));
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 100 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 50 });
    const drawImage = vi.fn();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => ({
      drawImage
    } as unknown as CanvasRenderingContext2D));
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => {
      callback(new Blob(["png"], { type: "image/png" }));
    });
    class FakeImage extends EventTarget {
      naturalWidth = 200;
      naturalHeight = 100;

      set src(_value: string) {
        queueMicrotask(() => this.dispatchEvent(new Event("load")));
      }
    }
    vi.stubGlobal("Image", FakeImage);
    window.electronAPI = {
      isElectron: true,
      platform: "linux",
      capturePageScreenshot: vi.fn().mockResolvedValue({
        dataUrl: "data:image/png;base64,ZmFrZQ==",
        width: 200,
        height: 100
      })
    };

    const file = await capturePageAnnotationScreenshot({
      left: 10,
      top: 5,
      width: 20,
      height: 10
    });

    expect(window.electronAPI.capturePageScreenshot).toHaveBeenCalled();
    expect(drawImage.mock.calls[0].slice(1)).toEqual([20, 10, 40, 20, 0, 0, 40, 20]);
    expect(file.name).toBe("debug-annotation-2026-06-08T12-34-56-789Z.png");
    expect(file.type).toBe("image/png");
  });

  it("uses decoded Electron image dimensions when bridge metadata is viewport-sized", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 100 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 50 });
    const drawImage = vi.fn();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => ({
      drawImage
    } as unknown as CanvasRenderingContext2D));
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => {
      callback(new Blob(["png"], { type: "image/png" }));
    });
    class FakeImage extends EventTarget {
      naturalWidth = 200;
      naturalHeight = 100;

      set src(_value: string) {
        queueMicrotask(() => this.dispatchEvent(new Event("load")));
      }
    }
    vi.stubGlobal("Image", FakeImage);
    window.electronAPI = {
      isElectron: true,
      platform: "linux",
      capturePageScreenshot: vi.fn().mockResolvedValue({
        dataUrl: "data:image/png;base64,ZmFrZQ==",
        width: 100,
        height: 50
      })
    };

    await capturePageAnnotationScreenshot({
      left: 10,
      top: 5,
      width: 20,
      height: 10
    });

    expect(drawImage.mock.calls[0].slice(1)).toEqual([20, 10, 40, 20, 0, 0, 40, 20]);
  });

  it("passes the selected area to Electron and does not re-crop exact bridge captures", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 100 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 50 });
    const drawImage = vi.fn();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => ({
      drawImage
    } as unknown as CanvasRenderingContext2D));
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => {
      callback(new Blob(["png"], { type: "image/png" }));
    });
    class FakeImage extends EventTarget {
      naturalWidth = 20;
      naturalHeight = 10;

      set src(_value: string) {
        queueMicrotask(() => this.dispatchEvent(new Event("load")));
      }
    }
    vi.stubGlobal("Image", FakeImage);
    const selection = {
      left: 10,
      top: 5,
      width: 20,
      height: 10
    };
    window.electronAPI = {
      isElectron: true,
      platform: "linux",
      capturePageScreenshot: vi.fn().mockResolvedValue({
        dataUrl: "data:image/png;base64,ZmFrZQ==",
        width: 20,
        height: 10,
        capturedRect: selection
      })
    };

    await capturePageAnnotationScreenshot(selection);

    expect(window.electronAPI.capturePageScreenshot).toHaveBeenCalledWith(selection);
    expect(drawImage.mock.calls[0].slice(1)).toEqual([0, 0, 20, 10, 0, 0, 20, 10]);
  });

  it("reports unavailable browser screenshot capture without an Electron bridge", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {}
    });

    await expect(capturePageAnnotationScreenshot({
      left: 0,
      top: 0,
      width: 10,
      height: 10
    })).rejects.toThrow("Screenshot capture is unavailable in this browser.");
  });

  it("asks browser capture for the current tab and rejects monitor shares", async () => {
    const stop = vi.fn();
    const track = {
      stop,
      getSettings: () => ({ displaySurface: "monitor" })
    };
    const getDisplayMedia = vi.fn().mockResolvedValue({
      getTracks: () => [track],
      getVideoTracks: () => [track]
    } as unknown as MediaStream);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getDisplayMedia }
    });

    await expect(capturePageAnnotationScreenshot({
      left: 0,
      top: 0,
      width: 10,
      height: 10
    })).rejects.toThrow("Select the current browser tab");

    expect(getDisplayMedia).toHaveBeenCalledWith(expect.objectContaining({
      audio: false,
      preferCurrentTab: true,
      selfBrowserSurface: "include",
      video: expect.objectContaining({ displaySurface: "browser" })
    }));
    expect(stop).toHaveBeenCalled();
  });

  it("reports whether any page screenshot capture path is available", () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {}
    });
    expect(canCapturePageAnnotationScreenshot()).toBe(false);

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getDisplayMedia: vi.fn() }
    });
    expect(canCapturePageAnnotationScreenshot()).toBe(true);

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {}
    });
    window.electronAPI = {
      isElectron: true,
      platform: "linux",
      capturePageScreenshot: vi.fn()
    };
    expect(canCapturePageAnnotationScreenshot()).toBe(true);
  });
});
