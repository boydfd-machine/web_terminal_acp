from __future__ import annotations

import json
from typing import Any

from .types import TerminalArtifactPlugin


def agent_trace_python_source(plugin: TerminalArtifactPlugin) -> str:
    header = "\n".join([
        f"ARTIFACT_KIND = {json.dumps(plugin.artifact_kind)}",
        f"LABEL = {json.dumps(plugin.label)}",
        f"DEFAULT_TITLE = {json.dumps(plugin.default_title)}",
        "",
        "",
        "def metadata_json(content):",
        '    return {"renderer": "agent-trace-graph", "artifact_kind": ARTIFACT_KIND}',
        "",
    ])
    return header + _TRACE_LAYOUT_SOURCE.strip() + "\n"


def trace_html_template() -> str:
    return """<!doctype html>
<html lang="{{ content.locale | default("en") }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ content.task | default(default_title) }}</title>
  <style>
    body{margin:0;background:#f6f8fb;color:#17202a;font:14px/1.5 system-ui,sans-serif}
    main{max-width:1280px;margin:0 auto;padding:28px}
    h1{margin:0 0 12px;font-size:28px;line-height:1.2}
    .summary{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
    .goal{border:1px solid #cbd5e1;border-radius:999px;background:#fff;padding:5px 10px;color:#334155;font-size:12px;font-weight:700}
    .trace-tools{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:0 0 16px}
    .trace-legend{display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px;color:#334155;font-size:12px}
    .legend-title{font-weight:800;color:#0f172a}.legend-swatch{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}.legend-line{display:inline-block;width:24px;height:0;border-top:3px solid;margin-right:5px;vertical-align:3px}.legend-line.dashed{border-top-style:dashed}.legend-shape{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:1.5px solid #94a3b8;border-radius:4px;background:#fff;margin-right:5px;font-size:10px;font-weight:900;color:#64748b}
    .trace-zoom{display:inline-flex;align-items:center;gap:6px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;padding:5px}
    .trace-zoom button{min-width:31px;height:28px;border:1px solid #cbd5e1;border-radius:6px;background:#f8fafc;color:#0f172a;cursor:pointer;font-weight:800}
    .trace-zoom button:disabled{cursor:not-allowed;opacity:.45}.trace-zoom-value{min-width:48px;text-align:center;color:#334155;font-size:12px;font-weight:800}
    .canvas{overflow:auto;border:1px solid #d8e0ea;border-radius:8px;background:#fff;box-shadow:0 12px 34px rgb(15 23 42 / 8%)}
    svg{display:block;max-width:none;background:#fbfbfc}
    .edge{fill:none;stroke-width:2.3;stroke-linecap:round;stroke-linejoin:round}
    .edge.root{stroke:#1a73e8;opacity:.38}.edge.success{stroke:#16a34a}.edge.partial{stroke:#d97706}.edge.deadend{stroke:#dc2626;stroke-dasharray:7 5}.edge.neutral{stroke:#94a3b8}.edge.backtrack{stroke:#9334e6;stroke-dasharray:7 5}
    .edge-label rect{fill:#fff;stroke:currentColor;stroke-opacity:.35}.edge-label text{font-size:11px;text-anchor:middle;fill:currentColor}
    .trace-node-clickable{cursor:pointer}.trace-node-clickable:focus-visible .node-card,.trace-node-clickable:hover .node-card{stroke-width:3}
    .node-card{fill:#fff;stroke:#94a3b8;stroke-width:1.8;filter:url(#shadow)}
    .node-card.root{fill:#e8f0fe;stroke:#1a73e8}.node-card.success{stroke:#16a34a;fill:#f0fdf4}.node-card.partial{stroke:#d97706;fill:#fffbeb}.node-card.deadend{stroke:#dc2626;fill:#fef2f2}
    .node-type{fill:#64748b;font-size:11px;font-weight:800;text-transform:uppercase}.node-label{fill:#0f172a;font-size:13px;font-weight:750}.empty{padding:32px;color:#64748b;text-align:center}
    .trace-modal{position:fixed;inset:0;z-index:20;display:none;align-items:center;justify-content:center;padding:24px;background:rgb(15 23 42 / 42%)}
    .trace-modal.open{display:flex}.trace-dialog{width:min(560px,calc(100vw - 32px));max-height:calc(100vh - 48px);overflow:auto;border:1px solid #d8e0ea;border-radius:8px;background:#fff;box-shadow:0 24px 80px rgb(15 23 42 / 28%)}
    .trace-dialog header{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:16px 18px;border-bottom:1px solid #e5eaf1}
    .trace-dialog h2{margin:0;font-size:17px;line-height:1.35}.trace-close{border:1px solid #cbd5e1;border-radius:6px;background:#f8fafc;color:#0f172a;cursor:pointer;font-size:18px;line-height:1;padding:5px 9px}
    .trace-dialog-body{display:grid;gap:12px;padding:16px 18px}.trace-meta{display:flex;flex-wrap:wrap;gap:6px}.trace-chip{border:1px solid #cbd5e1;border-radius:999px;background:#f8fafc;color:#334155;font-size:12px;font-weight:750;padding:3px 8px}
    .trace-detail{white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc;color:#334155;padding:12px}
  </style>
</head>
<body><main>
  <h1>{{ content.task | default(default_title) }}</h1>
  <div class="summary">{% for goal in content.goals | default([]) %}<span class="goal">{{ goal.label | default(goal.id | default("Goal")) }}</span>{% endfor %}</div>
  {% set source_nodes = content.nodes | default([]) %}
  {% if source_nodes | length == 0 %}
    <div class="empty">No trace nodes available.</div>
  {% else %}
    <div class="trace-tools">
      <div class="trace-legend" aria-label="Legend example">
        <span class="legend-title">Legend example</span>
        <span><i class="legend-swatch" style="background:#16a34a"></i>success</span>
        <span><i class="legend-swatch" style="background:#dc2626"></i>dead end</span>
        <span><i class="legend-swatch" style="background:#d97706"></i>partial</span>
        <span><i class="legend-swatch" style="background:#94a3b8"></i>neutral</span>
        <span><i class="legend-shape">D</i>decision</span>
        <span><i class="legend-shape">A</i>action</span>
        <span><i class="legend-shape">G</i>goal</span>
        <span><i class="legend-line" style="border-color:#16a34a"></i>successful path</span>
        <span><i class="legend-line dashed" style="border-color:#9334e6"></i>backtrack</span>
      </div>
      <div class="trace-zoom" aria-label="Zoom controls">
        <button type="button" id="trace-zoom-out" aria-label="Zoom out" title="Zoom out">-</button>
        <output class="trace-zoom-value" id="trace-zoom-value">100%</output>
        <button type="button" id="trace-zoom-in" aria-label="Zoom in" title="Zoom in">+</button>
        <button type="button" id="trace-zoom-reset" aria-label="Reset zoom" title="Reset zoom">100%</button>
      </div>
    </div>
    <div class="canvas">
      <svg id="trace-graph-svg" viewBox="0 0 {{ trace.width }} {{ trace.height }}" width="{{ trace.width }}" height="{{ trace.height }}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{{ content.task | default(default_title) }}">
        <defs>
          <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="2" stdDeviation="3.5" flood-color="#0f172a" flood-opacity=".13"/></filter>
          {% for marker in trace.markers %}<marker id="arrow-{{ marker.id }}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{{ marker.color }}"/></marker>{% endfor %}
        </defs>
        {% for edge in trace.edges %}
          <g class="edge-label" style="color:{{ edge.color }}"><path class="edge {{ edge.status }} {{ edge.kind }}" data-from="{{ edge.from }}" data-to="{{ edge.to }}" data-kind="{{ edge.kind }}" d="{{ edge.path }}" marker-end="url(#arrow-{{ edge.status }})"/>{% if edge.label %}<rect x="{{ edge.label_x - edge.label_w / 2 }}" y="{{ edge.label_y - 10 }}" width="{{ edge.label_w }}" height="20" rx="10"/><text x="{{ edge.label_x }}" y="{{ edge.label_y + 4 }}">{{ edge.label }}</text>{% endif %}</g>
        {% endfor %}
        {% for node in trace.nodes %}
          <g class="node{% if node.kind != "root" %} trace-node-clickable{% endif %}" data-id="{{ node.id }}"{% if node.kind != "root" %} role="button" tabindex="0" aria-label="{{ node.label }}"{% endif %}><rect class="node-card {{ node.status }}" x="{{ node.x }}" y="{{ node.y }}" width="{{ node.width }}" height="{{ node.height }}" rx="{{ node.radius }}"/>{% if node.kind != "root" %}<text class="node-type" x="{{ node.x + 14 }}" y="{{ node.y + 24 }}">{{ node.type }} / {{ node.raw_status }}</text>{% endif %}{% for line in node.label_lines %}<text class="node-label" x="{{ node.text_x }}" y="{{ node.label_y + loop.index0 * 18 }}" {% if node.kind == "root" %}text-anchor="middle"{% endif %}>{{ line }}</text>{% endfor %}</g>
        {% endfor %}
      </svg>
    </div>
  {% endif %}
  <div class="trace-modal" id="trace-node-modal" role="dialog" aria-modal="true" aria-labelledby="trace-node-modal-title">
    <article class="trace-dialog">
      <header><h2 id="trace-node-modal-title"></h2><button class="trace-close" type="button" aria-label="Close detail" title="Close detail">&times;</button></header>
      <div class="trace-dialog-body">
        <div class="trace-meta" id="trace-node-modal-meta"></div>
        <div class="trace-detail" id="trace-node-modal-detail"></div>
      </div>
    </article>
  </div>
  <script type="application/json" id="trace-node-data">{{ trace.node_details | tojson }}</script>
  <script>
    (function () {
      var dataEl = document.getElementById('trace-node-data');
      var modal = document.getElementById('trace-node-modal');
      if (!dataEl || !modal) return;
      var nodes = {};
      try { nodes = JSON.parse(dataEl.textContent || '{}'); } catch (error) { nodes = {}; }
      var title = document.getElementById('trace-node-modal-title');
      var meta = document.getElementById('trace-node-modal-meta');
      var detail = document.getElementById('trace-node-modal-detail');
      var close = modal.querySelector('.trace-close');
      var graphSvg = document.getElementById('trace-graph-svg');
      var zoomOut = document.getElementById('trace-zoom-out');
      var zoomIn = document.getElementById('trace-zoom-in');
      var zoomReset = document.getElementById('trace-zoom-reset');
      var zoomValue = document.getElementById('trace-zoom-value');
      function setTraceZoom(nextZoom) {
        var minZoom = 0.5;
        var maxZoom = 2;
        var zoom = Math.min(maxZoom, Math.max(minZoom, Math.round(nextZoom * 100) / 100));
        var viewBox = graphSvg.viewBox && graphSvg.viewBox.baseVal;
        var baseWidth = Number(graphSvg.getAttribute('width')) || (viewBox ? viewBox.width : 0);
        var baseHeight = Number(graphSvg.getAttribute('height')) || (viewBox ? viewBox.height : 0);
        graphSvg.style.width = Math.round(baseWidth * zoom) + 'px';
        graphSvg.style.height = Math.round(baseHeight * zoom) + 'px';
        graphSvg.dataset.zoom = String(zoom);
        zoomValue.textContent = Math.round(zoom * 100) + '%';
        zoomOut.disabled = zoom <= minZoom + 0.001;
        zoomIn.disabled = zoom >= maxZoom - 0.001;
        zoomReset.disabled = Math.abs(zoom - 1) < 0.001;
      }
      if (graphSvg && zoomOut && zoomIn && zoomReset && zoomValue) {
        setTraceZoom(1);
        zoomOut.addEventListener('click', function () { setTraceZoom(Number(graphSvg.dataset.zoom || '1') - 0.1); });
        zoomIn.addEventListener('click', function () { setTraceZoom(Number(graphSvg.dataset.zoom || '1') + 0.1); });
        zoomReset.addEventListener('click', function () { setTraceZoom(1); });
      }
      function chip(value) {
        var item = document.createElement('span');
        item.className = 'trace-chip';
        item.textContent = value;
        return item;
      }
      function openNode(id) {
        var node = nodes[id];
        if (!node) return;
        var stepLabel = node.step !== null && node.step !== undefined && node.step !== '' ? '#' + node.step + ' ' : '';
        title.textContent = stepLabel + (node.label || id);
        meta.textContent = '';
        [node.type, node.status, node.goal].filter(Boolean).forEach(function (value) {
          meta.appendChild(chip(value));
        });
        detail.textContent = node.detail || 'No details available.';
        modal.classList.add('open');
        close.focus();
      }
      function closeModal() { modal.classList.remove('open'); }
      document.querySelectorAll('.trace-node-clickable[data-id]').forEach(function (node) {
        node.addEventListener('click', function () { openNode(node.dataset.id); });
        node.addEventListener('keydown', function (event) {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            openNode(node.dataset.id);
          }
        });
      });
      close.addEventListener('click', closeModal);
      modal.addEventListener('click', function (event) {
        if (event.target === modal) closeModal();
      });
      document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') closeModal();
      });
    }());
  </script>
</main></body></html>"""


