import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ClientList } from "../src/components/ClientList";
import type { Client } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;

function makeClient(overrides: Partial<Client>): Client {
  return {
    id: "client-1",
    name: "Local client",
    status: "ONLINE",
    hostname: "workstation",
    install_path: null,
    version: "2.14.1",
    last_update_at: "2026-05-30T18:05:00Z",
    runtime: "local",
    last_seen_at: null,
    connected_at: null,
    created_at: "2026-05-30T18:00:00Z",
    updated_at: "2026-05-30T18:00:00Z",
    ...overrides
  };
}

function renderClientList(
  selectedClientId: string | null,
  options: {
    onUpdateClient?: (clientId: string) => void;
    onReregisterClient?: (client: Client) => void;
    onDeleteClient?: (client: Client) => void;
    reregisteringClientId?: string | null;
  } = {}
): void {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);

  act(() => {
    root?.render(
      <ClientList
        clients={[
          makeClient({ id: "client-1", name: "Local client" }),
          makeClient({
            id: "client-2",
            name: "Remote client",
            runtime: "remote",
            hostname: "remote-host",
            last_update_at: "2026-05-30T05:15:00Z"
          })
        ]}
        selectedClientId={selectedClientId}
        updatingClientId={null}
        reregisteringClientId={options.reregisteringClientId ?? null}
        deletingClientId={null}
        onSelectClient={() => {}}
        onUpdateClient={options.onUpdateClient ?? (() => {})}
        onReregisterClient={options.onReregisterClient ?? (() => {})}
        onDeleteClient={options.onDeleteClient ?? (() => {})}
      />
    );
  });
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  vi.restoreAllMocks();
});

describe("ClientList", () => {
  it("shows only name and status for clients that are not selected", () => {
    renderClientList("client-1");

    const cards = Array.from(container?.querySelectorAll(".client-card") ?? []);
    expect(cards).toHaveLength(2);
    expect(cards[1].textContent).toContain("Remote client");
    expect(cards[1].textContent).toContain("ONLINE");
    expect(cards[1].textContent).not.toContain("remote-host");
    expect(cards[1].textContent).not.toContain("Update");
  });

  it("shows selected client details with a compact 24-hour update time", () => {
    renderClientList("client-2");

    const selectedCard = container?.querySelector(".client-card.selected");
    expect(selectedCard?.textContent).toContain("remote-host");
    expect(selectedCard?.textContent).not.toContain("Update");
    expect(selectedCard?.textContent).not.toContain("Delete");
    expect(selectedCard?.textContent).not.toContain("Updated");
    expect(selectedCard?.textContent).not.toMatch(/\b(?:AM|PM)\b/);
  });

  it("shows selected remote client update and delete actions on hover", () => {
    const onUpdateClient = vi.fn();
    const onDeleteClient = vi.fn();
    renderClientList("client-2", { onUpdateClient, onDeleteClient });

    expect(container?.querySelector(".client-card-more")).toBeNull();
    expect(container?.querySelector(".client-card-actions")).toBeNull();
    expect(container?.querySelector(".client-actions-menu")).toBeNull();

    act(() => {
      container?.querySelector(".client-card.selected")?.dispatchEvent(new MouseEvent("mouseover", {
        bubbles: true,
        cancelable: true
      }));
    });

    const selectedCard = container?.querySelector(".client-card.selected");
    expect(selectedCard?.textContent).toContain("Update");
    expect(selectedCard?.textContent).toContain("Delete");

    act(() => {
      (selectedCard?.querySelector("[role='menuitem']") as HTMLButtonElement).click();
    });
    expect(onUpdateClient).toHaveBeenCalledWith("client-2");

    act(() => {
      selectedCard?.dispatchEvent(new MouseEvent("mouseover", {
        bubbles: true,
        cancelable: true
      }));
    });

    act(() => {
      (selectedCard?.querySelector(".client-card-delete") as HTMLButtonElement).click();
    });
    expect(onDeleteClient).toHaveBeenCalledWith(expect.objectContaining({ id: "client-2" }));
  });

  it("dismisses the selected remote client action menu after starting an update", () => {
    const onUpdateClient = vi.fn();
    renderClientList("client-2", { onUpdateClient });

    act(() => {
      container?.querySelector(".client-card.selected")?.dispatchEvent(new MouseEvent("mouseover", {
        bubbles: true,
        cancelable: true
      }));
    });

    const selectedCard = container?.querySelector(".client-card.selected");
    expect(selectedCard?.querySelector(".client-actions-menu")).not.toBeNull();

    act(() => {
      (selectedCard?.querySelector("[role='menuitem']") as HTMLButtonElement).click();
    });

    expect(onUpdateClient).toHaveBeenCalledWith("client-2");
    expect(selectedCard?.querySelector(".client-actions-menu")).toBeNull();
  });

  it("does not show a delete action for the local client", () => {
    renderClientList("client-1");

    const selectedCard = container?.querySelector(".client-card.selected");
    expect(selectedCard?.textContent).toContain("Local client");
    expect(selectedCard?.textContent).not.toContain("Delete");
  });

  it("shows the re-register action for the selected remote client and invokes the handler", () => {
    const onReregisterClient = vi.fn();
    renderClientList("client-2", { onReregisterClient });

    act(() => {
      container?.querySelector(".client-card.selected")?.dispatchEvent(new MouseEvent("mouseover", {
        bubbles: true,
        cancelable: true
      }));
    });

    const selectedCard = container?.querySelector(".client-card.selected");
    const reregisterButton = selectedCard?.querySelector(".client-card-reregister") as HTMLButtonElement;
    expect(reregisterButton).toBeTruthy();
    expect(reregisterButton.disabled).toBe(false);

    act(() => {
      reregisterButton.click();
    });
    expect(onReregisterClient).toHaveBeenCalledWith(expect.objectContaining({ id: "client-2" }));
    expect(selectedCard?.querySelector(".client-actions-menu")).toBeNull();
  });

  it("disables the re-register button while a re-register is pending", () => {
    const onReregisterClient = vi.fn();
    renderClientList("client-2", { onReregisterClient, reregisteringClientId: "client-2" });

    act(() => {
      container?.querySelector(".client-card.selected")?.dispatchEvent(new MouseEvent("mouseover", {
        bubbles: true,
        cancelable: true
      }));
    });

    const reregisterButton = container?.querySelector(".client-card-reregister") as HTMLButtonElement;
    expect(reregisterButton.disabled).toBe(true);
  });
});
