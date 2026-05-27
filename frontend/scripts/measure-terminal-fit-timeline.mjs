import { chromium } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:80";
const path = `/clients/00000000-0000-0000-0000-000000000001/terminals/253d515b-4479-4008-ad34-b3797298a871`;

async function readMetrics(page) {
  return page.evaluate(() => {
    const pane = document.querySelector(".terminal-pane-desktop, .terminal-pane-phone");
    const viewport = document.querySelector(".xterm-viewport");
    const canvas = document.querySelector(".xterm-screen canvas");
    const textarea = document.querySelector(".xterm-helper-textarea");
    if (!(pane instanceof HTMLElement) || !(viewport instanceof HTMLElement)) {
      return { ready: false };
    }
    const style = window.getComputedStyle(pane);
    const paddingY = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    const paneContentHeight = pane.clientHeight - paddingY;
    const viewportHeight = viewport.getBoundingClientRect().height;
    const canvasHeight = canvas instanceof HTMLElement ? canvas.getBoundingClientRect().height : 0;
    const rows = Number(textarea?.getAttribute("aria-rowcount") ?? "0");
    const cols = Number(textarea?.getAttribute("aria-colcount") ?? "0");
    return {
      ready: true,
      rows,
      cols,
      paneContentHeight,
      viewportHeight,
      canvasHeight,
      fillRatio: paneContentHeight > 0 ? viewportHeight / paneContentHeight : 0,
      canvasFillRatio: viewportHeight > 0 ? canvasHeight / viewportHeight : 0,
      connected: document.querySelector(".terminal-connection-status") === null,
    };
  });
}

const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  await page.route("**/api/clients/*/tree", async (route) => {
    await new Promise((r) => setTimeout(r, 6000));
    await route.continue();
  });

  const started = Date.now();
  await page.goto(`${baseURL}${path}`, { waitUntil: "commit", timeout: 60_000 });

  for (let elapsed = 0; elapsed <= 30_000; elapsed += 500) {
    const waitFor = elapsed - (Date.now() - started);
    if (waitFor > 0) {
      await page.waitForTimeout(waitFor);
    }
    const metrics = await readMetrics(page);
    console.log(JSON.stringify({ elapsed, ...metrics }));
    if (metrics.ready && metrics.canvasFillRatio < 0.85) {
      await page.screenshot({ path: `/tmp/terminal-half-${elapsed}.png` });
    }
  }
} finally {
  await browser.close();
}
