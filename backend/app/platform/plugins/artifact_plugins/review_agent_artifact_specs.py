from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewAgentArtifactSpec:
    artifact_kind: str
    label: str
    default_title: str
    purpose: str
    presentation: str
    sections: tuple[str, ...]
    item_fields: tuple[str, ...]
    references: tuple[dict[str, str], ...]


COMMON_QA_REFERENCE = {
    "label": "Software testing deliverables",
    "url": "https://www.techtarget.com/searchsoftwarequality/tip/Software-testing-deliverables-From-test-plans-to-status-reports",
    "note": "Use planning, test case, defect, and status deliverables as the base QA workflow.",
}
PLAYWRIGHT_REFERENCE = {
    "label": "Playwright trace viewer",
    "url": "https://playwright.dev/docs/trace-viewer-intro",
    "note": "Keep executable test evidence debuggable with traces, screenshots, and reports.",
}
WCAG_REFERENCE = {
    "label": "WCAG 2.2",
    "url": "https://www.w3.org/TR/WCAG22/",
    "note": "Accessibility findings should map to testable success criteria and conformance levels.",
}
OWASP_WSTG_REFERENCE = {
    "label": "OWASP WSTG",
    "url": "https://owasp.org/www-project-web-security-testing-guide/",
    "note": "Security review should follow structured web application security test areas.",
}
OWASP_API_REFERENCE = {
    "label": "OWASP API Security Top 10",
    "url": "https://owasp.org/API-Security/editions/2023/en/0x11-t10/",
    "note": "API review should cover authorization, authentication, object/property access, and abuse.",
}
WEB_VITALS_REFERENCE = {
    "label": "Core Web Vitals",
    "url": "https://web.dev/articles/vitals",
    "note": "Performance review should track LCP, INP, and CLS against explicit budgets.",
}
UX_REFERENCE = {
    "label": "NN/g usability heuristics",
    "url": "https://www.nngroup.com/articles/ten-usability-heuristics/",
    "note": "UX findings should cite the violated heuristic, severity, and user impact.",
}
COMPAT_REFERENCE = {
    "label": "MDN cross-browser testing",
    "url": "https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Testing/Introduction",
    "note": "Compatibility review should state browser, device, viewport, and feature coverage.",
}
EXPLORATORY_REFERENCE = {
    "label": "Exploratory test charters",
    "url": "https://www.qualitestgroup.com/insights/technical-hub/how-to-write-an-exploratory-test-charter/",
    "note": "Exploratory sessions need a charter, notes, bugs, and follow-up questions.",
}


