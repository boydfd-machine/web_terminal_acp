import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import type { ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../src/api";
import { ProjectFilePreviewPanel, ProjectFileTreePanel } from "../src/components/ProjectFilesView";
import {
  PROJECT_FILE_OPEN_EVENT,
  type ProjectFileOpenRequest
} from "../src/projectFileLinks";
import type { ProjectFileEntry, ProjectFileList } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../src/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api")>();
  return {
    ...actual,
    fetchProjectFiles: vi.fn(),
    fetchProjectFileContent: vi.fn(),
    fetchProjectFileBlob: vi.fn(),
    saveProjectFileContent: vi.fn(),
    downloadProjectFile: vi.fn(() => Promise.resolve())
  };
});

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function fileEntry(overrides: Partial<ProjectFileEntry>): ProjectFileEntry {
  return {
    name: "README",
    path: "README",
    kind: "file",
    size: 11,
    mtime: null,
    ...overrides
  };
}

function fileList(path: string, entries: ProjectFileEntry[]): ProjectFileList {
  return {
    project_path: "/workspace/project",
    path,
    entries
  };
}

async function renderWithQueryClient(element: ReactElement): Promise<void> {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      },
      mutations: {
        retry: false
      }
    }
  });

  await act(async () => {
    root?.render(
      <QueryClientProvider client={queryClient as QueryClient}>
        {element}
      </QueryClientProvider>
    );
  });
}

async function rerenderWithQueryClient(element: ReactElement): Promise<void> {
  await act(async () => {
    root?.render(
      <QueryClientProvider client={queryClient as QueryClient}>
        {element}
      </QueryClientProvider>
    );
  });
}

async function flushQueries(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function waitForAssertion(assertion: () => void): Promise<void> {
  let lastError: unknown = null;
  for (let index = 0; index < 20; index += 1) {
    try {
      assertion();
      return;
    } catch (error) {
      lastError = error;
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }
  }
  throw lastError;
}

async function clickButtonWithAriaLabel(label: string): Promise<void> {
  const button = container?.querySelector(`button[aria-label="${label}"]`);
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`button not found: ${label}`);
  }
  await act(async () => {
    button.click();
  });
}

async function clickFileNodeWithText(text: string): Promise<void> {
  const node = Array.from(container?.querySelectorAll(".project-file-node") ?? []).find(
    (candidate) => candidate.textContent?.includes(text)
  );
  if (!(node instanceof HTMLElement)) {
    throw new Error(`file node not found: ${text}`);
  }
  await act(async () => {
    node.click();
  });
}

