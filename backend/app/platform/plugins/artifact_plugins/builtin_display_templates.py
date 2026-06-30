from __future__ import annotations


def pitfalls_html_template() -> str:
    return """<!doctype html>
<html lang="{{ content.locale | default("en") }}">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ content.title | default(default_title) }}</title>
  <style>
    *{box-sizing:border-box}body{margin:0;background:#f7f9fb;color:#17202a;font:14px/1.55 system-ui,sans-serif}
    main{max-width:1240px;margin:0 auto;padding:28px}h1{margin:0;font-size:26px;line-height:1.2}h2{margin:0 0 10px;font-size:16px}
    .hero{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:18px}.muted{color:#64748b}
    .count{border:1px solid #cbd5e1;border-radius:999px;background:#fff;padding:6px 12px;white-space:nowrap}
    .lanes{display:grid;grid-template-columns:repeat(4,minmax(220px,1fr));gap:12px}.lane{border:1px solid #d8e0ea;border-radius:8px;background:#fff;padding:12px}
    .lane.install_software{border-top:4px solid #047857}.lane.update_memory{border-top:4px solid #2563eb}.lane.add_skill{border-top:4px solid #7c3aed}.lane.add_tool{border-top:4px solid #c2410c}
    .card{display:grid;gap:9px;border:1px solid #e2e8f0;border-radius:8px;background:#fbfdff;padding:12px;margin-top:10px}.card strong{font-size:15px}
    .badges{display:flex;gap:6px;flex-wrap:wrap}.badge{border-radius:999px;background:#eef4f8;padding:2px 8px;font-size:11px;font-weight:800;text-transform:uppercase}.high{background:#fee2e2;color:#991b1b}.medium{background:#fef3c7;color:#92400e}.low{background:#dcfce7;color:#166534}
    dl{display:grid;gap:7px;margin:0}dt{color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase}dd{margin:0}.solution{border-left:3px solid #cbd5e1;padding-left:10px}.steps{margin:4px 0 0;padding-left:18px}.kv{display:grid;gap:5px}.kv-row{display:grid;gap:2px}.kv-key{color:#475569;font-weight:800}
    @media(max-width:980px){.lanes{grid-template-columns:repeat(2,minmax(220px,1fr))}}@media(max-width:640px){main{padding:18px}.hero{display:grid}.lanes{grid-template-columns:1fr}}
  </style>
</head>
<body><main>
{% macro render_solution(value) -%}
  {% if value is mapping %}
    <div class="kv">{% for key,item in value.items() %}<div class="kv-row"><span class="kv-key">{{ key | replace("_", " ") | title }}</span><span>{{ render_solution(item) }}</span></div>{% endfor %}</div>
  {% elif value is sequence and value is not string %}
    <ol class="steps">{% for item in value %}<li>{{ render_solution(item) }}</li>{% endfor %}</ol>
  {% else %}{{ value | default("", true) }}{% endif %}
{%- endmacro %}
<section class="hero"><div><h1>{{ content.title | default(default_title) }}</h1><div class="muted">Reusable token-saving pitfalls grouped by the fix that prevents recurrence.</div></div><div class="count">{{ (content.pitfalls | default([])) | length }} pitfalls</div></section>
<section class="lanes">
{% for solution_type,label in [("install_software","Install Software"),("update_memory","Update Memory"),("add_skill","Add / Update Skill"),("add_tool","Add Tool")] %}
  <div class="lane {{ solution_type }}"><h2>{{ label }}</h2>
  {% for item in content.pitfalls | default([]) if item.solution_type == solution_type %}
    <article class="card"><div class="badges"><span class="badge {{ item.priority | default("medium") }}">{{ item.priority | default("medium") }}</span></div><strong>{{ item.pitfall | default("Pitfall") }}</strong><dl><dt>Wasted action</dt><dd>{{ item.wasted_action | default("") }}</dd><dt>Why it wastes tokens</dt><dd>{{ item.why_it_wastes_tokens | default("") }}</dd><dt>Better action</dt><dd>{{ item.better_action | default("") }}</dd><dt>Solution</dt><dd class="solution">{{ render_solution(item.solution | default("")) }}</dd></dl></article>
  {% else %}<p class="muted">No items in this lane.</p>{% endfor %}
  </div>
{% endfor %}
</section>
</main></body></html>"""


