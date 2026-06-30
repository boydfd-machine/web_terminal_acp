import { act, useEffect } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useTerminalCreateActions } from "../src/hooks/useTerminalCreateActions";
import type { TerminalCreateContext } from "../src/components/TerminalCreateModal";
import type { SwitcherGroupNode } from "../src/terminalGrouping";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;

function renderActions(options: {
  selectedClientId?: string | null;
  selectedClientOffline?: boolean;
  terminalCreateBusy?: boolean;
  setTerminalCreateContext?: (context: TerminalCreateContext | null) => void;
  setTerminalSwitcherOpen?: (open: boolean) => void;
}) {
  const createMutation = { mutate: vi.fn() };
  const setProjectTerminalPickerOpen = vi.fn();
  const setTerminalCreateContext = options.setTerminalCreateContext ?? vi.fn();
  const setTerminalSwitcherOpen = options.setTerminalSwitcherOpen ?? vi.fn();
  const captures: {
    handleConfigureTerminalAtGroup?: ReturnType<typeof useTerminalCreateActions>["handleConfigureTerminalAtGroup"];
  } = {};

  function Harness() {
    const actions = useTerminalCreateActions({
      createMutation,
      selectedClientId: options.selectedClientId ?? "client-1",
      selectedClientOffline: options.selectedClientOffline ?? false,
      terminalCreateBusy: options.terminalCreateBusy ?? false,
      terminalCreateContext: null,
      setProjectTerminalPickerOpen,
      setTerminalCreateContext,
      setTerminalSwitcherOpen,
    });

    useEffect(() => {
      captures.handleConfigureTerminalAtGroup = actions.handleConfigureTerminalAtGroup;
    }, [actions.handleConfigureTerminalAtGroup]);

    return null;
  }

  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => {
    root?.render(<Harness />);
  });

  return {
    captures,
    createMutation,
    setProjectTerminalPickerOpen,
    setTerminalCreateContext,
    setTerminalSwitcherOpen,
  };
}

const projectGroup: SwitcherGroupNode = {
  type: "group",
  key: "project:/workspace/app",
  label: "App",
  projectPath: "/workspace/app",
  count: 1,
  children: [],
};

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  vi.restoreAllMocks();
});

describe("useTerminalCreateActions", () => {
  it("opens group terminal configuration in required-agent config mode", () => {
    const setTerminalCreateContext = vi.fn();
    const { captures, setTerminalSwitcherOpen } = renderActions({ setTerminalCreateContext });

    act(() => {
      captures.handleConfigureTerminalAtGroup?.(projectGroup);
    });

    expect(setTerminalCreateContext).toHaveBeenCalledWith(expect.objectContaining({
      cwd: "/workspace/app",
      description: "/workspace/app",
      requireAgent: true,
      showConfigInitially: true,
    }));
    expect(setTerminalSwitcherOpen).not.toHaveBeenCalledWith(false);

    const context = setTerminalCreateContext.mock.calls[0]?.[0] as TerminalCreateContext;
    act(() => {
      context.afterCreate?.();
    });
    expect(setTerminalSwitcherOpen).toHaveBeenCalledWith(false);
  });
});