function setTextareaValue(textarea: HTMLTextAreaElement, value: string): void {
  const descriptor = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value");
  act(() => {
    descriptor?.set?.call(textarea, value);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

let createObjectURL: ReturnType<typeof vi.fn> | null = null;
let revokeObjectURL: ReturnType<typeof vi.fn> | null = null;

function stubObjectUrl(): void {
  createObjectURL = vi.fn(() => "blob:project-file");
  revokeObjectURL = vi.fn();
  vi.stubGlobal("URL", Object.assign(URL, {
    createObjectURL: createObjectURL as unknown as typeof URL.createObjectURL,
    revokeObjectURL: revokeObjectURL as unknown as typeof URL.revokeObjectURL
  }));
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  queryClient?.clear();
  queryClient = null;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  createObjectURL = null;
  revokeObjectURL = null;
});

describe("ProjectFilesView panels", () => {
  it("loads a directory when it is selected", async () => {
    const api = await import("../src/api");
    vi.mocked(api.fetchProjectFiles).mockImplementation((_clientId, _projectPath, path = ".") => {
      if (path === ".") {
        return Promise.resolve(fileList(".", [
          fileEntry({ name: "docs", path: "docs", kind: "directory", size: null })
        ]));
      }
      return Promise.resolve(fileList("docs", [
        fileEntry({ name: "README", path: "docs/README", kind: "file", size: 4 })
      ]));
    });
    const onSelectEntry = vi.fn();

    await renderWithQueryClient(
      <ProjectFileTreePanel
        clientId="client-1"
        projectPath="/workspace/project"
        selectedPath={null}
        onSelectEntry={onSelectEntry}
      />
    );
    await waitForAssertion(() => {
      expect(container?.textContent).toContain("docs");
    });

    await clickFileNodeWithText("docs");
    await waitForAssertion(() => {
      expect(api.fetchProjectFiles).toHaveBeenCalledWith("client-1", "/workspace/project", "docs", undefined);
    });
    await waitForAssertion(() => {
      expect(container?.textContent).toContain("README");
    });

    expect(onSelectEntry).toHaveBeenCalledWith(expect.objectContaining({
      path: "docs",
      kind: "directory"
    }));
  });

  it("keeps the loaded file tree when the parent rerenders with the same project context", async () => {
    const api = await import("../src/api");
    vi.mocked(api.fetchProjectFiles).mockResolvedValue(fileList(".", [
      fileEntry({ name: "docs", path: "docs", kind: "directory", size: null })
    ]));

    await renderWithQueryClient(
      <ProjectFileTreePanel
        clientId="client-1"
        projectPath="/workspace/project"
        selectedPath={null}
        onSelectEntry={vi.fn()}
      />
    );
    await waitForAssertion(() => {
      expect(container?.textContent).toContain("docs");
    });

    await rerenderWithQueryClient(
      <ProjectFileTreePanel
        clientId="client-1"
        projectPath="/workspace/project"
        selectedPath={null}
        onSelectEntry={vi.fn()}
      />
    );
    await flushQueries();

    expect(container?.textContent).toContain("docs");
  });

  it("keeps an externally selected file while loading its parent directory", async () => {
    const api = await import("../src/api");
    vi.mocked(api.fetchProjectFiles).mockImplementation((_clientId, _projectPath, path = ".") => {
      if (path === ".") {
        return Promise.resolve(fileList(".", [
          fileEntry({ name: "docs", path: "docs", kind: "directory", size: null })
        ]));
      }
      return Promise.resolve(fileList("docs", [
        fileEntry({ name: "README.md", path: "docs/README.md", kind: "file", size: 7 })
      ]));
    });
    const onSelectEntry = vi.fn();

    await renderWithQueryClient(
      <ProjectFileTreePanel
        clientId="client-1"
        projectPath="/workspace/project"
        selectedPath="docs/README.md"
        onSelectEntry={onSelectEntry}
      />
    );

    await waitForAssertion(() => {
      expect(api.fetchProjectFiles).toHaveBeenCalledWith("client-1", "/workspace/project", "docs", undefined);
    });
    await waitForAssertion(() => {
      expect(container?.textContent).toContain("README.md");
    });

    await waitForAssertion(() => {
      const selectedFileNode = container?.querySelector(".project-file-node.file.selected");
      expect(selectedFileNode?.textContent).toContain("README.md");
    });
    expect(onSelectEntry).not.toHaveBeenCalledWith(null);
  });

  it("previews and saves text files without relying on extensions", async () => {
    const api = await import("../src/api");
    vi.mocked(api.fetchProjectFileContent).mockResolvedValue({
      project_path: "/workspace/project",
      path: "README",
      content: "hello",
      encoding: "utf-8",
      truncated: false,
      size: 5
    });
    vi.mocked(api.saveProjectFileContent).mockResolvedValue({
      project_path: "/workspace/project",
      path: "README",
      size: 12
    });

    await renderWithQueryClient(
      <ProjectFilePreviewPanel
        clientId="client-1"
        projectPath="/workspace/project"
        entry={fileEntry({ name: "README", path: "README", size: 5 })}
        mode="edit"
        onModeChange={() => {}}
      />
    );
    await waitForAssertion(() => {
      expect(container?.textContent).toContain("hello");
    });
    const textarea = container?.querySelector("textarea");
    expect(textarea).toBeInstanceOf(HTMLTextAreaElement);
    setTextareaValue(textarea as HTMLTextAreaElement, "hello\nworld");
    await clickButtonWithAriaLabel("Save README");
    await waitForAssertion(() => {
      expect(api.saveProjectFileContent).toHaveBeenCalled();
    });

    expect(api.saveProjectFileContent).toHaveBeenCalledWith(
      "client-1",
      "/workspace/project",
      "README",
      "hello\nworld",
      true,
      undefined
    );
  });

  it("renders markdown files with shared markdown behavior and file links", async () => {
    const api = await import("../src/api");
    const openRequests: ProjectFileOpenRequest[] = [];
    const handleOpenRequest = (event: Event) => {
      openRequests.push((event as CustomEvent<ProjectFileOpenRequest>).detail);
    };
    window.addEventListener(PROJECT_FILE_OPEN_EVENT, handleOpenRequest);
    vi.mocked(api.fetchProjectFileContent).mockResolvedValue({
      project_path: "/workspace/project",
      path: "docs/README.md",
      content: [
        "# Docs",
        "",
        "- [x] shared GFM",
        "",
        "[Guide](./guide.md#L3)"
      ].join("\n"),
      encoding: "utf-8",
      truncated: false,
      size: 48
    });

    await renderWithQueryClient(
      <ProjectFilePreviewPanel
        clientId="client-1"
        projectPath="/workspace/project"
        entry={fileEntry({ name: "README.md", path: "docs/README.md", size: 48 })}
        targetLine={1}
        mode="preview"
        onModeChange={() => {}}
      />
    );

    await waitForAssertion(() => {
      expect(container?.querySelector(".markdown-preview .agent-event-markdown h1")?.textContent).toBe("Docs");
    });
    expect(container?.querySelectorAll(".markdown-preview .agent-event-markdown input[type=\"checkbox\"]")).toHaveLength(1);
    expect(container?.querySelector(".text-file-preview")).toBeNull();

    const link = container?.querySelector<HTMLAnchorElement>(".markdown-preview .agent-event-markdown a");
    expect(link).toBeInstanceOf(HTMLAnchorElement);
    expect(link?.getAttribute("href")).toBe(
      "/clients/client-1/files?project_path=%2Fworkspace%2Fproject&file_path=docs%2Fguide.md&line=3"
    );
    expect(link?.getAttribute("target")).toBeNull();

    await act(async () => {
      link?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    window.removeEventListener(PROJECT_FILE_OPEN_EVENT, handleOpenRequest);

    expect(openRequests).toEqual([
      {
        clientId: "client-1",
        windowId: null,
        projectPath: "/workspace/project",
        browseRoot: null,
        path: "docs/guide.md",
        line: 3
      }
    ]);
  });

  it("renders HTML files inside a sandboxed iframe preview", async () => {
    const api = await import("../src/api");
    vi.mocked(api.fetchProjectFileContent).mockResolvedValue({
      project_path: "/workspace/project",
      path: "site/index.html",
      content: [
        "<!DOCTYPE html>",
        "<html>",
        "  <head><title>Demo</title></head>",
        "  <body>",
        "    <h1>Hello preview</h1>",
        "    <script>window.__demo = true;</script>",
        "  </body>",
        "</html>"
      ].join("\n"),
      encoding: "utf-8",
      truncated: false,
      size: 96
    });

    await renderWithQueryClient(
      <ProjectFilePreviewPanel
        clientId="client-1"
        projectPath="/workspace/project"
        entry={fileEntry({ name: "index.html", path: "site/index.html", size: 96 })}
        mode="preview"
        onModeChange={() => {}}
      />
    );

    await waitForAssertion(() => {
      expect(container?.querySelector(".html-preview iframe")).toBeInstanceOf(HTMLIFrameElement);
    });

    const iframe = container?.querySelector<HTMLIFrameElement>(".html-preview iframe");
    expect(iframe?.getAttribute("sandbox")).toBe("allow-scripts");
    expect(iframe?.getAttribute("referrerpolicy")).toBe("no-referrer");
    expect(iframe?.getAttribute("title")).toBe("site/index.html");

    const srcDoc = iframe?.getAttribute("srcdoc") ?? "";
    expect(srcDoc).toContain("Content-Security-Policy");
    expect(srcDoc).toContain("<h1>Hello preview</h1>");
    expect(srcDoc).toContain("window.__demo = true;");
    expect(srcDoc).not.toContain("<iframe");
    // HTML file preview must allow external CDN resources so mermaid diagrams and
    // JS-driven tab controls work; artifact previews stay locked down separately.
    expect(srcDoc).toContain("script-src 'unsafe-inline' https:");
    expect(srcDoc).toContain("style-src 'unsafe-inline' https:");
    expect(srcDoc).toContain("img-src data: blob: https:");
    expect(srcDoc).toContain("connect-src https:");
    // Forms must remain blocked even with the relaxed network policy.
    expect(srcDoc).toContain("form-action 'none'");

    expect(container?.querySelector(".markdown-preview")).toBeNull();
    expect(container?.querySelector(".text-file-preview")).toBeNull();
  });

  it("highlights the requested line in source previews", async () => {
    const api = await import("../src/api");
    const scrollIntoView = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollIntoView;
    vi.mocked(api.fetchProjectFileContent).mockResolvedValue({
      project_path: "/workspace/project",
      path: "src/App.tsx",
      content: "first\nsecond\nthird",
      encoding: "utf-8",
      truncated: false,
      size: 18
    });

    await renderWithQueryClient(
      <ProjectFilePreviewPanel
        clientId="client-1"
        projectPath="/workspace/project"
        entry={fileEntry({ name: "App.tsx", path: "src/App.tsx", size: 18 })}
        targetLine={2}
        mode="preview"
        onModeChange={() => {}}
      />
    );
    await waitForAssertion(() => {
      expect(container?.querySelector(".text-file-preview-line-highlight")?.textContent).toBe("second");
    });

    const highlightedLine = container?.querySelector(".text-file-preview-line-highlight");
    expect(highlightedLine?.getAttribute("data-line-number")).toBe("2");
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "center" });
  });

  it("does not preview binary files", async () => {
    const api = await import("../src/api");
    vi.mocked(api.fetchProjectFileContent).mockRejectedValue(
      new ApiError(415, "Unsupported Media Type", "binary file preview is unsupported")
    );

    await renderWithQueryClient(
      <ProjectFilePreviewPanel
        clientId="client-1"
        projectPath="/workspace/project"
        entry={fileEntry({ name: "archive.bin", path: "archive.bin", size: 128 })}
        mode="preview"
        onModeChange={() => {}}
      />
    );
    await waitForAssertion(() => {
      expect(container?.textContent).toContain("Binary file preview is unavailable.");
    });
    expect(container?.querySelector("textarea")).toBeNull();
  });

  it("previews image files via blob fetch and skips the text content request", async () => {
    stubObjectUrl();
    const api = await import("../src/api");
    const blob = new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: "image/png" });
    vi.mocked(api.fetchProjectFileBlob).mockResolvedValue(blob);

    await renderWithQueryClient(
      <ProjectFilePreviewPanel
        clientId="client-1"
        projectPath="/workspace/project"
        entry={fileEntry({ name: "logo.png", path: "assets/logo.png", size: 4 })}
        mode="preview"
        onModeChange={() => {}}
      />
    );

    await waitForAssertion(() => {
      expect(container?.querySelector(".image-preview img")).toBeInstanceOf(HTMLImageElement);
    });

    expect(api.fetchProjectFileBlob).toHaveBeenCalledWith(
      "client-1",
      "/workspace/project",
      "assets/logo.png",
      undefined
    );
    expect(api.fetchProjectFileContent).not.toHaveBeenCalled();

    const img = container?.querySelector<HTMLImageElement>(".image-preview img");
    expect(img?.getAttribute("alt")).toBe("assets/logo.png");
    expect(img?.getAttribute("src")).toBe("blob:project-file");
    expect(createObjectURL).toHaveBeenCalledWith(blob);

    expect(container?.querySelector(".text-file-preview")).toBeNull();
    expect(container?.textContent ?? "").not.toContain("Binary file preview is unavailable.");
  });

  it("renders an image download button with an accessible label", async () => {
    stubObjectUrl();
    const api = await import("../src/api");
    const blob = new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: "image/png" });
    vi.mocked(api.fetchProjectFileBlob).mockResolvedValue(blob);
    vi.mocked(api.downloadProjectFile).mockResolvedValue();

    await renderWithQueryClient(
      <ProjectFilePreviewPanel
        clientId="client-1"
        projectPath="/workspace/project"
        entry={fileEntry({ name: "logo.png", path: "assets/logo.png", size: 4 })}
        mode="preview"
        onModeChange={() => {}}
      />
    );

    await waitForAssertion(() => {
      expect(container?.querySelector(".image-preview img")).toBeInstanceOf(HTMLImageElement);
    });

    const downloadButton = container?.querySelector<HTMLButtonElement>(
      "button.image-preview-download"
    );
    expect(downloadButton).toBeInstanceOf(HTMLButtonElement);
    expect(downloadButton?.getAttribute("aria-label")).toBe("Download logo.png");

    await act(async () => {
      downloadButton?.click();
    });

    expect(api.downloadProjectFile).toHaveBeenCalledWith(
      "client-1",
      "/workspace/project",
      "assets/logo.png",
      undefined
    );
  });

  it("surfaces image load failures without falling back to binary messaging", async () => {
    const api = await import("../src/api");
    vi.mocked(api.fetchProjectFileBlob).mockRejectedValue(
      new ApiError(413, "Request Entity Too Large", "file too large")
    );

    await renderWithQueryClient(
      <ProjectFilePreviewPanel
        clientId="client-1"
        projectPath="/workspace/project"
        entry={fileEntry({ name: "huge.png", path: "huge.png", size: 60_000_000 })}
        mode="preview"
        onModeChange={() => {}}
      />
    );

    await waitForAssertion(() => {
      expect(container?.textContent ?? "").toContain("413 file too large");
    });
    expect(container?.querySelector(".image-preview img")).toBeNull();
    expect(container?.textContent ?? "").not.toContain("Binary file preview is unavailable.");
  });
});
