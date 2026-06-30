import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppAuthGate } from "../src/AppAuthGate";
import { clearAuthToken, writeAuthTokens } from "../src/auth";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

async function renderAuthGate(): Promise<void> {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  await act(async () => {
    root?.render(
      <QueryClientProvider client={queryClient}>
        <AppAuthGate>
          {() => <section data-testid="authenticated-app">Authenticated app</section>}
        </AppAuthGate>
      </QueryClientProvider>
    );
  });
}

async function waitForText(text: string): Promise<void> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (container?.textContent?.includes(text)) {
      return;
    }
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
  throw new Error(`Timed out waiting for text: ${text}. Current text: ${container?.textContent ?? ""}`);
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  queryClient?.clear();
  container?.remove();
  root = null;
  container = null;
  queryClient = null;
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("AppAuthGate", () => {
  it("returns to the login gate when auth tokens are cleared externally", async () => {
    writeAuthTokens("access-1", "refresh-1");
    vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(jsonResponse({
      enabled: true,
      mode: "password"
    })));

    await renderAuthGate();
    await waitForText("Authenticated app");

    act(() => {
      clearAuthToken();
    });

    await waitForText("Login secret");
  });
});
