import type { SystemSkillDetail } from "../types";

export type SkillTreeNode = {
  id: string;
  name: string;
  path: string;
  kind: "directory" | "file";
  size: number | null;
  children?: SkillTreeNode[];
};

export type McpToolParameter = {
  name: string;
  type: string;
  required: boolean;
  description: string | null;
};

function basename(path: string): string {
  const slash = path.lastIndexOf("/");
  return slash === -1 ? path : path.slice(slash + 1);
}

function parentPath(path: string): string | null {
  const slash = path.lastIndexOf("/");
  return slash === -1 ? null : path.slice(0, slash);
}

export function buildSkillTree(entries: SystemSkillDetail["entries"]): SkillTreeNode[] {
  const nodes = new Map<string, SkillTreeNode>();
  const roots: SkillTreeNode[] = [];
  for (const entry of entries) {
    nodes.set(entry.path, {
      id: entry.path,
      name: basename(entry.path),
      path: entry.path,
      kind: entry.kind,
      size: entry.size,
      children: entry.kind === "directory" ? [] : undefined
    });
  }
  for (const node of nodes.values()) {
    const parent = parentPath(node.path);
    if (parent === null) {
      roots.push(node);
      continue;
    }
    const parentNode = nodes.get(parent);
    if (parentNode?.kind === "directory") {
      parentNode.children?.push(node);
    } else {
      roots.push(node);
    }
  }
  const sortNodes = (items: SkillTreeNode[]) => {
    items.sort((left, right) => {
      if (left.kind !== right.kind) {
        return left.kind === "directory" ? -1 : 1;
      }
      return left.name.localeCompare(right.name);
    });
    items.forEach((item) => {
      if (item.children !== undefined) {
        sortNodes(item.children);
      }
    });
  };
  sortNodes(roots);
  return roots;
}

function primitiveTypeLabel(value: unknown): string {
  if (Array.isArray(value)) {
    return value.filter((item) => typeof item === "string").join(" | ") || "unknown";
  }
  return typeof value === "string" && value.trim() !== "" ? value : "unknown";
}

function schemaTypeLabel(definition: Record<string, unknown>): string {
  const composite = definition.anyOf ?? definition.oneOf;
  if (Array.isArray(composite)) {
    const labels = composite
      .filter((item): item is Record<string, unknown> => (
        typeof item === "object" && item !== null && !Array.isArray(item)
      ))
      .map(schemaTypeLabel)
      .filter((label) => label !== "unknown");
    if (labels.length > 0) {
      return Array.from(new Set(labels)).join(" | ");
    }
  }

  if (Array.isArray(definition.enum)) {
    const values = definition.enum
      .filter((item): item is string | number | boolean => (
        typeof item === "string" || typeof item === "number" || typeof item === "boolean"
      ))
      .map((item) => String(item));
    if (values.length > 0) {
      return `enum: ${values.join(" | ")}`;
    }
  }

  const baseType = primitiveTypeLabel(definition.type);
  if (baseType === "array") {
    const items = definition.items;
    if (typeof items === "object" && items !== null && !Array.isArray(items)) {
      return `array<${schemaTypeLabel(items as Record<string, unknown>)}>`;
    }
  }
  if (baseType === "object") {
    const properties = definition.properties;
    if (typeof properties === "object" && properties !== null && !Array.isArray(properties)) {
      const keys = Object.keys(properties);
      if (keys.length > 0) {
        return `object { ${keys.slice(0, 4).join(", ")}${keys.length > 4 ? ", ..." : ""} }`;
      }
    }
  }
  return baseType;
}

export function mcpToolParameters(schema: Record<string, unknown>): McpToolParameter[] {
  const properties = schema.properties;
  if (typeof properties !== "object" || properties === null || Array.isArray(properties)) {
    return [];
  }
  const required = Array.isArray(schema.required)
    ? new Set(schema.required.filter((item): item is string => typeof item === "string"))
    : new Set<string>();
  return Object.entries(properties)
    .filter((entry): entry is [string, Record<string, unknown>] => (
      typeof entry[1] === "object" && entry[1] !== null && !Array.isArray(entry[1])
    ))
    .map(([name, definition]) => ({
      name,
      type: schemaTypeLabel(definition),
      required: required.has(name),
      description: typeof definition.description === "string" ? definition.description : null
    }));
}
