import { chromium } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const clientId = "00000000-0000-0000-0000-000000000001";
const windowId = process.env.PLAYWRIGHT_WINDOW_ID ?? "253d515b-4479-4008-ad34-b3797298a871";
const path = `/clients/${encodeURIComponent(clientId)}/terminals/${encodeURIComponent(windowId)}`;

async function readMetrics(page) {
  return page.evaluate(() => {
    const pane = document.querySelector(".terminal-pane-desktop, .terminal-pane-phone");
    const stage = document.querySelector(".terminal-stage");
    const workspace = document.querySelector(".workspace");
    const viewport = document.querySelector(".xterm-viewport");
    const screen = document.querySelector(".xterm-screen");
    const canvas = document.querySelector(".xterm-screen canvas");
    const rows = document.querySelector(".xterm-rows");
    const textarea = document.querySelector(".xterm-helper-textarea");
    if (!(pane instanceof HTMLElement) || !(viewport instanceof HTMLElement)) {
      return null;
    }
    const style = window.getComputedStyle(pane);
    const paddingY = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    const paneContentHeight = pane.clientHeight - paddingY;
    const viewportHeight = viewport.getBoundingClientRect().height;
    const canvasHeight = canvas instanceof HTMLElement ? canvas.getBoundingClientRect().height : 0;
    let renderedHeight = canvasHeight;
    if (rows instanceof HTMLElement) {
      const lineElements = rows.querySelectorAll("div");
      if (lineElements.length > 0) {
        const first = lineElements[0].getBoundingClientRect();
        const last = lineElements[lineElements.length - 1].getBoundingClientRect();
        renderedHeight = Math.max(renderedHeight, last.bottom - first.top);
      } else {
        renderedHeight = Math.max(renderedHeight, rows.getBoundingClientRect().height);
      }
    }
    const viewportMode = document.querySelector(".terminal-stage-phone")
      ? "phone"
      : document.querySelector(".terminal-stage-fixed")
        ? "fixed"
        : "desktop";
    return {
      viewportMode,
      paneContentHeight,
      viewportHeight,
      canvasHeight,
      renderedHeight,
      screenHeight: screen instanceof HTMLElement ? screen.getBoundingClientRect().height : 0,
      stageHeight: stage instanceof HTMLElement ? stage.clientHeight : 0,
      workspaceHeight: workspace instanceof HTMLElement ? workspace.clientHeight : 0,
      cols: Number(textarea?.getAttribute("aria-colcount") ?? "0"),
      rows: Number(textarea?.getAttribute("aria-rowcount") ?? "0"),
      fillRatio: paneContentHeight > 0 ? viewportHeight / paneContentHeight : 0,
      canvasFillRatio: viewportHeight > 0 ? canvasHeight / viewportHeight : 0,
      renderedFillRatio: paneContentHeight > 0 ? renderedHeight / paneContentHeight : 0,
    };
  });
}

async function sample(label, page, durationMs) {
  const samples = [];
  const started = Date.now();
  while (Date.now() - started < durationMs) {
    samples.push({ t: Date.now() - started, ...(await readMetrics(page)) });
    await page.waitForTimeout(250);
  }
  console.log(`\n=== ${label} ===`);
  for (const sample of samples) {
    console.log(JSON.stringify(sample));
  }
  const last = samples.at(-1);
  return last;
}

const launchOptions = { headless: true };
if (process.env.PLAYWRIGHT_EXECUTABLE_PATH) {
  launchOptions.executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
  launchOptions.args = ["--no-sandbox", "--disable-dev-shm-usage"];
}

const browser = await chromium.launch(launchOptions);

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log("Fast load:");
  await page.goto(`${baseURL}${path}`, { waitUntil: "networkidle", timeout: 60_000 });
  await page.waitForSelector(".xterm-viewport", { timeout: 30_000 });
  await page.waitForTimeout(3000);
  const fast = await sample("fast", page, 12000);
  await page.screenshot({ path: "/tmp/terminal-fit-fast.png", fullPage: false });
  console.log(`fast final fillRatio=${fast?.fillRatio} renderedFill=${fast?.renderedFillRatio} rows=${fast?.rows} mode=${fast?.viewportMode}`);

  await context.close();
  const slowContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const slowPage = await slowContext.newPage();
  await slowPage.route("**/api/clients/*/tree", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 5000));
    await route.continue();
  });

  console.log("\nSlow tree load:");
  await slowPage.goto(`${baseURL}${path}`, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await slowPage.waitForSelector(".xterm-viewport", { timeout: 30_000 });
  await slowPage.waitForTimeout(8000);
  const slow = await sample("slow-tree", slowPage, 25_000);
  await slowPage.screenshot({ path: "/tmp/terminal-fit-slow.png", fullPage: false });
  console.log(`slow final fillRatio=${slow?.fillRatio} renderedFill=${slow?.renderedFillRatio} rows=${slow?.rows} mode=${slow?.viewportMode}`);

  const ok = (metrics) =>
    (metrics?.fillRatio ?? 0) >= 0.9
    && (metrics?.renderedFillRatio ?? 0) >= 0.85;

  const pass = ok(fast) && ok(slow);
  if (!pass) {
    console.error("FAIL: expected fillRatio>=0.9 and renderedFillRatio>=0.85");
  }
  process.exitCode = pass ? 0 : 1;
} finally {
  await browser.close();
}
