import { ApiError } from "../api";
import type { ProjectFileEntry } from "../types";

export type FileTreeNode = {
  id: string;
  name: string;
  path: string;
  kind: "file" | "directory";
  size: number | null;
  mtime: number | null;
  children?: FileTreeNode[];
};

type ProjectFilesViewProps = {
  clientId: string | null;
  projectPath: string | null;
};

export const ROOT_PATH = ".";
const MARKDOWN_EXTENSIONS = new Set([".md", ".markdown"]);
const HTML_EXTENSIONS = new Set([".html", ".htm", ".xhtml"]);
const IMAGE_EXTENSIONS = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".webp",
  ".bmp",
  ".svg",
  ".ico",
  ".avif"
]);

export function childPath(parentPath: string, name: string): string {
  return parentPath === ROOT_PATH ? name : `${parentPath}/${name}`;
}

export function extensionFor(path: string): string {
  const slash = path.lastIndexOf("/");
  const name = slash === -1 ? path : path.slice(slash + 1);
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLocaleLowerCase();
}

export function isMarkdown(path: string): boolean {
  return MARKDOWN_EXTENSIONS.has(extensionFor(path));
}

export function isHtml(path: string): boolean {
  return HTML_EXTENSIONS.has(extensionFor(path));
}

export function isImage(path: string): boolean {
  return IMAGE_EXTENSIONS.has(extensionFor(path));
}

export function isBinaryPreviewError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 415;
}

export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function entryFromNode(node: FileTreeNode | null): ProjectFileEntry | null {
  if (node === null) {
    return null;
  }
  return {
    name: node.name,
    path: node.path,
    kind: node.kind,
    size: node.size,
    mtime: node.mtime
  };
}

export function formatBytes(value: number | null): string {
  if (value === null) {
    return "";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function toBase64(data: ArrayBuffer): string {
  let binary = "";
  const bytes = new Uint8Array(data);
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    const chunk = bytes.subarray(offset, offset + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

export function mergeDirectoryEntries(
  nodes: FileTreeNode[],
  directoryPath: string,
  entries: ProjectFileEntry[]
): FileTreeNode[] {
  const nextChildren = entries.map((entry) => ({
    id: entry.path,
    name: entry.name,
    path: entry.path,
    kind: entry.kind,
    size: entry.size,
    mtime: entry.mtime,
    children: entry.kind === "directory" ? findNode(nodes, entry.path)?.children ?? [] : undefined
  }));

  if (directoryPath === ROOT_PATH) {
    return nextChildren;
  }

  return nodes.map((node) => {
    if (node.path === directoryPath && node.kind === "directory") {
      return { ...node, children: nextChildren };
    }
    if (node.children === undefined) {
      return node;
    }
    return {
      ...node,
      children: mergeDirectoryEntries(node.children, directoryPath, entries)
    };
  });
}

export function findNode(nodes: FileTreeNode[], path: string): FileTreeNode | null {
  for (const node of nodes) {
    if (node.path === path) {
      return node;
    }
    if (node.children !== undefined) {
      const child = findNode(node.children, path);
      if (child !== null) {
        return child;
      }
    }
  }
  return null;
}
