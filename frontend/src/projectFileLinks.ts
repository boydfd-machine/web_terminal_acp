import { terminalRouteSelectionFromPath } from "./appState";
import { projectPathForWindow } from "./terminalTree";
import type { GitWorktreeActivity } from "./types";

export const PROJECT_FILE_OPEN_EVENT = "web-terminal-open-project-file";

export type ProjectFileLinkContext = {
  clientId: string | null;
  windowId: string | null;
  projectPath: string | null;
  browseRoot?: string | null;
  cwd?: string | null;
  gitWorktree?: GitWorktreeActivity | null;
};

export type ProjectFileOpenRequest = {
  clientId: string;
  windowId: string | null;
  projectPath: string;
  browseRoot: string | null;
  path: string;
  line: number | null;
};

export type ProjectFilesRouteRequest = {
  clientId: string;
  windowId: string | null;
  projectPath: string;
  browseRoot: string | null;
};

type WindowPathSource = {
  cwd?: string | null;
  runtime_tags?: string[] | null;
  git_worktree?: GitWorktreeActivity | null;
};

export function projectFileLinkContextForWindow({
  clientId,
  windowId,
  projectPath,
  browseRoot,
  window,
}: {
  clientId: string | null;
  windowId: string | null;
  projectPath: string | null;
  browseRoot?: string | null;
  window?: WindowPathSource | null;
}): ProjectFileLinkContext {
  const gitWorktree = window?.git_worktree ?? null;
  return {
    clientId,
    windowId,
    projectPath: gitWorktree?.main_repo_root ?? projectPath ?? projectPathForWindow(window),
    browseRoot: gitWorktree?.worktree_root ?? browseRoot ?? null,
    cwd: window?.cwd ?? null,
    gitWorktree,
  };
}

export function projectFileRoutePath(request: ProjectFileOpenRequest): string {
  const routePath = projectFilesRoutePath(request);
  const params = new URLSearchParams(routePath.slice(routePath.indexOf("?") + 1));
  params.set("file_path", request.path);
  if (request.line !== null) {
    params.set("line", String(request.line));
  }
  return `${routePath.slice(0, routePath.indexOf("?"))}?${params.toString()}`;
}

export function projectFilesRoutePath(request: ProjectFilesRouteRequest): string {
  const routePath = `/clients/${encodeURIComponent(request.clientId)}/files`;
  const params = new URLSearchParams({
    project_path: request.projectPath,
  });
  if (request.windowId !== null) {
    params.set("window_id", request.windowId);
  }
  if (request.browseRoot !== null) {
    params.set("browse_root", request.browseRoot);
  }
  return `${routePath}?${params.toString()}`;
}

export function projectFileRouteRequestFromUrl(value: string, base?: string): ProjectFileOpenRequest | null {
  const routeRequest = projectFilesRouteRequestFromUrl(value, base);
  if (routeRequest === null) {
    return null;
  }
  const fallbackBase = typeof window === "undefined" ? "http://localhost/" : window.location.href;
  let url: URL;
  try {
    url = new URL(value, base ?? fallbackBase);
  } catch {
    return null;
  }
  const filePath = url.searchParams.get("file_path");
  if (!filePath) {
    return null;
  }
  return {
    ...routeRequest,
    path: filePath,
    line: lineFromString(url.searchParams.get("line")),
  };
}

export function projectFilesRouteRequestFromUrl(value: string, base?: string): ProjectFilesRouteRequest | null {
  const fallbackBase = typeof window === "undefined" ? "http://localhost/" : window.location.href;
  let url: URL;
  try {
    url = new URL(value, base ?? fallbackBase);
  } catch {
    return null;
  }
  if (typeof window !== "undefined" && url.origin !== window.location.origin) {
    return null;
  }
  const routeSelection = projectFileRouteSelectionFromUrl(url);
  if (routeSelection === null) {
    return null;
  }
  const projectPath = url.searchParams.get("project_path");
  if (!projectPath) {
    return null;
  }
  return {
    clientId: routeSelection.clientId,
    windowId: routeSelection.windowId,
    projectPath,
    browseRoot: url.searchParams.get("browse_root"),
  };
}

export function readProjectFileRouteRequest(): ProjectFileOpenRequest | null {
  if (typeof window === "undefined") {
    return null;
  }
  return projectFileRouteRequestFromUrl(`${window.location.pathname}${window.location.search}${window.location.hash}`);
}

export function readProjectFilesRouteRequest(): ProjectFilesRouteRequest | null {
  if (typeof window === "undefined") {
    return null;
  }
  return projectFilesRouteRequestFromUrl(`${window.location.pathname}${window.location.search}${window.location.hash}`);
}

export function writeProjectFilesRoute(request: ProjectFilesRouteRequest, mode: "push" | "replace"): void {
  if (typeof window === "undefined") {
    return;
  }
  const nextPath = projectFilesRoutePath(request);
  if (`${window.location.pathname}${window.location.search}${window.location.hash}` === nextPath) {
    return;
  }
  window.history[mode === "push" ? "pushState" : "replaceState"](
    { clientId: request.clientId, windowId: request.windowId, view: "files" },
    "",
    nextPath
  );
}

