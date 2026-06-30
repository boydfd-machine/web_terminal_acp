from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from alembic import op
import sqlalchemy as sa

revision: str = "20260607_0053"
down_revision: str | None = "20260606_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SEEDED_TYPE_IDS = (
    "quick-fix",
    "ui-change",
    "debug",
    "small-feature",
    "large-feature",
    "solution-research",
    "performance-optimization",
    "review",
    "product-design",
    "user-review",
)


def upgrade() -> None:
    table = _project_todo_types_table()
    existing_ids = set(
        op.get_bind()
        .execute(
            sa.select(table.c.id).where(
                table.c.scope == "system",
                table.c.id.in_(SEEDED_TYPE_IDS),
            )
        )
        .scalars()
    )
    rows = [row for row in _seed_rows() if row["id"] not in existing_ids]
    if rows:
        op.bulk_insert(table, rows)


def downgrade() -> None:
    table = _project_todo_types_table()
    op.execute(
        table.delete().where(
            table.c.scope == "system",
            table.c.id.in_(SEEDED_TYPE_IDS),
        )
    )


def _project_todo_types_table() -> sa.Table:
    return sa.table(
        "project_todo_types",
        sa.column("record_id", sa.Uuid()),
        sa.column("id", sa.String(length=64)),
        sa.column("scope", sa.String(length=16)),
        sa.column("name", sa.String(length=255)),
        sa.column("description", sa.Text()),
        sa.column("agent", sa.String(length=64)),
        sa.column("agent_profile_id", sa.String(length=128)),
        sa.column("artifact_kinds_json", sa.JSON()),
        sa.column("dispatch_template", sa.Text()),
    )


