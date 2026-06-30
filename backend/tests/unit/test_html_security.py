from app.platform.html_security import ARTIFACT_HTML_CSP, artifact_html_headers


def test_artifact_html_csp_sandboxes_scripted_reports_without_same_origin():
    assert "sandbox allow-scripts" in ARTIFACT_HTML_CSP
    assert "allow-same-origin" not in ARTIFACT_HTML_CSP
    assert "object-src 'none'" in ARTIFACT_HTML_CSP
    assert "frame-src 'none'" in ARTIFACT_HTML_CSP
    assert "connect-src 'none'" in ARTIFACT_HTML_CSP


def test_artifact_html_headers_disable_referrers_and_content_sniffing():
    headers = artifact_html_headers()

    assert headers["Content-Security-Policy"] == ARTIFACT_HTML_CSP
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["X-Content-Type-Options"] == "nosniff"
