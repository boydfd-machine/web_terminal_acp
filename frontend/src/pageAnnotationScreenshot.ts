import type { PageAnnotationRect } from "./pageAnnotationEvidence";

type ElectronAnnotationCapture = {
  dataUrl: string;
  width: number;
  height: number;
  capturedRect?: PageAnnotationRect;
};

const SCREENSHOT_FILENAME_PREFIX = "debug-annotation";

export async function capturePageAnnotationScreenshot(selection: PageAnnotationRect): Promise<File> {
  const electronCapture = await captureFromElectron(selection);
  if (electronCapture !== null) {
    return cropDataUrlCapture(electronCapture, selection);
  }
  return cropDisplayMediaCapture(selection);
}

export function canCapturePageAnnotationScreenshot(): boolean {
  return window.electronAPI?.capturePageScreenshot !== undefined
    || navigator.mediaDevices?.getDisplayMedia !== undefined;
}

async function captureFromElectron(selection: PageAnnotationRect): Promise<ElectronAnnotationCapture | null> {
  const capture = window.electronAPI?.capturePageScreenshot;
  if (capture === undefined) {
    return null;
  }
  return capture(selection);
}

async function cropDisplayMediaCapture(selection: PageAnnotationRect): Promise<File> {
  if (navigator.mediaDevices?.getDisplayMedia === undefined) {
    throw new Error("Screenshot capture is unavailable in this browser.");
  }
  const stream = await navigator.mediaDevices.getDisplayMedia(currentTabCaptureOptions());
  try {
    assertCurrentTabCapture(stream);
    const video = await videoFromStream(stream);
    const source = {
      element: video,
      width: video.videoWidth,
      height: video.videoHeight
    };
    return cropSourceToFile(source, selection);
  } finally {
    stopStream(stream);
  }
}

async function cropDataUrlCapture(
  capture: ElectronAnnotationCapture,
  selection: PageAnnotationRect
): Promise<File> {
  const image = await imageFromDataUrl(capture.dataUrl);
  const sourceWidth = image.naturalWidth || capture.width;
  const sourceHeight = image.naturalHeight || capture.height;
  const source = {
    element: image,
    width: sourceWidth,
    height: sourceHeight
  };
  if (rectMatches(capture.capturedRect, selection)) {
    return cropSourceRectToFile(source, { left: 0, top: 0, width: sourceWidth, height: sourceHeight });
  }
  return cropSourceToFile(source, selection);
}

function currentTabCaptureOptions(): DisplayMediaStreamOptions {
  return {
    video: { displaySurface: "browser" } as MediaTrackConstraints,
    audio: false,
    preferCurrentTab: true,
    selfBrowserSurface: "include"
  } as DisplayMediaStreamOptions;
}

function assertCurrentTabCapture(stream: MediaStream): void {
  const track = stream.getVideoTracks()[0];
  const displaySurface = track?.getSettings?.().displaySurface;
  if (displaySurface !== undefined && displaySurface !== "browser") {
    throw new Error("Select the current browser tab to capture annotation screenshots.");
  }
}

function cropSourceToFile(
  source: { element: CanvasImageSource; width: number; height: number },
  selection: PageAnnotationRect
): Promise<File> {
  const crop = scaledSelection(selection, source.width, source.height);
  return cropSourceRectToFile(source, crop);
}

function cropSourceRectToFile(
  source: { element: CanvasImageSource; width: number; height: number },
  crop: PageAnnotationRect
): Promise<File> {
  const canvas = document.createElement("canvas");
  canvas.width = crop.width;
  canvas.height = crop.height;
  const context = canvas.getContext("2d");
  if (context === null) {
    throw new Error("Screenshot canvas is unavailable.");
  }
  context.drawImage(
    source.element,
    crop.left,
    crop.top,
    crop.width,
    crop.height,
    0,
    0,
    crop.width,
    crop.height
  );
  return canvasToPngFile(canvas, screenshotFilename());
}

function scaledSelection(
  selection: PageAnnotationRect,
  sourceWidth: number,
  sourceHeight: number
): PageAnnotationRect {
  const viewportWidth = Math.max(window.innerWidth, 1);
  const viewportHeight = Math.max(window.innerHeight, 1);
  const scaleX = sourceWidth / viewportWidth;
  const scaleY = sourceHeight / viewportHeight;
  const left = clamp(Math.round(selection.left * scaleX), 0, sourceWidth - 1);
  const top = clamp(Math.round(selection.top * scaleY), 0, sourceHeight - 1);
  const right = clamp(Math.round((selection.left + selection.width) * scaleX), left + 1, sourceWidth);
  const bottom = clamp(Math.round((selection.top + selection.height) * scaleY), top + 1, sourceHeight);
  return {
    left,
    top,
    width: right - left,
    height: bottom - top
  };
}

function rectMatches(first: PageAnnotationRect | undefined, second: PageAnnotationRect): boolean {
  return first !== undefined
    && first.left === second.left
    && first.top === second.top
    && first.width === second.width
    && first.height === second.height;
}

function videoFromStream(stream: MediaStream): Promise<HTMLVideoElement> {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.srcObject = stream;
  return new Promise((resolve, reject) => {
    video.addEventListener("loadedmetadata", () => {
      video.play().then(() => resolve(video)).catch(reject);
    }, { once: true });
    video.addEventListener("error", () => reject(new Error("Screenshot stream could not be loaded.")), { once: true });
  });
}

function imageFromDataUrl(dataUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.addEventListener("load", () => resolve(image), { once: true });
    image.addEventListener("error", () => reject(new Error("Screenshot image could not be loaded.")), { once: true });
    image.src = dataUrl;
  });
}

function canvasToPngFile(canvas: HTMLCanvasElement, filename: string): Promise<File> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob === null) {
        reject(new Error("Screenshot image could not be encoded."));
        return;
      }
      resolve(new File([blob], filename, { type: "image/png" }));
    }, "image/png");
  });
}

function stopStream(stream: MediaStream): void {
  for (const track of stream.getTracks()) {
    track.stop();
  }
}

function screenshotFilename(): string {
  return `${SCREENSHOT_FILENAME_PREFIX}-${new Date().toISOString().replace(/[:.]/g, "-")}.png`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