def _seed_rows() -> list[dict[str, object]]:
    return [
        _row(
            "00000000-0000-0000-0000-000000000101",
            "quick-fix",
            "快速修复",
            "Small, low-risk defect fix with tight validation and no unrelated refactor.",
            "builtin/developer",
            ["qa_release_readiness"],
            """You are assigned a quick-fix project todo.
Project path: {{ project_path }}
Todo: {{ title }}

Context:
{{ description }}

Make the smallest coherent fix. Confirm the failing behavior or risk first, avoid unrelated refactors, run focused validation, and report changed files plus validation.""",
        ),
        _row(
            "00000000-0000-0000-0000-000000000102",
            "ui-change",
            "UI变化",
            "Visible UI behavior or layout change that needs design-system fit and visual evidence.",
            "builtin/developer",
            ["qa_ux_review"],
            """You are assigned a UI-change project todo.
Project path: {{ project_path }}
Todo: {{ title }}

Context:
{{ description }}

Match the existing UI conventions and design system. Verify the changed flow on relevant desktop and mobile states, check accessibility basics, and report changed files plus validation evidence.""",
        ),
        _row(
            "00000000-0000-0000-0000-000000000103",
            "debug",
            "debug",
            "Root-cause debugging task that should reproduce, isolate, fix, and regress-test the issue.",
            "builtin/debug-expert",
            ["agent_trace_graph", "qa_regression_suite"],
            """You are assigned a debugging project todo.
Project path: {{ project_path }}
Todo: {{ title }}

Context:
{{ description }}

Use root-cause debugging. Reproduce or explain why reproduction is impossible, isolate the cause with evidence, add or update a regression test where practical, fix the cause rather than symptoms, and report changed files plus validation.""",
        ),
        _row(
            "00000000-0000-0000-0000-000000000104",
            "small-feature",
            "小需求",
            "Scoped feature or behavior addition that fits existing architecture.",
            "builtin/developer",
            ["qa_regression_suite"],
            """You are assigned a small-feature project todo.
Project path: {{ project_path }}
Todo: {{ title }}

Context:
{{ description }}

Implement the smallest complete behavior that satisfies the card. Follow existing module boundaries, add focused tests around changed behavior, and report changed files plus validation.""",
        ),
        _row(
            "00000000-0000-0000-0000-000000000105",
            "large-feature",
            "大需求",
            "Larger feature that needs architecture fit, staged work, risk coverage, and release readiness evidence.",
            "builtin/developer",
            ["agent_trace_graph", "qa_risk_coverage_plan", "qa_release_readiness"],
            """You are assigned a large-feature project todo.
Project path: {{ project_path }}
Todo: {{ title }}

Context:
{{ description }}

First inspect the architecture and identify the smallest staged implementation path. Keep changes inside the owning contexts, preserve compatibility, add tests for the main contracts, document residual risks, and report changed files plus validation.""",
        ),
        _row(
            "00000000-0000-0000-0000-000000000106",
            "solution-research",
            "方案调研",
            "Research and compare implementation or product options before committing to a direction.",
            "builtin/deep-researcher",
            ["deep_research_report"],
            """You are assigned a solution-research project todo.
Project path: {{ project_path }}
Todo: {{ title }}

Context:
{{ description }}

Research the decision, compare credible options, state assumptions and tradeoffs, cite sources when web research is used, and recommend a concrete next step. Do not implement code unless the card explicitly asks for implementation.""",
        ),
        _row(
            "00000000-0000-0000-0000-000000000107",
            "performance-optimization",
            "性能优化",
            "Performance task that needs baseline metrics, budget, optimization, and regression evidence.",
            "builtin/debug-expert",
            ["qa_performance_review"],
            """You are assigned a performance-optimization project todo.
Project path: {{ project_path }}
Todo: {{ title }}

Context:
{{ description }}

Establish the baseline first, identify the bottleneck with evidence, optimize without weakening correctness, compare before/after metrics against an explicit budget, and report changed files plus validation.""",
        ),
        _row(
            "00000000-0000-0000-0000-000000000108",
            "review",
            "review",
            "Independent engineering review of completed work, risks, and validation evidence.",
            "builtin/pr-review",
            ["qa_risk_coverage_plan", "qa_release_readiness"],
            """You are assigned an independent review project todo.
Project path: {{ project_path }}
Todo: {{ title }}

Context:
{{ description }}

Review the relevant diff, behavior, architecture fit, tests, and residual risks. Lead with findings ordered by severity, include file or evidence references where possible, and state whether the work is approved, needs changes, or needs human review.""",
        ),
        _row(
            "00000000-0000-0000-0000-000000000109",
            "product-design",
            "产品设计",
            "Product design task that turns user goals and constraints into concrete requirement cards.",
            "builtin/page-review",
            ["page_review_cards", "project:user_journey"],
            """You are assigned a product-design project todo.
Project path: {{ project_path }}
Todo: {{ title }}

Context:
{{ description }}

Clarify the target user, job, constraints, current journey, desired outcome, edge cases, and acceptance criteria. Produce actionable requirement cards and avoid implementation detail unless it changes product decisions.""",
        ),
        _row(
            "00000000-0000-0000-0000-000000000110",
            "user-review",
            "用户review",
            "User-facing review that converts observed page or flow issues into actionable cards.",
            "builtin/page-review",
            ["page_review_cards", "qa_ux_review", "project:user_journey"],
            """You are assigned a user-review project todo.
Project path: {{ project_path }}
Todo: {{ title }}

Context:
{{ description }}

Inspect the requested user-facing page or flow from the user's perspective. Capture evidence, usability issues, severity, proposed fixes, acceptance criteria, and retest notes. Produce project-todo-ready review cards.""",
        ),
    ]


def _row(
    record_id: str,
    type_id: str,
    name: str,
    description: str,
    profile_id: str | None,
    artifact_kinds: list[str],
    dispatch_template: str,
) -> dict[str, object]:
    return {
        "record_id": UUID(record_id),
        "id": type_id,
        "scope": "system",
        "name": name,
        "description": description,
        "agent": "codex",
        "agent_profile_id": profile_id,
        "artifact_kinds_json": artifact_kinds,
        "dispatch_template": dispatch_template,
    }
