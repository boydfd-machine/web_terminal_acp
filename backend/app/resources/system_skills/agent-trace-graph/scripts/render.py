#!/usr/bin/env python3
"""
Render an agent intent-tree JSON into a single self-contained HTML page with a
hand-laid-out SVG diagram (no external libraries, works offline).

Usage:
    python3 render.py trace.json [-o out.html]
    cat trace.json | python3 render.py -            # read JSON from stdin

LAYOUT = TOP-DOWN TREE (tidy tree). The shape is derived from the EDGES, not
from step order:
  - `tried` / `leads-to` edges define parent -> child flow. They build the tree.
  - A failed attempt (status=deadend) is a LEAF: nothing flows out of it.
  - When the agent backtracks, the retry's `tried` edge originates from the node
    it actually RETURNED to (which may be several steps up), so the retry becomes
    a SIBLING branch, not a successor of the dead-end.
  - `backtrack` edges are drawn as purple dashed annotations from the dead-end
    back up to the returned-to ancestor; they do NOT affect tree parentage.
Multiple goals => multiple subtrees under the root, each ending in a green goal.

Colours encode status (green=success, red=deadend, amber=partial, grey=neutral,
purple=backtrack). Hovering a node/edge highlights the related lines with a
flowing-dash animation and dims the rest. Clicking a node opens a detail panel.

The agent only produces JSON — all geometry/SVG is generated here.
"""
import sys, json, html, argparse, math
from collections import defaultdict

PALETTE = {
    "success": {"line": "#1e8e3e", "fill": "#eafaf0", "text": "#0d652d"},
    "deadend": {"line": "#d93025", "fill": "#fdecea", "text": "#a50e0e"},
    "failed":  {"line": "#d93025", "fill": "#fdecea", "text": "#a50e0e"},
    "partial": {"line": "#f29900", "fill": "#fff7e0", "text": "#7a5200"},
    "neutral": {"line": "#80868b", "fill": "#f4f5f6", "text": "#3c4043"},
}
EDGE_COL = {"success": "#1e8e3e", "deadend": "#d93025", "partial": "#f29900",
            "neutral": "#9aa0a6", "backtrack": "#9334e6", "root": "#1a73e8",
            "cross": "#b0b3b8"}
TYPE_GLYPH = {"decision": "◆", "action": "■", "goal": "★"}

ROOT = "__root__"

# ---- geometry ---------------------------------------------------------------
MARGIN    = 56
CARD_W    = 240
HGAP      = 46
COL_PITCH = CARD_W + HGAP
ROW_TOP   = 38
VGAP      = 72
FS_TITLE  = 14
LINE_H    = 20
PAD_X     = 18
PAD_TOP   = 48
PAD_BOT   = 16


def char_w(ch, fs):
    o = ord(ch)
    if o > 0x2E80 or o in (0x2014, 0x2026):
        return fs * 1.0
    return fs * 0.56


def wrap(text, max_w, fs):
    lines, cur, cur_w = [], "", 0.0
    for ch in str(text):
        if ch == "\n":
            lines.append(cur); cur, cur_w = "", 0.0; continue
        w = char_w(ch, fs)
        if cur_w + w > max_w and cur:
            lines.append(cur); cur, cur_w = ch, w
        else:
            cur += ch; cur_w += w
    if cur:
        lines.append(cur)
    return lines or [""]


def x(s):
    return html.escape(str(s), quote=True)


def rounded(pts, r=14):
    pts = [(float(a), float(b)) for a, b in pts]
    if len(pts) == 2:
        return "M%.1f,%.1f L%.1f,%.1f" % (pts[0][0], pts[0][1], pts[1][0], pts[1][1])
    d = "M%.1f,%.1f" % pts[0]
    for i in range(1, len(pts) - 1):
        x0, y0 = pts[i - 1]; x1, y1 = pts[i]; x2, y2 = pts[i + 1]
        d1 = math.hypot(x1 - x0, y1 - y0) or 1
        d2 = math.hypot(x2 - x1, y2 - y1) or 1
        rr = min(r, d1 / 2, d2 / 2)
        ex, ey = x1 - (x1 - x0) / d1 * rr, y1 - (y1 - y0) / d1 * rr
        sx, sy = x1 + (x2 - x1) / d2 * rr, y1 + (y2 - y1) / d2 * rr
        d += " L%.1f,%.1f Q%.1f,%.1f %.1f,%.1f" % (ex, ey, x1, y1, sx, sy)
    d += " L%.1f,%.1f" % pts[-1]
    return d


