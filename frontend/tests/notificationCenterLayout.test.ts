import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS,
  installAutoHideScrollbars
} from "../src/autoHideScrollbars";
import { NotificationBellButton } from "../src/components/NotificationCenter";
import { cssRuleBody as readCssRuleBody, readFrontendCss } from "./cssTestUtils";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;
const stylesCss = readFrontendCss("src/styles.css");

function cssRuleBody(selector: string): string {
  return readCssRuleBody(stylesCss, selector);
}

function cssText(): string {
  return stylesCss;
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  document
    .querySelectorAll(`.${AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS}`)
    .forEach((element) => element.classList.remove(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS));
  root = null;
  container = null;
});

describe("notification center layout", () => {
  it("opens the notification list on the left side with the sidebar bell", () => {
    expect(cssRuleBody(".notification-center-backdrop")).toContain("justify-content: flex-start");
  });

  it("keeps unread notification color on the badge only", () => {
    expect(cssText()).not.toContain(".notification-bell.unread");
    expect(cssRuleBody(".notification-bell-badge")).toMatch(/background:\s*(#dc2626|var\(--skin-danger\))/);
  });

  it("marks the bell unread when unread notifications exist", () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    act(() => {
      root?.render(createElement(NotificationBellButton, { unreadCount: 2, isOpen: false, onClick: () => {} }));
    });

    const bell = container.querySelector<HTMLButtonElement>(".notification-bell");
    expect(bell?.classList.contains("unread")).toBe(true);
    expect(container.querySelector(".notification-bell-badge")?.textContent).toBe("2");
  });

  it("prevents the right detail tabs from showing a vertical scrollbar", () => {
    expect(cssRuleBody(".detail-panel-tabs")).toContain("overflow-y: hidden");
  });

  it("keeps artifact settings create controls above the scrollable artifact list", () => {
    expect(cssRuleBody(".artifact-plugin-sidebar")).toContain("grid-template-rows: auto auto auto minmax(0, 1fr)");
  });

  it("lets the right detail panel collapse out of the desktop grid", () => {
    expect(cssRuleBody(".app-shell.detail-panel-collapsed")).toContain("grid-template-columns: 320px minmax(0, 1fr)");
    expect(cssRuleBody(".detail-panel-collapsed .detail-panel")).toContain("display: none");
  });

  it("lets agent record filters wrap inside the right detail panel", () => {
    expect(cssRuleBody(".agent-record-viewer .agent-record-role-toggle")).toContain("flex-wrap: wrap");
    expect(cssRuleBody(".agent-record-body")).toContain("overflow: hidden");
  });

  it("keeps agent preview chat bubbles on the same row as avatars", () => {
    expect(cssRuleBody(".agent-chat-message-content")).toContain("grid-row: 1");
    expect(cssRuleBody(".agent-chat-avatar")).toContain("grid-row: 1");
    expect(cssRuleBody(".project-todo-agent-record-message-content")).toContain("grid-row: 1");
    expect(cssRuleBody(".project-todo-agent-record-avatar")).toContain("grid-row: 1");
  });

  it("lets expanded single agent preview messages scroll inside the viewport", () => {
    expect(cssRuleBody(".agent-chat-message-fullscreen")).toContain("align-items: stretch");
    expect(cssRuleBody(".agent-chat-message-fullscreen .agent-chat-message-content")).toContain("height: 100%");
    expect(cssRuleBody(".agent-chat-message-fullscreen .agent-chat-message-content")).toContain("overflow: hidden");
    expect(cssRuleBody(".agent-chat-message-fullscreen .agent-event-markdown")).toContain("overflow: auto");
  });

  it("keeps agent preview message text on the compact shared font scale", () => {
    expect(cssRuleBody(".agent-chat-message-body .agent-event-markdown")).toContain("font-size: 12px");
    expect(cssRuleBody(".agent-chat-message-body .agent-event-markdown")).toContain("line-height: 1.45");
    expect(cssRuleBody(".agent-chat-message-body .agent-event-json")).toContain("font-size: 12px");
    expect(cssRuleBody(".agent-chat-message-body .agent-event-json")).toContain("line-height: 1.45");
    expect(cssRuleBody(".project-todo-agent-record-message-content p")).toContain("font-size: 12px");
    expect(cssRuleBody(".project-todo-agent-record-message-content p")).toContain("line-height: 1.45");
  });

  it("keeps document markdown third-level headings larger than body text", () => {
    expect(cssRuleBody(".markdown-preview > .agent-event-markdown")).toContain(
      "--agent-event-markdown-h3-font-size: 1.1em"
    );
    expect(cssRuleBody(".agent-event-markdown h3")).toContain(
      "font-size: var(--agent-event-markdown-h3-font-size)"
    );
  });

  it("keeps todo agent previews from collapsing inside kanban card grids", () => {
    expect(cssRuleBody(".project-todo-agent-record")).toContain("grid-column: 1 / -1");
    expect(cssRuleBody(".project-todo-agent-record-list")).toContain("width: 100%");
    expect(cssRuleBody(".project-todo-agent-record-list")).toContain("justify-items: stretch");
    expect(cssRuleBody(".project-todo-agent-record-list article")).toContain("width: 100%");
    expect(cssRuleBody(".project-todo-agent-record-list article")).toContain("justify-self: stretch");
    expect(cssRuleBody(".project-todo-agent-record-list article.project-todo-agent-record-item-agent")).toContain("minmax(0, 1fr) 30px");
    expect(cssRuleBody(".project-todo-agent-record-message-content")).toContain("width: 100%");
    expect(cssRuleBody(".agent-chat-events")).toContain("width: 100%");
    expect(cssRuleBody(".agent-chat-message")).toContain("width: 100%");
    expect(cssRuleBody(".agent-chat-message")).toContain("max-width: 92%");
    expect(cssRuleBody(".agent-chat-message-content")).toContain("width: 100%");
    expect(cssRuleBody(".agent-event-markdown")).toContain("width: 100%");
  });

  it("keeps shared scrollbars hidden until scrolling is active", () => {
    expect(cssRuleBody(":where(body, body *)")).toContain("scrollbar-color: transparent transparent");
    expect(cssRuleBody(`.${AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS}`)).toContain(
      "scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track)"
    );
    expect(cssRuleBody(":where(body, body *)::-webkit-scrollbar-thumb")).toContain("background: transparent");
    expect(cssRuleBody(`.${AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS}::-webkit-scrollbar-thumb`)).toContain(
      "background: var(--scrollbar-thumb)"
    );
  });

  it("marks only the scrolled element active briefly after captured scroll events", () => {
    vi.useFakeTimers();
    const scroller = document.createElement("div");
    const idleScroller = document.createElement("div");
    document.body.appendChild(scroller);
    document.body.appendChild(idleScroller);
    const uninstall = installAutoHideScrollbars({ idleMs: 100 });

    try {
      expect(document.body.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(false);
      expect(scroller.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(false);
      expect(idleScroller.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(false);

      scroller.dispatchEvent(new Event("scroll"));

      expect(document.body.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(false);
      expect(scroller.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(true);
      expect(idleScroller.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(false);

      vi.advanceTimersByTime(99);
      expect(scroller.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(true);

      vi.advanceTimersByTime(1);
      expect(scroller.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(false);
    } finally {
      uninstall();
      scroller.remove();
      idleScroller.remove();
      vi.useRealTimers();
    }

    expect(document.body.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(false);
  });

  it("moves the visible scrollbar marker to the latest scrolled element", () => {
    vi.useFakeTimers();
    const firstScroller = document.createElement("div");
    const secondScroller = document.createElement("div");
    document.body.append(firstScroller, secondScroller);
    const uninstall = installAutoHideScrollbars({ idleMs: 100 });

    try {
      firstScroller.dispatchEvent(new Event("scroll"));
      expect(firstScroller.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(true);
      expect(secondScroller.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(false);

      secondScroller.dispatchEvent(new Event("scroll"));
      expect(firstScroller.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(false);
      expect(secondScroller.classList.contains(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS)).toBe(true);
    } finally {
      uninstall();
      firstScroller.remove();
      secondScroller.remove();
      vi.useRealTimers();
    }
  });
});
