import type { Plugin } from "vite";

const PAGE_ANNOTATION_ENTRY = "/src/pageAnnotationEntry.ts";

export function pageAnnotationPlugin(): Plugin {
  let enabled = false;
  return {
    name: "web-terminal-page-annotation",
    configResolved(config) {
      enabled = config.command === "serve" || process.env.VITE_ENABLE_PAGE_ANNOTATION === "true";
    },
    transformIndexHtml: {
      order: "pre",
      handler(html) {
        if (!enabled) {
          return html;
        }
        return html.replace(
          /<\/body>/i,
          `    <script type="module" src="${PAGE_ANNOTATION_ENTRY}"></script>\n  </body>`
        );
      }
    }
  };
}