def build_svg(data):
    nodes = data["nodes"]
    edges = data.get("edges", [])
    task  = data.get("task", "Agent task")
    by_id = {n["id"]: n for n in nodes}

    # ---- build tree from tried/leads-to edges ----
    parent = {}
    children = defaultdict(list)
    cross_edges = []      # extra (non-tree) parent links -> drawn faint
    tree_edge_of = {}     # child id -> edge dict (for status/label)
    for e in edges:
        if e.get("kind") == "backtrack":
            continue
        frm, to = e.get("from"), e.get("to")
        if frm not in by_id or to not in by_id:
            continue
        if to in parent:
            cross_edges.append(e)
        else:
            parent[to] = frm
            children[frm].append(to)
            tree_edge_of[to] = e

    # entries (no tree parent) attach to synthetic root, ordered by step
    def stepkey(nid):
        s = by_id[nid].get("step")
        return (s is None, s if s is not None else 0)

    entries = sorted([n["id"] for n in nodes if n["id"] not in parent], key=stepkey)
    children[ROOT] = entries
    for nid in entries:
        parent[nid] = ROOT
    for k in children:
        children[k].sort(key=stepkey)

    # ---- card heights ----
    height = {}
    wrapped = {}
    for n in nodes:
        inner = CARD_W - 2 * PAD_X - 8
        lines = wrap(n.get("label", n["id"]), inner, FS_TITLE)
        wrapped[n["id"]] = lines
        h = PAD_TOP + len(lines) * LINE_H + PAD_BOT
        if n.get("type") == "goal":
            h = max(h, 64)
        height[n["id"]] = h
    rtitle = "🎯 " + task
    rlines = wrap(rtitle, min(640, 900) - 48, 16)
    if len(rlines) > 2:
        rlines = rlines[:2]; rlines[1] = rlines[1][:-1] + "…"
    height[ROOT] = 56 if len(rlines) == 1 else 78

    # ---- depth (BFS) ----
    depth = {ROOT: 0}
    queue = [ROOT]
    order = []
    while queue:
        cur = queue.pop(0)
        order.append(cur)
        for c in children.get(cur, []):
            if c not in depth:
                depth[c] = depth[cur] + 1
                queue.append(c)

    # ---- x slots (tidy tree: leaves sequential, parents centred) ----
    xslot = {}
    cursor = [0.0]
    sys.setrecursionlimit(10000)

    def assign_x(node):
        ch = children.get(node, [])
        if not ch:
            xslot[node] = cursor[0]
            cursor[0] += 1
            return
        for c in ch:
            assign_x(c)
        xslot[node] = sum(xslot[c] for c in ch) / len(ch)

    assign_x(ROOT)
    leaf_count = max(1, int(round(cursor[0])))

    # ---- row Y by depth (variable row heights) ----
    max_depth = max(depth.values())
    row_h = {d: 0 for d in range(max_depth + 1)}
    for nid, d in depth.items():
        row_h[d] = max(row_h[d], height[nid])
    row_y = {0: ROW_TOP}
    for d in range(1, max_depth + 1):
        row_y[d] = row_y[d - 1] + row_h[d - 1] + VGAP

    # ---- pixel geometry ----
    geom = {}
    for nid, d in depth.items():
        cx = MARGIN + CARD_W / 2 + xslot[nid] * COL_PITCH
        top = row_y[d]
        h = height[nid]
        geom[nid] = {"cx": cx, "left": cx - CARD_W / 2, "right": cx + CARD_W / 2,
                     "top": top, "bot": top + h, "cy": top + h / 2, "h": h}

    total_w = MARGIN * 2 + (leaf_count - 1) * COL_PITCH + CARD_W
    total_h = row_y[max_depth] + row_h[max_depth] + MARGIN

    out = [
        f'<svg viewBox="0 0 {int(total_w)} {int(total_h)}" width="{int(total_w)}" '
        f'height="{int(total_h)}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,PingFang SC,Microsoft YaHei,sans-serif">'
    ]
    out.append("<defs>")
    out.append('<filter id="sh" x="-20%" y="-20%" width="140%" height="140%">'
               '<feDropShadow dx="0" dy="2" stdDeviation="3.5" flood-color="#000" flood-opacity="0.13"/></filter>')
    for key, col in EDGE_COL.items():
        out.append(f'<marker id="ar-{key}" viewBox="0 0 10 10" refX="8.5" refY="5" '
                   f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                   f'<path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
    out.append("</defs>")
    out.append(f'<rect x="0" y="0" width="{int(total_w)}" height="{int(total_h)}" fill="#fbfbfc"/>')

    edge_html = []

    def emit_edge(eid, frm, to, d, col, ckey, label, sw, dashed):
        dash = ' stroke-dasharray="7 5"' if dashed else ""
        g = [f'<g class="edge" data-id="{eid}" data-from="{x(frm)}" data-to="{x(to)}">']
        g.append(f'<path class="hit" d="{d}" fill="none" stroke="#000" stroke-opacity="0" stroke-width="16"/>')
        g.append(f'<path class="line" d="{d}" fill="none" stroke="{col}" stroke-width="{sw}"{dash} '
                 f'marker-end="url(#ar-{ckey})" stroke-linecap="round" stroke-linejoin="round"/>')
        if label:
            mx, my = midpoints.get(eid, (0, 0))
            lw = sum(char_w(c, 11) for c in label) + 16
            g.append(f'<g class="elabel"><rect x="{mx-lw/2:.1f}" y="{my-10:.1f}" width="{lw:.1f}" '
                     f'height="20" rx="9" fill="#ffffff" stroke="{col}" stroke-opacity="0.4"/>'
                     f'<text x="{mx:.1f}" y="{my+4:.1f}" font-size="11" fill="{col}" '
                     f'text-anchor="middle">{x(label)}</text></g>')
        g.append("</g>")
        edge_html.append("".join(g))

    midpoints = {}

    # ---- tree edges (parent -> child, vertical) ----
    for ix, (cid, e) in enumerate(tree_edge_of.items()):
        pid = parent[cid]
        s, t = geom[pid], geom[cid]
        sx, sy = s["cx"], s["bot"]
        tx, ty = t["cx"], t["top"]
        dy = ty - sy
        d = (f'M{sx:.1f},{sy:.1f} C{sx:.1f},{sy+dy*0.5:.1f} {tx:.1f},{ty-dy*0.5:.1f} {tx:.1f},{ty:.1f}')
        status = e.get("status", "neutral")
        ckey = status if status in ("success", "deadend", "partial") else "neutral"
        col = EDGE_COL[ckey]
        sw = 3 if ckey == "success" else (2.2 if ckey != "neutral" else 1.7)
        eid = f"te{ix}"
        midpoints[eid] = ((sx + tx) / 2, sy + dy * 0.5)
        emit_edge(eid, pid, cid, d, col, ckey, e.get("label", ""), sw, ckey == "deadend")

    # ---- root -> entries (blue, faint) ----
    for ix, cid in enumerate(entries):
        s, t = geom[ROOT], geom[cid]
        sx, sy = s["cx"], s["bot"]
        tx, ty = t["cx"], t["top"]
        dy = ty - sy
        d = (f'M{sx:.1f},{sy:.1f} C{sx:.1f},{sy+dy*0.5:.1f} {tx:.1f},{ty-dy*0.5:.1f} {tx:.1f},{ty:.1f}')
        eid = f"re{ix}"
        emit_edge(eid, ROOT, cid, d, EDGE_COL["root"], "root", "", 1.8, False)
        edge_html[-1] = edge_html[-1].replace('class="line"', 'class="line" opacity="0.5"')

    # ---- backtrack edges (dead-end -> ancestor, dashed, routed via side) ----
    bt_local = 0
    for e in edges:
        if e.get("kind") != "backtrack":
            continue
        frm, to = e.get("from"), e.get("to")
        if frm not in geom or to not in geom:
            continue
        s, t = geom[frm], geom[to]
        left_side = t["cx"] <= s["cx"]
        if left_side:
            sx, tx = s["left"], t["left"]
            chx = min(s["left"], t["left"]) - (40 + bt_local * 22)
        else:
            sx, tx = s["right"], t["right"]
            chx = max(s["right"], t["right"]) + (40 + bt_local * 22)
        bt_local += 1
        sy, ty = s["cy"], t["cy"]
        d = rounded([(sx, sy), (chx, sy), (chx, ty), (tx, ty)])
        label = e.get("label", "")
        label = ("↩ " + label) if label else "↩"
        eid = f"bt{bt_local}"
        midpoints[eid] = (chx, (sy + ty) / 2)
        emit_edge(eid, frm, to, d, EDGE_COL["backtrack"], "backtrack", label, 2.2, True)

    # ---- cross edges (extra parents, faint dashed) ----
    for ix, e in enumerate(cross_edges):
        frm, to = e["from"], e["to"]
        s, t = geom[frm], geom[to]
        sx, sy = s["cx"], s["bot"]
        tx, ty = t["cx"], t["top"]
        d = f'M{sx:.1f},{sy:.1f} C{sx:.1f},{(sy+ty)/2:.1f} {tx:.1f},{(sy+ty)/2:.1f} {tx:.1f},{ty:.1f}'
        eid = f"ce{ix}"
        midpoints[eid] = ((sx + tx) / 2, (sy + ty) / 2)
        emit_edge(eid, frm, to, d, EDGE_COL["cross"], "cross", e.get("label", ""), 1.5, True)

    out.extend(edge_html)

    # ---- root node ----
    rg = geom[ROOT]
    rw = max(300, max(sum(char_w(c, 16) for c in ln) for ln in rlines) + 50)
    rw = min(rw, total_w - 2 * MARGIN)
    rh = rg["h"]
    out.append(f'<g class="node" data-id="{ROOT}"><rect x="{rg["cx"]-rw/2:.0f}" y="{rg["top"]:.0f}" '
               f'width="{rw:.0f}" height="{rh:.0f}" rx="20" fill="#e8f0fe" stroke="#1a73e8" '
               f'stroke-width="2" filter="url(#sh)"/>')
    ry = rg["top"] + (rh - (len(rlines) - 1) * 22) / 2 + 6
    for ln in rlines:
        out.append(f'<text x="{rg["cx"]:.0f}" y="{ry:.0f}" font-size="16" font-weight="700" '
                   f'fill="#174ea6" text-anchor="middle">{x(ln)}</text>')
        ry += 22
    out.append("</g>")

    # ---- node cards ----
    for n in nodes:
        nid = n["id"]
        g = geom[nid]
        st = n.get("status", "neutral")
        pal = PALETTE.get(st, PALETTE["neutral"])
        typ = n.get("type", "action")
        left, top, h = g["left"], g["top"], g["h"]
        is_goal = typ == "goal"
        rx = min(h / 2, 32) if is_goal else 14
        fill = pal["fill"] if is_goal else "#ffffff"
        sw = 2.2 if is_goal else 1.6
        out.append(f'<g class="node" data-id="{x(nid)}" style="cursor:pointer">')
        out.append(f'<rect class="card" x="{left:.1f}" y="{top:.1f}" width="{CARD_W}" height="{h:.1f}" '
                   f'rx="{rx:.0f}" fill="{fill}" stroke="{pal["line"]}" stroke-width="{sw}" filter="url(#sh)"/>')
        if not is_goal:
            out.append(f'<rect x="{left:.1f}" y="{top:.1f}" width="6" height="{h:.1f}" '
                       f'fill="{pal["line"]}" rx="3"/>'
                       f'<rect x="{left+3:.1f}" y="{top:.1f}" width="4" height="{h:.1f}" fill="{fill}"/>')
        tx0 = left + PAD_X + (4 if not is_goal else 0)
        if is_goal:
            out.append(f'<text x="{g["cx"]:.0f}" y="{top+h/2+5:.0f}" font-size="15" font-weight="800" '
                       f'fill="{pal["text"]}" text-anchor="middle">{x(n.get("label", nid))}</text>')
        else:
            step = n.get("step")
            badge_y = top + 13
            if step is not None:
                bw = 22 + len(str(step)) * 7
                out.append(f'<rect x="{tx0:.1f}" y="{badge_y:.1f}" width="{bw}" height="19" rx="9.5" '
                           f'fill="{pal["line"]}"/>'
                           f'<text x="{tx0+bw/2:.1f}" y="{badge_y+14:.1f}" font-size="11.5" '
                           f'font-weight="700" fill="#fff" text-anchor="middle">#{step}</text>')
            out.append(f'<text x="{left+CARD_W-14:.0f}" y="{badge_y+14:.0f}" font-size="12" '
                       f'fill="{pal["line"]}" text-anchor="end" opacity="0.85">{TYPE_GLYPH.get(typ,"")}</text>')
            ty = top + PAD_TOP
            for ln in wrapped[nid]:
                out.append(f'<text x="{tx0:.1f}" y="{ty:.1f}" font-size="{FS_TITLE}" '
                           f'fill="#202124" font-weight="600">{x(ln)}</text>')
                ty += LINE_H
        out.append("</g>")

    out.append("</svg>")
    return "".join(out)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;background:#f4f5f7;color:#202124}header{padding:14px 22px;background:#fff;border-bottom:1px solid #e6e6ea}h1{margin:0;font-size:17px}.sub{color:#5f6368;font-size:12.5px;margin-top:4px}.tools{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-top:10px}.legend{display:flex;gap:8px 12px;flex-wrap:wrap;font-size:12px;color:#3c4043}.legend span{display:inline-flex;align-items:center;gap:6px}.title{font-weight:800;color:#202124}.dot{width:22px;height:0;border-top:3px solid;border-radius:2px}.dot.dash{border-top-style:dashed}.sw{width:11px;height:11px;border-radius:3px}.shape{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:1.5px solid #9aa0a6;border-radius:4px;background:#fff;font-size:10px;font-weight:800}.zoom{display:inline-flex;align-items:center;gap:6px;border:1px solid #d8dce2;border-radius:8px;background:#fff;padding:5px}.zoom button{height:28px;min-width:31px;border:1px solid #cfd4dc;border-radius:6px;background:#f8f9fa;color:#202124;cursor:pointer;font-weight:800}.zoom button:disabled{cursor:not-allowed;opacity:.45}#zv{min-width:48px;text-align:center;font-size:12px;font-weight:800;color:#3c4043}.layout{display:flex;height:calc(100vh - 148px)}#graph{flex:1;overflow:auto;padding:24px}#graph svg{display:block}#panel{width:360px;flex-shrink:0;border-left:1px solid #e6e6ea;background:#fff;padding:22px;overflow:auto}#panel.empty{color:#9aa0a6;display:flex;align-items:center;justify-content:center;text-align:center;font-size:14px}#panel h2{font-size:15px;margin:0 0 8px;line-height:1.4}#panel .badge{display:inline-block;font-size:11px;font-weight:700;padding:3px 10px;border-radius:11px;margin-bottom:12px}#panel .detail{white-space:pre-wrap;font-size:13px;line-height:1.7;background:#f8f9fa;border:1px solid #ececf0;border-radius:10px;padding:14px}.b-success{background:#e9f7ef;color:#0d652d}.b-deadend{background:#fdecea;color:#a50e0e}.b-partial{background:#fff7e0;color:#7a5200}.b-neutral{background:#f1f3f4;color:#3c4043}.edge .line{transition:opacity .15s,stroke-width .15s}.edge .hit{cursor:pointer}.node{transition:opacity .15s}.node .card{transition:stroke-width .12s}.node:hover .card{stroke-width:3.4}@keyframes flow{to{stroke-dashoffset:-32}}svg.act .edge:not(.hl){opacity:.10}svg.act .node:not(.hl){opacity:.34}.edge.hl .line{stroke-width:3.6!important;stroke-dasharray:10 7!important;animation:flow .65s linear infinite;opacity:1!important}
</style></head><body><header><h1>__TITLE__</h1><div class="sub">树状执行路径 · 失败=岔出的死枝,重试从「回到的节点」长出兄弟分支 · 悬停高亮 · 点击看详情</div>
<div class="tools"><div class="legend" aria-label="Legend example"><span class="title">Legend 示例</span><span><i class="sw" style="background:#1e8e3e"></i>走通</span><span><i class="sw" style="background:#d93025"></i>碰壁</span><span><i class="sw" style="background:#f29900"></i>部分</span><span><i class="sw" style="background:#9aa0a6"></i>中间</span><span><i class="shape">D</i>decision</span><span><i class="shape">A</i>action</span><span><i class="shape">G</i>goal</span><span><i class="dot" style="border-color:#1e8e3e"></i>成功边</span><span><i class="dot dash" style="border-color:#9334e6"></i>↩ 回溯</span></div><div class="zoom" aria-label="Zoom controls"><button id="zo" type="button" title="Zoom out" aria-label="Zoom out">-</button><output id="zv">100%</output><button id="zi" type="button" title="Zoom in" aria-label="Zoom in">+</button><button id="zr" type="button" title="Reset zoom" aria-label="Reset zoom">100%</button></div></div></header>
<div class="layout"><div id="graph">__SVG__</div><div id="panel" class="empty">← 点击节点查看详情</div></div>
<script>
const NODES=__NODES_JSON__,SL={success:"走通 success",deadend:"碰壁 deadend",failed:"碰壁 failed",partial:"部分成功 partial",neutral:"中间步骤 neutral"};
function esc(s){return String(s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
const svg=document.querySelector("#graph svg"),edges=[...svg.querySelectorAll(".edge")],nodes=[...svg.querySelectorAll(".node")],zo=document.getElementById("zo"),zi=document.getElementById("zi"),zr=document.getElementById("zr"),zv=document.getElementById("zv");
function zoom(v){const min=.5,max=2,z=Math.min(max,Math.max(min,Math.round(v*100)/100)),bw=+svg.getAttribute("width"),bh=+svg.getAttribute("height");svg.style.width=Math.round(bw*z)+"px";svg.style.height=Math.round(bh*z)+"px";svg.dataset.zoom=z;zv.textContent=Math.round(z*100)+"%";zo.disabled=z<=min+.001;zi.disabled=z>=max-.001;zr.disabled=Math.abs(z-1)<.001}
zoom(1);zo.onclick=()=>zoom(+(svg.dataset.zoom||1)-.1);zi.onclick=()=>zoom(+(svg.dataset.zoom||1)+.1);zr.onclick=()=>zoom(1);
function clearHi(){svg.classList.remove("act");edges.forEach(e=>e.classList.remove("hl"));nodes.forEach(n=>n.classList.remove("hl"))}
function applyHi(edgeEls,nodeIds){svg.classList.add("act");edgeEls.forEach(e=>e.classList.add("hl"));nodes.forEach(n=>{if(nodeIds.has(n.dataset.id))n.classList.add("hl")})}
edges.forEach(e=>{e.addEventListener("mouseenter",()=>{clearHi();applyHi([e],new Set([e.dataset.from,e.dataset.to]))});e.addEventListener("mouseleave",clearHi)});
nodes.forEach(n=>{n.addEventListener("mouseenter",()=>{const id=n.dataset.id,rel=edges.filter(e=>e.dataset.from===id||e.dataset.to===id),ids=new Set([id]);rel.forEach(e=>{ids.add(e.dataset.from);ids.add(e.dataset.to)});clearHi();applyHi(rel,ids)});n.addEventListener("mouseleave",clearHi);n.addEventListener("click",()=>{const nd=NODES[n.dataset.id];if(!nd)return;const p=document.getElementById("panel"),st=nd.status||"neutral";p.classList.remove("empty");p.innerHTML=`<h2>${(nd.step!=null?"#"+nd.step+" ":"")+esc(nd.label||n.dataset.id)}</h2><span class="badge b-${st}">${SL[st]||st}</span>${nd.cost?`<div class="detail" style="margin-bottom:10px">⏱ ${esc(nd.cost)}</div>`:""}<div class="detail">${esc(nd.detail||"(无详情)")}</div>`})});
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", default=None)
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    data = json.loads(raw)

    if "nodes" not in data or not data["nodes"]:
        sys.exit("ERROR: JSON must contain a non-empty 'nodes' array.")
    ids = [n.get("id") for n in data["nodes"]]
    if len(ids) != len(set(ids)):
        sys.exit("ERROR: duplicate node ids found.")
    idset = set(ids)
    for e in data.get("edges", []):
        for end in ("from", "to"):
            if e.get(end) not in idset:
                sys.exit(f"ERROR: edge references unknown node id: {e.get(end)!r}")
    if not any(n.get("status") == "success" for n in data["nodes"]):
        sys.stderr.write("WARN: no node has status 'success' — graph has no green endpoint.\n")

    svg = build_svg(data)
    node_map = {n["id"]: n for n in data["nodes"]}
    title = html.escape(data.get("task", "Agent Trace"))
    out = (HTML_TEMPLATE
           .replace("__TITLE__", title)
           .replace("__SVG__", svg)
           .replace("__NODES_JSON__", json.dumps(node_map, ensure_ascii=False)))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"Wrote {args.output}")
    else:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()
