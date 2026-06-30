export function isDebugAnnotationEnabled(): boolean {
  if (typeof window !== "undefined" && window.__WEB_TERMINAL_PAGE_ANNOTATION_ENABLED__ === true) {
    return true;
  }
  return import.meta.env.DEV || import.meta.env.VITE_ENABLE_PAGE_ANNOTATION === "true";
}