def page_review_html_template() -> str:
    return """<!doctype html>
<html lang="{{ content.locale | default("en") }}">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ content.title | default(default_title) }}</title>
  <style>
    *{box-sizing:border-box}body{margin:0;background:#f6f8fb;color:#18202a;font:14px/1.5 system-ui,sans-serif}
    main{max-width:1240px;margin:0 auto;padding:28px}h1{margin:0;font-size:26px;line-height:1.2}h2{margin:0 0 10px;font-size:16px}h3{margin:0;font-size:15px}.muted{color:#64748b}
    .summary{border:1px solid #d8e0ea;border-radius:8px;background:#fff;padding:14px;margin:16px 0}.summary-grid{display:grid;grid-template-columns:1fr 2fr;gap:12px}
    .board{display:grid;grid-template-columns:repeat(4,minmax(230px,1fr));gap:12px}.lane{border:1px solid #d8e0ea;border-radius:8px;background:#fff;padding:12px}.lane.P0{border-top:4px solid #b91c1c}.lane.P1{border-top:4px solid #0f766e}.lane.P2{border-top:4px solid #2563eb}.lane.P3{border-top:4px solid #64748b}
    .card{display:grid;gap:10px;border:1px solid #e2e8f0;border-radius:8px;background:#fbfdff;padding:12px;margin-top:10px}.meta{display:flex;gap:6px;flex-wrap:wrap}.pill{border:1px solid #d8e0ea;border-radius:999px;background:#eef4f8;padding:2px 8px;font-size:11px;font-weight:800;text-transform:uppercase}
    .critical,.high{color:#991b1b}.medium{color:#92400e}.low{color:#166534}dl{display:grid;gap:7px;margin:0}dt{color:#64748b;font-size:12px;font-weight:800;text-transform:uppercase}dd{margin:0}ul{margin:4px 0 0;padding-left:18px}
    @media(max-width:1080px){.board{grid-template-columns:repeat(2,minmax(230px,1fr))}.summary-grid{grid-template-columns:1fr}}@media(max-width:640px){main{padding:18px}.board{grid-template-columns:1fr}}
  </style>
</head>
<body><main>
<header><h1>{{ content.title | default(default_title) }}</h1><div class="muted">{{ content.page | default("Current page or flow") }} / {{ (content.cards | default([])) | length }} cards</div></header>
<section class="summary"><div class="summary-grid"><div><strong>Scope</strong><div class="muted">{{ content.review_scope | default("Scope not specified") }}</div></div><div><strong>Summary</strong><div>{{ content.executive_summary | default("No summary provided.") }}</div></div></div></section>
<section class="board">
{% for priority in ["P0","P1","P2","P3"] %}
  <div class="lane {{ priority }}"><h2>{{ priority }}</h2>
  {% for card in content.cards | default([]) if card.priority | default("P2") == priority %}
    <article class="card"><div class="meta"><span class="pill">{{ card.type | default("enhancement") }}</span><span class="pill {{ card.severity | default("medium") }}">{{ card.severity | default("medium") }}</span><span class="pill">{{ card.id | default("card") }}</span></div><h3>{{ card.title | default("Requirement card") }}</h3><dl><dt>User value</dt><dd>{{ card.user_value | default("-") }}</dd><dt>Problem</dt><dd>{{ card.problem | default("-") }}</dd><dt>Proposal</dt><dd>{{ card.proposal | default("-") }}</dd><dt>Evidence</dt><dd><ul>{% for item in card.evidence | default([]) %}<li><strong>{{ item.label | default("Evidence") }}:</strong> {{ item.detail | default(item.note | default("")) }}</li>{% else %}<li>No evidence recorded.</li>{% endfor %}</ul></dd><dt>Acceptance criteria</dt><dd><ul>{% for item in card.acceptance_criteria | default([]) %}<li>{{ item }}</li>{% else %}<li>No criteria recorded.</li>{% endfor %}</ul></dd><dt>Retest</dt><dd><ul>{% for item in card.test_notes | default([]) %}<li>{{ item }}</li>{% else %}<li>No retest notes recorded.</li>{% endfor %}</ul></dd></dl></article>
  {% else %}<p class="muted">No cards.</p>{% endfor %}
  </div>
{% endfor %}
</section>
</main></body></html>"""


