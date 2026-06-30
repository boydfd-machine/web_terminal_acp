from __future__ import annotations

from pathlib import Path
import sys

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS_ROOT = REPO_ROOT / "artifacts"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from acas_sharded_assets import load_acas_asset  # noqa: E402

PAGES_ARTIFACT = ARTIFACTS_ROOT / "page_artifact"
PAGES_PATH = PAGES_ARTIFACT / "instances" / "global" / "assets" / "page_wireframe_inventory.yaml"
RENDERER_PATH = PAGES_ARTIFACT / "definition" / "renderer" / "index.html"


def _load_pages() -> dict:
    loaded = load_acas_asset(PAGES_PATH)
    assert isinstance(loaded, dict)
    return loaded


def _flatten_pages(pages: list[dict]) -> list[dict]:
    flattened: list[dict] = []
    for page in pages:
        flattened.append(page)
        flattened.extend(_flatten_pages(page.get("children") or []))
    return flattened


def test_acas_pages_have_existing_png_screenshots_for_every_page() -> None:
    inventory = _load_pages()
    pages = _flatten_pages(inventory["pages"])

    assert len(pages) == inventory["summary"]["totalPages"]
    assert inventory["summary"]["screenshotRefs"] == len(pages)
    assert "screenshotMethod" in inventory["mappingMethod"]
    assert "renderer.html" not in inventory["mappingMethod"]["screenshotMethod"]
    for page in pages:
        screenshot = page.get("screenshot")
        assert isinstance(screenshot, dict), page["pageId"]
        path = screenshot.get("path")
        assert isinstance(path, str) and path.startswith("./screenshots/"), page["pageId"]
        assert path.endswith(".png"), page["pageId"]
        assert screenshot.get("source") == "real-frontend-mock-api"
        assert "renderer.html" not in str(screenshot.get("capturedFrom")), page["pageId"]
        assert str(screenshot.get("capturedFrom")).startswith("real-frontend:"), page["pageId"]
        assert (PAGES_PATH.parent / path).resolve().is_file(), path


def test_acas_pages_renderer_displays_page_screenshots() -> None:
    renderer = RENDERER_PATH.read_text(encoding="utf-8")

    assert "page-screenshot" in renderer
    assert "screenshotFigure" in renderer
    assert "p.screenshot?.path" in renderer


def test_acas_pages_wireframes_are_semantic_ascii_element_maps() -> None:
    inventory = _load_pages()
    pages = _flatten_pages(inventory["pages"])

    assert "Semantic ASCII wireframes" in inventory["mappingMethod"]["wireframeMethod"]
    for page in pages:
        wireframe = page.get("wireframe")
        assert isinstance(wireframe, str), page["pageId"]
        assert "PNG-derived" not in wireframe, page["pageId"]
        assert "+-" in wireframe or "|-" in wireframe, page["pageId"]
        assert page["name"] in wireframe, page["pageId"]
        assert "Element coverage:" in wireframe, page["pageId"]
        assert "Title:" in wireframe, page["pageId"]
        assert "Sections:" in wireframe, page["pageId"]
        assert "Buttons/Controls:" in wireframe, page["pageId"]
        assert "Data/States:" in wireframe, page["pageId"]


def test_acas_pages_renderer_displays_semantic_ascii_wireframes_next_to_screenshots() -> None:
    renderer = RENDERER_PATH.read_text(encoding="utf-8")

    assert "ascii-wireframe" in renderer
    assert "semanticAsciiWireframeFigure" in renderer
    assert "wireframe-pair" in renderer
    assert "Semantic ASCII wireframe" in renderer
    assert "PNG-derived" not in renderer


def test_acas_root_artifacts_index_progressively_loads_artifact_renderers() -> None:
    renderer = (ARTIFACTS_ROOT / "index.html").read_text(encoding="utf-8")
    index = yaml.safe_load((ARTIFACTS_ROOT / "index.json").read_text(encoding="utf-8"))
    artifact_ids = {artifact["artifactId"] for artifact in index["artifacts"]}

    assert index["kind"] == "AcasArtifactCatalog"
    assert {"capability_map", "entity", "api", "page"} <= artifact_ids
    assert "createRendererFrame" in renderer
    assert "iframe" in renderer
    assert "rendererPath" in renderer
    assert "traceRoot" in renderer
