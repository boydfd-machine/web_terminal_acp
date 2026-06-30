import { act, useRef, useState, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useOverlayFocus } from "../src/components/useOverlayFocus";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;

function TestOverlay({
  label,
  onEscape,
  children
}: {
  label: string;
  onEscape?: () => void;
  children?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  useOverlayFocus({ isOpen: true, ref, onEscape });

  return (
    <div ref={ref} role="dialog" aria-label={label}>
      {children}
    </div>
  );
}

function NestedOverlayHarness({
  onOuterEscape,
  onInnerEscape,
  innerHasEscapeHandler = true
}: {
  onOuterEscape: () => void;
  onInnerEscape: () => void;
  innerHasEscapeHandler?: boolean;
}) {
  const [innerOpen, setInnerOpen] = useState(false);
  const [outerRenderCount, setOuterRenderCount] = useState(0);

  return (
    <TestOverlay label={`outer-${outerRenderCount}`} onEscape={() => onOuterEscape()}>
      <button type="button" onClick={() => setOuterRenderCount((count) => count + 1)}>
        rerender outer
      </button>
      <button type="button" onClick={() => setInnerOpen(true)}>
        open inner
      </button>
      {innerOpen && (
        <TestOverlay
          label="inner"
          onEscape={innerHasEscapeHandler ? onInnerEscape : undefined}
        />
      )}
    </TestOverlay>
  );
}

function renderHarness(onOuterEscape = vi.fn(), onInnerEscape = vi.fn()) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);

  act(() => {
    root?.render(<NestedOverlayHarness onOuterEscape={onOuterEscape} onInnerEscape={onInnerEscape} />);
  });

  return { onOuterEscape, onInnerEscape };
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

describe("useOverlayFocus", () => {
  it("keeps the inner overlay as the Escape target when an outer overlay rerenders", () => {
    const { onOuterEscape, onInnerEscape } = renderHarness();
    const buttons = Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? []);
    const rerenderOuter = buttons.find((button) => button.textContent === "rerender outer");
    const openInner = buttons.find((button) => button.textContent === "open inner");
    expect(rerenderOuter).toBeInstanceOf(HTMLButtonElement);
    expect(openInner).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      openInner?.click();
    });

    act(() => {
      rerenderOuter?.click();
    });

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Escape"
      }));
    });

    expect(onInnerEscape).toHaveBeenCalledTimes(1);
    expect(onOuterEscape).not.toHaveBeenCalled();
  });

  it("lets an open overlay without an Escape handler block lower Escape handlers", () => {
    const onOuterEscape = vi.fn();
    const onInnerEscape = vi.fn();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    act(() => {
      root?.render(
        <NestedOverlayHarness
          onOuterEscape={onOuterEscape}
          onInnerEscape={onInnerEscape}
          innerHasEscapeHandler={false}
        />
      );
    });
    const openInner = Array.from(container.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent === "open inner");
    expect(openInner).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      openInner?.click();
    });

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Escape"
      }));
    });

    expect(onInnerEscape).not.toHaveBeenCalled();
    expect(onOuterEscape).not.toHaveBeenCalled();
  });
});