def requirement_review_html_template() -> str:
    return """<!doctype html>
<html lang="{{ content.locale | default("en") }}">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ content.title | default(default_title) }}</title>
  <style>
    *{box-sizing:border-box}body{margin:0;background:#f6f8fb;color:#18202a;font:14px/1.5 system-ui,sans-serif}
    main{max-width:1180px;margin:0 auto;padding:28px}header,.panel,.card{border:1px solid #d8e0ea;border-radius:8px;background:#fff;padding:14px}
    header{display:grid;gap:8px;margin-bottom:14px}h1{margin:0;font-size:26px;line-height:1.2}h2{margin:0 0 10px;font-size:18px}h3{margin:0;font-size:15px}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.stack,.card{display:grid;gap:10px}.panel{margin-bottom:14px}.muted{color:#64748b}
    .meta{display:flex;gap:6px;flex-wrap:wrap}.pill{border:1px solid #d8e0ea;border-radius:999px;background:#eef4f8;padding:2px 8px;font-size:12px;font-weight:800}
    .ready,.pass{background:#dcfce7;color:#166534}.needs_clarification,.needs_split,.concern,.unknown{background:#fef3c7;color:#92400e}.too_broad,.not_recommended,.risky,.fail{background:#fee2e2;color:#991b1b}
    .criteria,.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}dl{display:grid;gap:6px;margin:0}dt{color:#64748b;font-weight:800}dd{margin:0}ul{margin:6px 0 0;padding-left:18px}
    button{justify-self:start;border:1px solid #0f766e;border-radius:6px;background:#0f766e;color:#fff;padding:6px 10px;font-weight:800;cursor:pointer}button:disabled{cursor:default;opacity:.72}
    @media(max-width:760px){main{padding:18px}h1{font-size:22px}.grid,.criteria,.cards{grid-template-columns:1fr}}
  </style>
</head>
<body><main>
<header><div class="meta"><span class="pill">{{ content.detected_type | default("default") }}</span><span class="pill {{ content.verdict | default("unknown") }}">{{ content.verdict | default("unknown") }}</span><span class="pill">{{ content.confidence | default("medium") }}</span></div><h1>{{ content.title | default(default_title) }}</h1><div>{{ content.executive_summary | default("No summary provided.") }}</div></header>
<section class="grid"><article class="panel"><h2>Optimized Requirement</h2><dl><dt>Title</dt><dd>{{ content.optimized_requirement.title | default("-") }}</dd><dt>Todo type</dt><dd>{{ content.optimized_requirement.todo_type_id | default("default") }}</dd><dt>Description</dt><dd>{{ content.optimized_requirement.description | default("-") }}</dd></dl></article><article class="panel"><h2>Clarifying Questions</h2><ul>{% for item in content.clarifying_questions | default([]) %}<li>{{ item.question | default(item) }}{% if item.why %} <span class="muted">{{ item.why }}</span>{% endif %}</li>{% else %}<li class="muted">None recorded.</li>{% endfor %}</ul></article></section>
<section class="panel"><h2>Rubric</h2><div class="criteria">{% for item in content.rubric.criteria | default([]) %}<article class="card"><div class="meta"><span class="pill {{ item.result | default("unknown") }}">{{ item.result | default("unknown") }}</span><span class="pill">{{ item.id | default("criterion") }}</span></div><h3>{{ item.label | default("Criterion") }}</h3><dl><dt>Evidence</dt><dd><ul>{% for note in item.evidence | default([]) %}<li>{{ note }}</li>{% else %}<li class="muted">None recorded.</li>{% endfor %}</ul></dd><dt>Assumptions</dt><dd><ul>{% for note in item.assumptions | default([]) %}<li>{{ note }}</li>{% else %}<li class="muted">None recorded.</li>{% endfor %}</ul></dd><dt>Suggestions</dt><dd><ul>{% for note in item.suggestions | default([]) %}<li>{{ note }}</li>{% else %}<li class="muted">None recorded.</li>{% endfor %}</ul></dd></dl></article>{% else %}<div class="muted">No rubric criteria recorded.</div>{% endfor %}</div></section>
<section class="panel"><h2>Candidate Todo Cards</h2><div class="cards">{% for card in content.project_todo_cards | default([]) %}<article class="card"><div class="meta"><span class="pill">{{ card.todo_type_id | default("default") }}</span><span class="pill">{{ card.status | default("TODO") }}</span><span class="pill">{{ card.id | default("card") }}</span></div><h3>{{ card.title | default("Requirement") }}</h3><p>{{ card.description | default("-") }}</p><button type="button" data-card-id="{{ card.id | default(loop.index) }}">Add to board</button></article>{% else %}<div class="muted">No candidate cards recorded.</div>{% endfor %}</div></section>
<script type="application/json" id="project-todo-cards">{{ content.project_todo_cards | default([]) | tojson }}</script>
<script>
const cards = JSON.parse(document.getElementById("project-todo-cards")?.textContent || "[]");
const pending = new Map();
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-card-id]");
  if (!button) return;
  const card = cards.find((item) => item.id === button.dataset.cardId);
  if (!card) return;
  const requestId = `requirement-card-${card.id}-${Date.now()}`;
  pending.set(requestId, button);
  button.disabled = true;
  button.textContent = "Adding";
  window.parent.postMessage({ type: "web-terminal.project-todo.create", version: 1, request_id: requestId, card }, "*");
});
window.addEventListener("message", (event) => {
  const message = event.data || {};
  const button = pending.get(message.request_id);
  if (!button) return;
  if (message.type === "web-terminal.project-todo.created") { button.textContent = "Added"; pending.delete(message.request_id); }
  if (message.type === "web-terminal.project-todo.create_failed") { button.disabled = false; button.textContent = "Retry"; pending.delete(message.request_id); }
});
</script>
</main></body></html>"""


