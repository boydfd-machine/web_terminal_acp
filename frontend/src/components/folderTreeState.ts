import type { SwitcherNode } from "../terminalGrouping";

export type CollapsedState = {
  storageKey: string;
  keys: Set<string>;
};

export function collapsedStorageKey(clientId: string | null, groupingMode: string): string {
  return `web-terminal-acp:terminals-tree:collapsed:${clientId ?? "no-client"}:${groupingMode}`;
}

export function readCollapsedKeys(storageKey: string): Set<string> | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const rawValue = window.localStorage.getItem(storageKey);
    if (rawValue === null) {
      return null;
    }

    const parsedValue: unknown = JSON.parse(rawValue);
    if (!Array.isArray(parsedValue)) {
      return null;
    }

    return new Set(parsedValue.filter((value): value is string => typeof value === "string"));
  } catch {
    return null;
  }
}

export function defaultCollapsedKeys(nodes: SwitcherNode[]): Set<string> {
  const keys = new Set<string>();

  const visit = (node: SwitcherNode, depth: number) => {
    if (node.type === "window") {
      return;
    }

    if (depth > 0) {
      keys.add(node.key);
    }

    for (const child of node.children) {
      visit(child, depth + 1);
    }
  };

  for (const node of nodes) {
    visit(node, 0);
  }

  return keys;
}

export function loadCollapsedKeys(storageKey: string, displayTree: SwitcherNode[]): Set<string> {
  return readCollapsedKeys(storageKey) ?? defaultCollapsedKeys(displayTree);
}

export function writeCollapsedKeys(storageKey: string, keys: Set<string>) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(storageKey, JSON.stringify(Array.from(keys)));
  } catch {
    return;
  }
}
