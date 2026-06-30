import json
import subprocess
from pathlib import Path

from app.artifact_plugins.agent_trace_graph import AgentTraceGraphArtifactPlugin


def _trace_content() -> dict:
    return {
        "task": "Trace controls",
        "goals": [{"id": "g1", "label": "Goal"}],
        "nodes": [
            {
                "id": "n1",
                "type": "action",
                "label": "Inspect output",
                "goal": "g1",
                "step": 1,
                "status": "success",
                "detail": "Done.",
            }
        ],
        "edges": [],
    }


def test_agent_trace_graph_plugin_renders_legend_and_zoom_controls() -> None:
    rendered = AgentTraceGraphArtifactPlugin().render(_trace_content())

    assert "Legend example" in rendered.display_html
    assert "trace-zoom-out" in rendered.display_html
    assert "trace-zoom-in" in rendered.display_html
    assert "trace-zoom-reset" in rendered.display_html
    assert "setTraceZoom" in rendered.display_html
    assert 'id="trace-graph-svg"' in rendered.display_html


def test_agent_trace_graph_system_renderer_renders_legend_and_zoom_controls(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    render_script = repo_root / "backend" / "app" / "resources" / "system_skills" / "agent-trace-graph" / "scripts" / "render.py"
    input_path = tmp_path / "trace.json"
    output_path = tmp_path / "trace.html"
    input_path.write_text(json.dumps(_trace_content()), encoding="utf-8")

    result = subprocess.run(
        ["python3", str(render_script), str(input_path), "-o", str(output_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    html = output_path.read_text(encoding="utf-8")
    assert "Legend 示例" in html
    assert 'aria-label="Zoom controls"' in html
    assert 'id="zo"' in html
    assert 'id="zi"' in html
    assert "function zoom" in html