def review_agent_html_template() -> str:
    return """<!doctype html>
<html lang="{{ content.locale | default("en") }}">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ content.title | default(default_title) }}</title>
  <style>
    *{box-sizing:border-box}body{margin:0;background:#f7f9fb;color:#18202a;font:14px/1.5 system-ui,sans-serif}
    main{max-width:1240px;margin:0 auto;padding:28px}h1{margin:0;font-size:26px;line-height:1.2}h2{margin:0 0 8px;font-size:18px}.muted{color:#64748b}
    .hero,.panel,.section,.decision{border:1px solid #d7dee8;border-radius:8px;background:#fff;padding:14px}.hero{display:grid;gap:8px;margin-bottom:14px}.metric-row,.decisions{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.metric{border:1px solid #e2e8f0;border-radius:8px;background:#fbfdff;padding:10px}
    .section{margin-top:14px}.table-wrap{overflow-x:auto;border:1px solid #d7dee8;border-radius:8px}table{width:100%;min-width:760px;border-collapse:collapse;background:#fff}th,td{padding:9px 10px;border-bottom:1px solid #d7dee8;text-align:left;vertical-align:top}th{background:#eef3f8;color:#617083;font-size:12px;text-transform:uppercase}tr:last-child td{border-bottom:0}
    .status{display:inline-flex;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:800;text-transform:uppercase;background:#64748b;color:#fff}.pass{background:#047857}.warn{background:#b45309}.fail{background:#b91c1c}.unknown{background:#475569}
    ul{margin:4px 0 0;padding-left:18px}.kv{display:grid;gap:5px}.kv-row{display:grid;grid-template-columns:minmax(90px,140px) 1fr;gap:8px}.kv-key{color:#64748b;font-weight:800}
    @media(max-width:720px){main{padding:18px}.kv-row{grid-template-columns:1fr}table{min-width:640px}}
  </style>
</head>
<body><main>
{% macro render_value(value) -%}
  {% if value is mapping %}
    <div class="kv">{% for key,item in value.items() %}<div class="kv-row"><span class="kv-key">{{ key | replace("_", " ") | title }}</span><span>{{ render_value(item) }}</span></div>{% endfor %}</div>
  {% elif value is sequence and value is not string %}
    <ul>{% for item in value %}<li>{{ render_value(item) }}</li>{% endfor %}</ul>
  {% else %}{{ value | default("", true) }}{% endif %}
{%- endmacro %}
<section class="hero"><h1>{{ content.title | default(default_title) }}</h1><div class="muted">{{ content.artifact_kind | default(artifact_kind) }} / {{ content.target | default("Current review target") }}</div><div>{{ content.executive_summary | default("No summary provided.") }}</div></section>
<section class="panel"><div class="metric-row"><div class="metric"><strong>Review scope</strong><div>{{ content.review_scope | default("Scope not specified") }}</div></div><div class="metric"><strong>Presentation</strong><div>{{ content.presentation.primary | default("QA evidence table") }}</div><div class="muted">{{ content.presentation.why | default("") }}</div></div><div class="metric"><strong>Sections</strong><div>{{ (content.sections | default([])) | length }}</div></div></div></section>
{% if content.decisions | default([]) %}<section class="decisions" aria-label="Decisions">{% for decision in content.decisions %}<article class="decision"><span class="status {{ decision.status | default("unknown") }}">{{ decision.status | default("unknown") }}</span><h2>{{ decision.label | default("Decision") }}</h2><p>{{ decision.rationale | default("") }}</p><div class="muted">{{ decision.next_action | default("") }}</div></article>{% endfor %}</section>{% endif %}
{% for section in content.sections | default([]) %}
  <section class="section"><h2>{{ section.title | default("Section") }}</h2><div class="muted">{{ section.intent | default("") }}</div><div class="table-wrap"><table><thead><tr>{% for column in section.columns | default([]) %}<th>{{ column | replace("_", " ") }}</th>{% endfor %}</tr></thead><tbody>{% for item in section["items"] | default([]) %}<tr>{% for column in section.columns | default([]) %}<td>{{ render_value(item.get(column, "")) }}</td>{% endfor %}</tr>{% else %}<tr><td colspan="{{ (section.columns | default([])) | length }}">No rows.</td></tr>{% endfor %}</tbody></table></div></section>
{% endfor %}
</main></body></html>"""