REVIEW_AGENT_QA_ARTIFACT_SPECS: tuple[ReviewAgentArtifactSpec, ...] = (
    ReviewAgentArtifactSpec(
        artifact_kind="qa_risk_coverage_plan",
        label="QA Risk Coverage Plan",
        default_title="QA risk and coverage plan",
        purpose="Decide what a review agent should test by change risk, user impact, and evidence gaps.",
        presentation="Risk-ranked coverage map with explicit in-scope, out-of-scope, and unknown rows.",
        sections=("Change risk inventory", "Coverage map by test type", "Out of scope and assumptions"),
        item_fields=("id", "area", "risk", "user_impact", "test_type", "priority", "evidence", "owner", "status"),
        references=(COMMON_QA_REFERENCE, WCAG_REFERENCE, OWASP_WSTG_REFERENCE, WEB_VITALS_REFERENCE),
    ),
    ReviewAgentArtifactSpec(
        artifact_kind="qa_regression_suite",
        label="QA Regression Suite",
        default_title="QA regression suite",
        purpose="Turn the review scope into repeatable functional and regression cases.",
        presentation="Scripted test case table grouped by critical journey and automation readiness.",
        sections=("Critical user journeys", "Regression test cases", "Automation backlog"),
        item_fields=(
            "id",
            "scenario",
            "preconditions",
            "steps",
            "expected",
            "data",
            "priority",
            "automation",
            "status",
        ),
        references=(COMMON_QA_REFERENCE, PLAYWRIGHT_REFERENCE),
    ),
    ReviewAgentArtifactSpec(
        artifact_kind="qa_exploratory_sessions",
        label="QA Exploratory Sessions",
        default_title="QA exploratory sessions",
        purpose="Capture open-ended QA work that discovers unknown bugs beyond scripted cases.",
        presentation="Time-boxed charter cards with live notes, bugs, risks, and next probes.",
        sections=("Charters", "Session notes", "Findings and follow-ups"),
        item_fields=(
            "id",
            "charter",
            "timebox",
            "persona",
            "data_setup",
            "observations",
            "bugs",
            "risks",
            "next_probe",
            "evidence",
        ),
        references=(EXPLORATORY_REFERENCE, COMMON_QA_REFERENCE),
    ),
    ReviewAgentArtifactSpec(
        artifact_kind="qa_accessibility_audit",
        label="QA Accessibility Audit",
        default_title="QA accessibility audit",
        purpose="Record accessibility barriers with enough WCAG context for remediation and retest.",
        presentation="WCAG issue register plus keyboard, focus, and assistive-technology check sections.",
        sections=("WCAG issues", "Keyboard and focus checks", "Assistive technology notes"),
        item_fields=("id", "wcag", "level", "page_or_component", "issue", "impact", "evidence", "fix", "status"),
        references=(WCAG_REFERENCE,),
    ),
    ReviewAgentArtifactSpec(
        artifact_kind="qa_ux_review",
        label="QA UX Review",
        default_title="QA UX heuristic review",
        purpose="Show usability risks that make a working feature hard, confusing, or error-prone.",
        presentation="Heuristic findings board with severity, affected flow, evidence, and recommendation.",
        sections=("Heuristic findings", "Flow friction", "Copy and error recovery"),
        item_fields=(
            "id",
            "heuristic",
            "flow",
            "issue",
            "severity",
            "frequency",
            "impact",
            "recommendation",
            "evidence",
        ),
        references=(UX_REFERENCE,),
    ),
    ReviewAgentArtifactSpec(
        artifact_kind="qa_performance_review",
        label="QA Performance Review",
        default_title="QA performance review",
        purpose="Make performance regressions visible with user-centric metrics, budgets, and suspects.",
        presentation="Metric budget dashboard for routes, interactions, causes, and recommended actions.",
        sections=("Core Web Vitals", "Interaction and rendering risks", "Budget actions"),
        item_fields=("id", "route", "metric", "target", "actual", "status", "evidence", "suspected_cause", "action"),
        references=(WEB_VITALS_REFERENCE, PLAYWRIGHT_REFERENCE),
    ),
    ReviewAgentArtifactSpec(
        artifact_kind="qa_security_api_review",
        label="QA Security and API Review",
        default_title="QA security and API review",
        purpose="Track web security, API contract, authorization, and abuse-case checks in one risk register.",
        presentation="Security/API risk register grouped by surface, OWASP category, evidence, and fix.",
        sections=("Web security checks", "API contract and auth checks", "Abuse cases"),
        item_fields=(
            "id",
            "surface",
            "owasp_category",
            "check",
            "expected_control",
            "evidence",
            "risk",
            "fix",
            "status",
        ),
        references=(OWASP_WSTG_REFERENCE, OWASP_API_REFERENCE),
    ),
    ReviewAgentArtifactSpec(
        artifact_kind="qa_compatibility_matrix",
        label="QA Compatibility Matrix",
        default_title="QA compatibility matrix",
        purpose="Show where the reviewed behavior was checked across browsers, devices, and viewports.",
        presentation="Browser/device/viewport matrix with pass, fail, blocked, and not-run cells.",
        sections=("Browser and device matrix", "Responsive breakpoints", "Known compatibility risks"),
        item_fields=(
            "id",
            "browser",
            "version",
            "os_device",
            "viewport",
            "feature_area",
            "result",
            "evidence",
            "issue",
            "owner",
        ),
        references=(COMPAT_REFERENCE, PLAYWRIGHT_REFERENCE),
    ),
    ReviewAgentArtifactSpec(
        artifact_kind="qa_release_readiness",
        label="QA Release Readiness",
        default_title="QA release readiness",
        purpose="Summarize whether the change is ready to ship and what evidence supports the decision.",
        presentation="Go/no-go gate dashboard with blockers, residual risks, owners, and sign-off state.",
        sections=("Release gates", "Blocking defects", "Residual risks and sign-off"),
        item_fields=(
            "id",
            "gate",
            "required_evidence",
            "current_status",
            "blocker",
            "owner",
            "next_action",
            "decision",
        ),
        references=(
            COMMON_QA_REFERENCE,
            WCAG_REFERENCE,
            OWASP_WSTG_REFERENCE,
            WEB_VITALS_REFERENCE,
            COMPAT_REFERENCE,
        ),
    ),
)
