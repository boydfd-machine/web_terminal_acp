from __future__ import annotations

# Artifact reports keep script-driven interactions, but run without same-origin privileges.
ARTIFACT_HTML_CSP = (
    "sandbox allow-scripts; "
    "default-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "object-src 'none'; "
    "frame-src 'none'; "
    "connect-src 'none'; "
    "img-src data: blob:; "
    "font-src data:; "
    "style-src 'unsafe-inline'; "
    "script-src 'unsafe-inline'"
)


def artifact_html_headers() -> dict[str, str]:
    return {
        "Content-Security-Policy": ARTIFACT_HTML_CSP,
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    }
