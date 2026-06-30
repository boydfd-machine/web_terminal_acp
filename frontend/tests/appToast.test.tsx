import { QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../src/api";
import { AppQueryErrorBridge, queryClient } from "../src/AppQueryErrorBridge";
import { AppToastProvider } from "../src/components/AppToastProvider";
import { I18nProvider } from "../src/i18n";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;

function renderToastBridge() {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => {
    root?.render(
      <I18nProvider initialLocale="en-US">
        <AppToastProvider>
          <QueryClientProvider client={queryClient}>
            <AppQueryErrorBridge />
          </QueryClientProvider>
        </AppToastProvider>
      </I18nProvider>
    );
  });
}

async function failQuery(error: unknown) {
  await queryClient.fetchQuery({
    queryKey: ["toast-test", Math.random()],
    queryFn: async () => {
      throw error;
    },
    retry: false
  }).catch(() => {});
}

async function failSuppressedQuery(error: unknown) {
  await queryClient.fetchQuery({
    queryKey: ["toast-test-suppressed", Math.random()],
    queryFn: async () => {
      throw error;
    },
    meta: { suppressApiErrorToast: true },
    retry: false
  }).catch(() => {});
}

async function waitForRequests() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  queryClient.clear();
  vi.restoreAllMocks();
});

describe("global API error toast", () => {
  it("shows API failures from React Query as an alert toast", async () => {
    renderToastBridge();

    await act(async () => {
      await failQuery(new ApiError(500, "Internal Server Error", "server exploded"));
    });
    await waitForRequests();

    const toast = document.body.querySelector(".app-toast");
    expect(toast?.getAttribute("role")).toBe("alert");
    expect(toast?.textContent).toContain("API request failed");
    expect(toast?.textContent).toContain("HTTP 500: server exploded");
  });

  it("ignores repeated identical failures inside the dedupe window", async () => {
    const error = new ApiError(500, "Internal Server Error", "same failure");
    renderToastBridge();
    await act(async () => {
      await failQuery(error);
    });
    await waitForRequests();
    expect(document.body.querySelector(".app-toast")?.textContent).toContain("same failure");

    const firstToast = document.body.querySelector(".app-toast");
    await act(async () => {
      await failQuery(error);
    });

    expect(document.body.querySelector(".app-toast")).toBe(firstToast);
  });

  it("does not toast API errors from queries that opt out", async () => {
    renderToastBridge();

    await act(async () => {
      await failSuppressedQuery(new ApiError(415, "Unsupported Media Type", "binary preview"));
    });
    await waitForRequests();

    expect(document.body.querySelector(".app-toast")).toBeNull();
  });
});
