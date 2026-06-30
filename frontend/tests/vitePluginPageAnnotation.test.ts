import { describe, expect, it } from "vitest";

import { pageAnnotationPlugin } from "../vite-plugin-page-annotation";

function resolvePlugin(command: "serve" | "build", envEnabled?: string) {
  const previous = process.env.VITE_ENABLE_PAGE_ANNOTATION;
  if (envEnabled === undefined) {
    delete process.env.VITE_ENABLE_PAGE_ANNOTATION;
  } else {
    process.env.VITE_ENABLE_PAGE_ANNOTATION = envEnabled;
  }
  const plugin = pageAnnotationPlugin();
  plugin.configResolved?.({
    command,
    mode: command === "serve" ? "development" : "production"
  } as Parameters<NonNullable<typeof plugin.configResolved>>[0]);
  process.env.VITE_ENABLE_PAGE_ANNOTATION = previous;
  return plugin;
}

describe("page annotation Vite plugin", () => {
  it("injects the runtime during dev serve", () => {
    const plugin = resolvePlugin("serve");
    const result = transformHtml(plugin, "<html><body></body></html>");

    expect(result).toContain('<script type="module" src="/src/pageAnnotationEntry.ts"></script>');
  });

  it("does not inject production builds unless explicitly enabled", () => {
    const plugin = resolvePlugin("build");

    expect(transformHtml(plugin, "<html><body></body></html>")).toBe("<html><body></body></html>");
  });

  it("allows explicit env opt-in for non-dev builds", () => {
    const plugin = resolvePlugin("build", "true");

    expect(transformHtml(plugin, "<html><body></body></html>")).toContain("/src/pageAnnotationEntry.ts");
  });
});

function transformHtml(plugin: ReturnType<typeof pageAnnotationPlugin>, html: string): string {
  const transform = plugin.transformIndexHtml;
  if (typeof transform === "function") {
    return transform(html, {} as Parameters<typeof transform>[1]) as string;
  }
  return transform?.handler(html, {} as Parameters<typeof transform.handler>[1]) as string;
}