_TRACE_LAYOUT_SOURCE = r'''
CARD_W = 220
CARD_H = 92
ROOT_H = 68
MARGIN = 48
COL_GAP = 58
ROW_GAP = 78
PITCH = CARD_W + COL_GAP
ROOT = "__root__"
COLORS = {"root": "#1a73e8", "success": "#16a34a", "partial": "#d97706", "deadend": "#dc2626", "neutral": "#94a3b8", "backtrack": "#9334e6"}


def template_context(content):
    return {"trace": _build_trace(content or {})}


def _build_trace(content):
    nodes = [_node(raw, i) for i, raw in enumerate(content.get("nodes") or [])]
    by_id = {node["id"]: node for node in nodes}
    raw_edges = [edge for edge in content.get("edges") or [] if isinstance(edge, dict)]
    children, parent, tree_edges = {}, {}, {}
    for edge in raw_edges:
        frm, to = str(edge.get("from", "")), str(edge.get("to", ""))
        if edge.get("kind") == "backtrack" or frm not in by_id or to not in by_id or frm == to:
            continue
        if to in parent:
            continue
        parent[to] = frm
        children.setdefault(frm, []).append(to)
        tree_edges[to] = edge
    entries = [node["id"] for node in nodes if node["id"] not in parent]
    if not entries and nodes:
        entries = [nodes[0]["id"]]
    children[ROOT] = entries
    for entry in entries:
        parent[entry] = ROOT
    for ids in children.values():
        ids.sort(key=lambda nid: _step(by_id[nid].get("step")))

    xslot, cursor = {}, [0.0]
    def assign(nid, seen=None):
        seen = set(seen or ())
        branch = [cid for cid in children.get(nid, []) if cid not in seen]
        if not branch:
            xslot[nid] = cursor[0]
            cursor[0] += 1
            return
        for cid in branch:
            assign(cid, {*seen, nid})
        xslot[nid] = sum(xslot[cid] for cid in branch) / len(branch)
    assign(ROOT)

    depth, queue = {ROOT: 0}, [ROOT]
    while queue:
        nid = queue.pop(0)
        for cid in children.get(nid, []):
            if cid not in depth:
                depth[cid] = depth[nid] + 1
                queue.append(cid)
    for node in nodes:
        if node["id"] not in depth:
            depth[node["id"]] = 1
            xslot[node["id"]] = cursor[0]
            cursor[0] += 1

    width = int(MARGIN * 2 + max(1, cursor[0]) * PITCH - COL_GAP)
    height = int(MARGIN * 2 + (max(depth.values()) + 1) * (CARD_H + ROW_GAP) - ROW_GAP)
    geom = {ROOT: _geom(width / 2 - CARD_W / 2, MARGIN, CARD_W, ROOT_H)}
    for node in nodes:
        geom[node["id"]] = _geom(MARGIN + xslot[node["id"]] * PITCH, MARGIN + depth[node["id"]] * (CARD_H + ROW_GAP), CARD_W, CARD_H)

    svg_nodes = [_svg_node(ROOT, "root", "root", "root", content.get("task") or DEFAULT_TITLE, "", "", None, geom[ROOT])]
    svg_nodes += [_svg_node(node["id"], node["type"], node["status"], node["raw_status"], node["label"], node["detail"], node["goal"], node["step"], geom[node["id"]]) for node in nodes]
    svg_edges = []
    for entry in entries:
        svg_edges.append(_edge(ROOT, entry, "", "root", "root", geom[ROOT], geom[entry]))
    for child_id, edge in tree_edges.items():
        status = _status(edge.get("status") or by_id[child_id]["status"])
        svg_edges.append(_edge(parent[child_id], child_id, edge.get("label", ""), status, "tree", geom[parent[child_id]], geom[child_id]))
    for edge in raw_edges:
        if edge.get("kind") == "backtrack" and str(edge.get("from", "")) in geom and str(edge.get("to", "")) in geom:
            svg_edges.append(_side_edge(str(edge.get("from")), str(edge.get("to")), "backtrack " + str(edge.get("label", "") or ""), geom[str(edge.get("from"))], geom[str(edge.get("to"))]))
    return {"width": width, "height": height, "nodes": svg_nodes, "edges": svg_edges, "markers": [{"id": key, "color": value} for key, value in COLORS.items()], "node_details": {node["id"]: node for node in svg_nodes}}


def _node(raw, index):
    nid = str(raw.get("id") or f"n{index + 1}")
    raw_status = str(raw.get("status") or "neutral")
    return {"id": nid, "type": str(raw.get("type") or "action"), "label": str(raw.get("label") or nid), "detail": str(raw.get("detail") or ""), "goal": str(raw.get("goal") or ""), "raw_status": raw_status, "status": _status(raw_status), "step": raw.get("step")}


def _status(value):
    text = str(value or "neutral").lower()
    if text in {"success", "root", "backtrack"}:
        return text
    if text in {"warning", "partial"}:
        return "partial"
    if text in {"error", "failed", "deadend"}:
        return "deadend"
    return "neutral"


def _geom(x, y, w, h):
    return {"x": round(x, 1), "y": round(y, 1), "w": w, "h": h, "cx": round(x + w / 2, 1), "top": y, "bottom": y + h, "cy": y + h / 2}


def _step(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _svg_node(nid, typ, status, raw_status, label, detail, goal, step, g):
    root = nid == ROOT
    lines = _wrap(label, 28 if root else 24, 2)
    return {"id": nid, "kind": "root" if root else "node", "type": typ, "status": status, "raw_status": raw_status, "label": label, "goal": goal, "step": step, "detail": detail, "label_lines": lines, "x": g["x"], "y": g["y"], "width": g["w"], "height": g["h"], "radius": 20 if root else 10, "text_x": g["cx"] if root else g["x"] + 14, "label_y": g["y"] + (30 if root else 52)}


def _edge(frm, to, label, status, kind, s, t):
    sy, ty = s["bottom"], t["top"]
    mid_y = sy + (ty - sy) / 2
    path = f'M{s["cx"]},{sy} C{s["cx"]},{mid_y} {t["cx"]},{mid_y} {t["cx"]},{ty}'
    return _edge_data(frm, to, label, status, kind, path, (s["cx"] + t["cx"]) / 2, mid_y)


def _side_edge(frm, to, label, s, t):
    side = min(s["x"], t["x"]) - 30 if t["cx"] <= s["cx"] else max(s["x"] + s["w"], t["x"] + t["w"]) + 30
    path = f'M{s["cx"]},{s["cy"]} L{side},{s["cy"]} L{side},{t["cy"]} L{t["cx"]},{t["cy"]}'
    return _edge_data(frm, to, label, "backtrack", "backtrack", path, side, (s["cy"] + t["cy"]) / 2)


def _edge_data(frm, to, label, status, kind, path, lx, ly):
    label = _short(label, 20)
    return {"from": frm, "to": to, "label": label, "label_w": max(34, len(label) * 7 + 16), "label_x": round(lx, 1), "label_y": round(ly, 1), "status": status, "kind": kind, "path": path, "color": COLORS.get(status, COLORS["neutral"])}


def _wrap(value, limit, max_lines):
    text = str(value or "")
    lines = [text[i:i + limit] for i in range(0, len(text), limit)] or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _short(lines[-1], limit)
    return lines


def _short(value, limit):
    text = str(value or "")
    return text if len(text) <= limit else text[: max(0, limit - 3)] + "..."
'''