export function writeProjectFileRoute(request: ProjectFileOpenRequest, mode: "push" | "replace"): void {
  if (typeof window === "undefined") {
    return;
  }
  const nextPath = projectFileRoutePath(request);
  if (`${window.location.pathname}${window.location.search}${window.location.hash}` === nextPath) {
    return;
  }
  window.history[mode === "push" ? "pushState" : "replaceState"](
    { clientId: request.clientId, windowId: request.windowId, view: "files", filePath: request.path },
    "",
    nextPath
  );
}

function projectFileRouteSelectionFromUrl(url: URL): { clientId: string; windowId: string | null } | null {
  const filesMatch = url.pathname.match(/^\/clients\/([^/]+)\/files\/?$/);
  if (filesMatch) {
    return {
      clientId: decodeURIComponent(filesMatch[1]),
      windowId: url.searchParams.get("window_id"),
    };
  }

  if (url.searchParams.get("view") !== "files") {
    return null;
  }
  const legacySelection = terminalRouteSelectionFromPath(url.pathname);
  return legacySelection.clientId === null
    ? null
    : { clientId: legacySelection.clientId, windowId: legacySelection.windowId };
}

export function dispatchProjectFileOpenRequest(request: ProjectFileOpenRequest): void {
  window.dispatchEvent(new CustomEvent<ProjectFileOpenRequest>(PROJECT_FILE_OPEN_EVENT, { detail: request }));
}

export function isProjectFileOpenEvent(event: Event): event is CustomEvent<ProjectFileOpenRequest> {
  return event instanceof CustomEvent && event.type === PROJECT_FILE_OPEN_EVENT && isProjectFileOpenRequest(event.detail);
}

export function projectFileLinkHref(rawUrl: string, context?: ProjectFileLinkContext | null): string | null {
  const request = projectFileOpenRequestFromMarkdownUrl(rawUrl, context);
  return request === null ? null : projectFileRoutePath(request);
}

export function projectFileOpenRequestFromMarkdownUrl(
  rawUrl: string,
  context?: ProjectFileLinkContext | null
): ProjectFileOpenRequest | null {
  const existingRouteRequest = projectFileRouteRequestFromUrl(rawUrl);
  if (existingRouteRequest !== null) {
    return existingRouteRequest;
  }
  if (!context || context.clientId === null) {
    return null;
  }
  const parsed = parseMarkdownFilePath(rawUrl);
  if (parsed === null) {
    return null;
  }
  const projectRoot = trimTrailingSlash(context.projectPath);
  const browseRoot = trimTrailingSlash(context.browseRoot ?? null);
  const effectiveRoot = browseRoot ?? projectRoot;
  if (projectRoot === null || effectiveRoot === null) {
    return null;
  }

  const absoluteTarget = parsed.path.startsWith("/")
    ? normalizeAbsolutePath(parsed.path)
    : normalizeRelativePath(`${baseDirectoryForContext(context, effectiveRoot)}/${parsed.path}`);
  if (absoluteTarget === null) {
    return null;
  }

  const browseRelative = browseRoot === null ? null : relativePathWithinRoot(absoluteTarget, browseRoot);
  if (browseRelative !== null) {
    return requestForNormalizedPath(context, projectRoot, browseRoot, browseRelative, parsed.line);
  }
  const projectRelative = relativePathWithinRoot(absoluteTarget, projectRoot);
  if (projectRelative !== null) {
    return requestForNormalizedPath(context, projectRoot, null, projectRelative, parsed.line);
  }
  return null;
}

export function fileEntryForProjectPath(path: string): {
  name: string;
  path: string;
  kind: "file";
  size: null;
  mtime: null;
} {
  const normalized = normalizeProjectFilePath(path) ?? path;
  const parts = normalized.split("/").filter(Boolean);
  return {
    name: parts.length > 0 ? parts[parts.length - 1] : normalized,
    path: normalized,
    kind: "file",
    size: null,
    mtime: null,
  };
}

function requestForNormalizedPath(
  context: ProjectFileLinkContext,
  projectPath: string,
  browseRoot: string | null,
  path: string,
  line: number | null
): ProjectFileOpenRequest | null {
  const normalizedPath = normalizeProjectFilePath(path);
  if (normalizedPath === null) {
    return null;
  }
  return {
    clientId: context.clientId as string,
    windowId: context.windowId,
    projectPath,
    browseRoot,
    path: normalizedPath,
    line,
  };
}