def deep_research_html_template() -> str:
    return """<!doctype html>
<html lang="{{ content.locale | default("en") }}">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ content.title | default(default_title) }}</title>
  <style>
    *{box-sizing:border-box}body{margin:0;background:#f6f8fb;color:#18202a;font:15px/1.55 system-ui,sans-serif}main{max-width:1120px;margin:0 auto;padding:30px}h1{font-size:30px;line-height:1.2;margin:0 0 8px}h2{font-size:18px;margin:0 0 10px}h3{font-size:15px;margin:0 0 8px}
    .summary,.panel,details{background:#fff;border:1px solid #d7dee8;border-radius:8px;padding:16px;margin-top:14px}.summary{font-size:16px;color:#526173;max-width:860px}.research-highlight-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-top:14px}.highlight,.section-card,.recommendation{border:1px solid #d7dee8;border-radius:8px;padding:12px;background:#f9fbfd}.highlight strong{display:block;font-size:20px;margin:3px 0}.muted{color:#64748b}.sections,.recommendations{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}ul{padding-left:20px}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:560px}th,td{border:1px solid #d7dee8;padding:8px 10px;text-align:left;vertical-align:top}th{background:#eef3f8;color:#617083;font-size:12px;text-transform:uppercase}.priority{display:inline-block;border-radius:999px;background:#1f2937;color:#fff;padding:2px 8px;font-size:12px;font-weight:750}details table{display:block;overflow-x:auto}details blockquote{border-left:3px solid #94a3b8;margin:12px 0;padding:2px 0 2px 12px;color:#526173}details code{background:#eef2f7;border-radius:4px;padding:1px 4px}details pre{overflow:auto;background:#0f172a;color:#e2e8f0;border-radius:6px;padding:12px}a{color:#0369a1}
    @media(max-width:720px){main{padding:18px}h1{font-size:24px}.sections,.recommendations{grid-template-columns:1fr}}
  </style>
</head>
<body><main>
{% macro render_list(items) -%}
  <ul>{% for item in items | default([]) %}<li>{{ item }}</li>{% else %}<li class="muted">No items recorded.</li>{% endfor %}</ul>
{%- endmacro %}
<h1>{{ content.title | default(default_title) }}</h1>
{% if content.executive_summary %}<p class="summary">{{ content.executive_summary }}</p>{% endif %}
{% if content.highlights | default([]) %}<section class="research-highlight-grid">{% for item in content.highlights %}<article class="highlight"><span class="muted">{{ item.label | default("Finding") }}</span><strong>{{ item.value | default("") }}</strong><small>{{ item.detail | default("") }}</small></article>{% endfor %}</section>{% endif %}
<section class="panel"><h2>Research Analysis</h2><div class="sections">{% for section in content.sections | default([]) %}<article class="section-card"><h3>{{ section.title | default("Section") }}</h3>{% if section.takeaway %}<p>{{ section.takeaway }}</p>{% endif %}{{ render_list(section.bullets) }}{% if section.evidence | default([]) %}<h3>Evidence</h3>{{ render_list(section.evidence) }}{% endif %}</article>{% else %}<article class="section-card">No analysis sections recorded.</article>{% endfor %}</div></section>
{% set matrix = content.comparison_matrix | default({}) %}{% if matrix.columns | default([]) and matrix.rows | default([]) %}<section class="panel"><h2>Comparison Matrix</h2><div class="table-wrap"><table><thead><tr>{% for column in matrix.columns %}<th>{{ column }}</th>{% endfor %}</tr></thead><tbody>{% for row in matrix.rows %}<tr>{% for cell in row.cells | default([]) %}<td>{{ cell }}</td>{% endfor %}</tr>{% endfor %}</tbody></table></div></section>{% endif %}
{% if content.recommendations | default([]) %}<section class="panel"><h2>Recommendations</h2><div class="recommendations">{% for item in content.recommendations %}<article class="recommendation"><span class="priority">{{ item.priority | default("P1") }}</span><h3>{{ item.recommendation | default("Recommendation") }}</h3><p>{{ item.reason | default("") }}</p></article>{% endfor %}</div></section>{% endif %}
{% if content.sources | default([]) %}<section class="panel"><h2>Sources</h2><ul>{% for source in content.sources %}<li>{% if source.url %}<a href="{{ source.url }}" target="_blank" rel="noreferrer">{{ source.label | default(source.url) }}</a>{% else %}{{ source.label | default("Source") }}{% endif %} <span>{{ source.note | default("") }}</span></li>{% endfor %}</ul></section>{% endif %}
{% if content.report_markdown %}<details><summary>Raw Source Markdown</summary>{{ source_markdown_html | default("") | safe }}</details>{% endif %}
</main></body></html>"""
