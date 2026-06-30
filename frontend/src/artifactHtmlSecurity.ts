import DOMPurify from "dompurify";

export const ARTIFACT_HTML_CSP = [
  "default-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "object-src 'none'",
  "frame-src 'none'",
  "connect-src 'none'",
  "img-src data: blob:",
  "font-src data:",
  "style-src 'unsafe-inline'",
  "script-src 'unsafe-inline'"
].join("; ");

// HTML files in the user's project (e.g. skill renderers, mermaid reports) routinely
// load libraries and assets from CDNs. The iframe is still sandboxed to an opaque
// origin without allow-forms/allow-same-origin, so external scripts cannot reach the
// parent app; we only relax network egress for https: resources.
export const HTML_FILE_CSP = [
  "default-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "object-src 'none'",
  "frame-src 'none'",
  "img-src data: blob: https:",
  "font-src data: https:",
  "style-src 'unsafe-inline' https:",
  "script-src 'unsafe-inline' https:",
  "connect-src https:",
  "worker-src https: blob:"
].join("; ");

export const ARTIFACT_IFRAME_SANDBOX = "allow-scripts";

const FORBIDDEN_ARTIFACT_TAGS = [
  "applet",
  "base",
  "embed",
  "form",
  "iframe",
  "object"
];

const FORBIDDEN_ARTIFACT_ATTRS = [
  "formaction",
  "srcdoc"
];

export function sanitizeArtifactHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    // Existing artifact reports use inline scripts inside a sandboxed, opaque-origin iframe.
    ADD_TAGS: ["script"],
    FORBID_ATTR: FORBIDDEN_ARTIFACT_ATTRS,
    FORBID_TAGS: FORBIDDEN_ARTIFACT_TAGS,
    WHOLE_DOCUMENT: true
  });
}