function parseMarkdownFilePath(rawUrl: string): { path: string; line: number | null } | null {
  const trimmed = rawUrl.trim();
  if (
    trimmed.length === 0
    || trimmed.startsWith("#")
    || trimmed.startsWith("//")
    || /[\u0000-\u001f]/u.test(trimmed)
  ) {
    return null;
  }

  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed) && !trimmed.startsWith("file:")) {
    return null;
  }
  if (/^[a-z][a-z0-9+.-]*:/i.test(trimmed) && !trimmed.startsWith("file:") && lineFromPathSuffix(trimmed) === null) {
    return null;
  }

  let pathname: string;
  let line: number | null = null;
  try {
    if (trimmed.startsWith("file:")) {
      const url = new URL(trimmed);
      pathname = decodePath(url.pathname);
      line = lineFromSearchParams(url.searchParams) ?? lineFromHash(url.hash);
    } else {
      const hashIndex = trimmed.indexOf("#");
      const pathWithMaybeQuery = hashIndex === -1 ? trimmed : trimmed.slice(0, hashIndex);
      const queryIndex = pathWithMaybeQuery.indexOf("?");
      const pathWithMaybeLine = queryIndex === -1 ? pathWithMaybeQuery : pathWithMaybeQuery.slice(0, queryIndex);
      pathname = decodePath(pathWithMaybeLine);
      line = (
        queryIndex === -1 ? null : lineFromQueryString(pathWithMaybeQuery.slice(queryIndex + 1))
      ) ?? (
        hashIndex === -1 ? null : lineFromHash(trimmed.slice(hashIndex))
      );
    }
  } catch {
    return null;
  }

  if (pathname.length === 0) {
    return null;
  }
  const suffixLine = lineSuffixFromPath(pathname);
  if (suffixLine !== null) {
    pathname = suffixLine.path;
    line = line ?? suffixLine.line;
  }
  return { path: pathname, line };
}

function baseDirectoryForContext(context: ProjectFileLinkContext, fallbackRoot: string): string {
  const cwd = trimTrailingSlash(context.cwd ?? null);
  if (cwd === null) {
    return fallbackRoot;
  }
  const browseRoot = trimTrailingSlash(context.browseRoot ?? null);
  if (browseRoot !== null && relativePathWithinRoot(cwd, browseRoot) !== null) {
    return cwd;
  }
  const projectRoot = trimTrailingSlash(context.projectPath);
  if (projectRoot !== null && relativePathWithinRoot(cwd, projectRoot) !== null) {
    return cwd;
  }
  return fallbackRoot;
}

function normalizeProjectFilePath(path: string): string | null {
  if (path.startsWith("/")) {
    return null;
  }
  const normalized = normalizeRelativeSegments(path.split("/"));
  if (normalized === null || normalized.length === 0) {
    return null;
  }
  return normalized.join("/");
}

function normalizeRelativePath(path: string): string | null {
  if (!path.startsWith("/")) {
    return null;
  }
  return normalizeAbsolutePath(path);
}

function normalizeAbsolutePath(path: string): string | null {
  const normalized = normalizeRelativeSegments(path.split("/"));
  if (normalized === null) {
    return null;
  }
  return `/${normalized.join("/")}`;
}

function normalizeRelativeSegments(segments: string[]): string[] | null {
  const normalized: string[] = [];
  for (const segment of segments) {
    if (segment === "" || segment === ".") {
      continue;
    }
    if (segment === "..") {
      if (normalized.length === 0) {
        return null;
      }
      normalized.pop();
      continue;
    }
    normalized.push(segment);
  }
  return normalized;
}

function relativePathWithinRoot(path: string, root: string): string | null {
  if (path === root) {
    return "";
  }
  const prefix = `${root}/`;
  return path.startsWith(prefix) ? path.slice(prefix.length) : null;
}

function trimTrailingSlash(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  return value.length > 1 ? value.replace(/\/+$/u, "") : value;
}

function decodePath(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function lineFromString(value: string | null): number | null {
  if (value === null || !/^[1-9][0-9]*$/u.test(value)) {
    return null;
  }
  const line = Number(value);
  return Number.isSafeInteger(line) ? line : null;
}

function lineFromHash(hash: string): number | null {
  const match = /^#L?([1-9][0-9]*)/u.exec(hash);
  return lineFromString(match?.[1] ?? null);
}

function lineFromQueryString(query: string): number | null {
  try {
    return lineFromSearchParams(new URLSearchParams(query));
  } catch {
    return null;
  }
}

function lineFromSearchParams(params: URLSearchParams): number | null {
  return lineFromString(
    params.get("line")
      ?? params.get("lineno")
      ?? params.get("lineNumber")
      ?? params.get("L")
  );
}

function lineSuffixFromPath(path: string): { path: string; line: number } | null {
  const match = /:([1-9][0-9]*)(?::[1-9][0-9]*)?$/u.exec(path);
  const line = lineFromString(match?.[1] ?? null);
  if (match === null || line === null) {
    return null;
  }
  return {
    path: path.slice(0, match.index),
    line,
  };
}

function lineFromPathSuffix(path: string): number | null {
  return lineSuffixFromPath(path)?.line ?? null;
}

function isProjectFileOpenRequest(value: unknown): value is ProjectFileOpenRequest {
  if (!value || typeof value !== "object") {
    return false;
  }
  const request = value as ProjectFileOpenRequest;
  return typeof request.clientId === "string"
    && (typeof request.windowId === "string" || request.windowId === null)
    && typeof request.projectPath === "string"
    && (typeof request.browseRoot === "string" || request.browseRoot === null)
    && typeof request.path === "string"
    && (typeof request.line === "number" || request.line === null);
}
