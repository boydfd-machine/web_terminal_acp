from __future__ import annotations

import json
from pathlib import Path
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS_ROOT = REPO_ROOT / "artifacts"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from acas_sharded_assets import load_acas_asset  # noqa: E402

REQUIRED_ARTIFACTS = {
    "capability_map": "capability_map_artifact",
    "entity": "entity_artifact",
    "api": "api_artifact",
    "page": "page_artifact",
}
REQUIRED_SHARDED_ASSETS = {
    "capability_map_artifact": ["capability_map_current.yaml"],
    "entity_artifact": ["entity_inventory.yaml", "entity_operation_groups.yaml"],
    "api_artifact": ["api_inventory.yaml", "api_capability_map_current.yaml", "api_structure.yaml"],
    "page_artifact": ["page_wireframe_inventory.yaml"],
}
MAIN_ASSET_MAX_BYTES = 64 * 1024


def _load_json(path: Path) -> dict:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _load_yaml(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _asset_manifest(path: Path) -> dict:
    manifest = _load_yaml(path).get("assetManifest")
    assert isinstance(manifest, dict), path
    return manifest


def _shard_paths(path: Path) -> list[str]:
    return [
        shard["path"].lstrip("./")
        for fragment in _asset_manifest(path)["fragments"]
        for shard in fragment["shards"]
    ]


def _flatten_pages(pages: list[dict]) -> list[dict]:
    flattened: list[dict] = []
    for page in pages:
        flattened.append(page)
        flattened.extend(_flatten_pages(page.get("children") or []))
    return flattened


def test_acas_artifact_catalog_lists_split_artifacts_with_renderer_paths() -> None:
    catalog = _load_json(ARTIFACTS_ROOT / "index.json")
    by_id = {artifact["artifactId"]: artifact for artifact in catalog["artifacts"]}

    assert catalog["kind"] == "AcasArtifactCatalog"
    assert set(REQUIRED_ARTIFACTS) <= set(by_id)
    for artifact_id, directory in REQUIRED_ARTIFACTS.items():
        artifact = by_id[artifact_id]
        assert artifact["directory"] == directory
        assert artifact["rendererPath"].endswith("/definition/renderer/index.html")
        assert (ARTIFACTS_ROOT / artifact["rendererPath"]).is_file()
        assert (ARTIFACTS_ROOT / artifact["metadataPath"]).is_file()
        assert artifact["globalIndexPath"].endswith("/instances/global/index.json")
        assert (ARTIFACTS_ROOT / artifact["globalIndexPath"]).is_file()


def test_each_acas_artifact_has_definition_and_global_instance_layers() -> None:
    for artifact_id, directory in REQUIRED_ARTIFACTS.items():
        root = ARTIFACTS_ROOT / directory
        meta = _load_json(root / "definition" / "META.json")
        index = _load_json(root / "instances" / "global" / "index.json")
        export = _load_json(root / "instances" / "global" / "export.json")
        dependencies = _load_json(root / "instances" / "global" / "dependencies.json")

        assert meta["artifactId"] == artifact_id
        assert meta["instanceRoot"] == "../instances"
        assert index["artifactId"] == artifact_id
        assert index["kind"].endswith("GlobalIndex")
        assert export["artifactId"] == artifact_id
        assert dependencies["artifactId"] == artifact_id
        assert isinstance(dependencies["dependencies"], list)
        assert (root / "definition" / "renderer" / "index.html").is_file()
        assert (root / "instances" / "global" / "assets").is_dir()
        assert (root / "instances" / "workspaces").is_dir()


def test_acas_global_asset_main_files_are_lightweight_shard_manifests() -> None:
    for artifact_dir, asset_names in REQUIRED_SHARDED_ASSETS.items():
        assets_root = ARTIFACTS_ROOT / artifact_dir / "instances" / "global" / "assets"
        for asset_name in asset_names:
            path = assets_root / asset_name
            manifest = _load_yaml(path)
            asset_manifest = manifest.get("assetManifest")

            assert path.stat().st_size < MAIN_ASSET_MAX_BYTES, path
            assert asset_manifest["sharded"] is True, path
            assert asset_manifest["version"] == 1, path
            assert asset_manifest["fragments"], path
            load_phases = {fragment["loadPhase"] for fragment in asset_manifest["fragments"]}
            assert "initial" in load_phases, path
            if asset_name != "capability_map_current.yaml":
                assert "detail" in load_phases, path

            shard_paths = [
                shard["path"]
                for fragment in asset_manifest["fragments"]
                for shard in fragment["shards"]
            ]
            assert shard_paths, path
            for shard_path in shard_paths:
                resolved = (path.parent / shard_path).resolve()
                assert resolved.is_file(), shard_path
                assert path.parent in resolved.parents
                assert resolved.parent != path.parent


def test_acas_asset_shards_follow_business_hierarchy() -> None:
    capability_asset = (
        ARTIFACTS_ROOT
        / "capability_map_artifact"
        / "instances"
        / "global"
        / "assets"
        / "capability_map_current.yaml"
    )
    manifest = _asset_manifest(capability_asset)
    capability = _shard_paths(
        capability_asset
    )
    phases = {fragment["fragmentId"]: fragment["loadPhase"] for fragment in manifest["fragments"]}
    assert phases["capability_map_layout"] == "initial"
    assert phases["capability_map_capabilities"] == "detail"
    assert all("/capabilities/" not in path for path in capability)
    assert all("/l1/" not in path and "/l2/" not in path for path in capability)
    assert all("cap-l1-" not in path and "cap-l2-" not in path for path in capability)
    assert "capability_map_current/终端运行时编排/index.yaml" in capability
    assert "capability_map_current/终端运行时编排/窗口生命周期管理.yaml" in capability
    assert all(not path.endswith("/relationships.yaml") for path in capability)

    entity = _shard_paths(
        ARTIFACTS_ROOT
        / "entity_artifact"
        / "instances"
        / "global"
        / "assets"
        / "entity_inventory.yaml"
    )
    assert "Indexes/by_capability_map.yaml" in entity
    assert "Indexes/by_context_map.yaml" in entity
    assert "Indexes/by_api_map.yaml" in entity
    assert "Indexes/by_page_map.yaml" in entity
    assert all(not path.startswith("entity_inventory/Indexes/") for path in entity)
    assert "entity_inventory/Workspace And Project/workspace/Project.yaml" in entity
    assert "entity_inventory/Workspace And Project/workspace/Project_related_paths.yaml" in entity
    assert "entity_inventory/Workspace And Project/relationships.yaml" in entity
    assert all("/groups/" not in path and "/contexts/" not in path for path in entity)
    assert all(not path.endswith("/group.yaml") for path in entity)
    assert (
        ARTIFACTS_ROOT
        / "entity_artifact"
        / "instances"
        / "global"
        / "assets"
        / "README.md"
    ).is_file()
    assert not (
        ARTIFACTS_ROOT
        / "entity_artifact"
        / "instances"
        / "global"
        / "assets"
        / "entity_inventory"
        / "README.md"
    ).exists()

    operations = _shard_paths(
        ARTIFACTS_ROOT
        / "entity_artifact"
        / "instances"
        / "global"
        / "assets"
        / "entity_operation_groups.yaml"
    )
    assert any("/capabilities/" in path and "/operation_groups/" in path for path in operations)

    api_inventory = _shard_paths(
        ARTIFACTS_ROOT
        / "api_artifact"
        / "instances"
        / "global"
        / "assets"
        / "api_inventory.yaml"
    )
    assert any("/contexts/" in path and path.endswith("/group.yaml") for path in api_inventory)
    assert any("/contexts/" in path and path.endswith("/endpoints.yaml") for path in api_inventory)
    assert any("/contexts/" in path and path.endswith("/openapi_paths.yaml") for path in api_inventory)
    assert any("/schema/openapi_components/" in path for path in api_inventory)

    api_current = _shard_paths(
        ARTIFACTS_ROOT
        / "api_artifact"
        / "instances"
        / "global"
        / "assets"
        / "api_capability_map_current.yaml"
    )
    assert any("/contexts/" in path and path.endswith("/capability_mappings.yaml") for path in api_current)
    assert any("/capabilities/l1/" in path for path in api_current)
    assert any("/call_graph/method_sets/" in path for path in api_current)
    assert any("/call_graph/method_index/" in path and path.endswith("/001.yaml") for path in api_current)

    api_structure = _shard_paths(
        ARTIFACTS_ROOT
        / "api_artifact"
        / "instances"
        / "global"
        / "assets"
        / "api_structure.yaml"
    )
    assert "api_structure/index/by_context.yaml" in api_structure
    assert "api_structure/index/by_capability_map.yaml" in api_structure
    assert any("/contexts/" in path and path.endswith("/main.yaml") for path in api_structure)
    assert any("/contexts/" in path and path.endswith("/related_files.yaml") for path in api_structure)
    assert all("/api_get_" not in path and "/api_post_" not in path for path in api_structure)

    pages = _shard_paths(
        ARTIFACTS_ROOT
        / "page_artifact"
        / "instances"
        / "global"
        / "assets"
        / "page_wireframe_inventory.yaml"
    )
    assert any("/areas/" in path and path.endswith("/group.yaml") for path in pages)
    assert any("/areas/" in path and "/pages/" in path for path in pages)
    assert any("/trace/" in path for path in pages)


def test_capability_map_global_index_contains_summary_and_relationships() -> None:
    index = _load_json(ARTIFACTS_ROOT / "capability_map_artifact" / "instances" / "global" / "index.json")
    capability_index = index.get("capabilityIndex")

    assert isinstance(capability_index, dict)
    assert capability_index["assetId"] == "capability_map_current"
    assert capability_index["path"] == "assets/capability_map_current.yaml"
    assert capability_index["layoutTree"]["title"] == "Web Terminal ACP 能力架构"

    l1_items = capability_index.get("l1Capabilities")
    assert isinstance(l1_items, list)
    assert l1_items
    assert all({"capabilityId", "name", "description", "path", "l2Capabilities"} <= set(item) for item in l1_items)

    first = next(item for item in l1_items if item["capabilityId"] == "CAP-L1-CORE-01")
    assert first["path"] == "assets/capability_map_current/终端运行时编排/index.yaml"
    assert first["description"]
    assert first["l2Capabilities"]
    assert all({"capabilityId", "name", "description", "path"} <= set(item) for item in first["l2Capabilities"])
    assert first["l2Capabilities"][0]["path"].startswith("assets/capability_map_current/终端运行时编排/")
    assert "/l1/" not in first["path"]
    assert "cap-l1-" not in first["path"]
    assert all("/l2/" not in item["path"] for item in first["l2Capabilities"])
    assert all("cap-l2-" not in item["path"] for item in first["l2Capabilities"])

    relationships = capability_index.get("relationships")
    assert isinstance(relationships, list)
    assert relationships
    assert all({"fromCapabilityId", "toCapabilityId", "relationType", "label"} <= set(item) for item in relationships)

    assets_root = ARTIFACTS_ROOT / "capability_map_artifact" / "instances" / "global"
    detail_paths = [first["path"], *[item["path"] for item in first["l2Capabilities"]]]
    for path in detail_paths:
        loaded = yaml.safe_load((assets_root / path).read_text(encoding="utf-8"))
        assert isinstance(loaded, list)
        assert loaded[0]["capabilityId"]


def test_acas_sharded_asset_loader_reconstructs_legacy_shapes() -> None:
    loaded = {
        asset_name: load_acas_asset(
            ARTIFACTS_ROOT / artifact_dir / "instances" / "global" / "assets" / asset_name
        )
        for artifact_dir, asset_names in REQUIRED_SHARDED_ASSETS.items()
        for asset_name in asset_names
    }

    assert loaded["capability_map_current.yaml"]["capabilityMap"]["capabilities"]
    assert loaded["capability_map_current.yaml"]["capabilityMap"]["layoutModel"]["layoutTree"]
    assert loaded["entity_inventory.yaml"]["entities"]
    assert loaded["entity_inventory.yaml"]["entityRelatedPaths"]
    assert loaded["entity_inventory.yaml"]["contextIndex"]
    assert loaded["entity_inventory.yaml"]["capabilityIndex"]
    assert loaded["entity_inventory.yaml"]["apiIndex"]
    assert loaded["entity_inventory.yaml"]["pageIndex"]
    assert loaded["entity_inventory.yaml"]["entityRelationships"]
    assert loaded["entity_operation_groups.yaml"]["entityOperationGroups"]
    assert loaded["api_inventory.yaml"]["endpoints"]
    assert loaded["api_inventory.yaml"]["openapi"]["paths"]
    assert loaded["api_capability_map_current.yaml"]["apiMappings"]
    assert loaded["api_capability_map_current.yaml"]["methodIndex"]
    assert loaded["api_structure.yaml"]["contextIndex"]
    assert loaded["api_structure.yaml"]["capabilityIndex"]
    assert set(loaded["api_structure.yaml"]["contextIndex"][0]) == {"contextId", "contextName", "apis"}
    assert set(loaded["api_structure.yaml"]["capabilityIndex"][0]) == {"capabilityId", "capabilityName", "apis"}
    assert loaded["api_structure.yaml"]["apis"]
    assert loaded["api_structure.yaml"]["apiDetails"]
    assert loaded["page_wireframe_inventory.yaml"]["pages"]
    assert loaded["page_wireframe_inventory.yaml"]["pageIndex"]


def test_entity_inventory_indexes_are_lightweight_mappings() -> None:
    global_root = ARTIFACTS_ROOT / "entity_artifact" / "instances" / "global"
    index = _load_json(global_root / "index.json")
    entity_index = index["entityIndex"]

    assert entity_index["assetId"] == "entity_inventory"
    assert entity_index["path"] == "assets/entity_inventory.yaml"
    assert entity_index["contextIndexPath"] == "assets/Indexes/by_context_map.yaml"
    assert entity_index["capabilityIndexPath"] == "assets/Indexes/by_capability_map.yaml"
    assert entity_index["apiIndexPath"] == "assets/Indexes/by_api_map.yaml"
    assert entity_index["pageIndexPath"] == "assets/Indexes/by_page_map.yaml"

    context_index = yaml.safe_load((global_root / entity_index["contextIndexPath"]).read_text(encoding="utf-8"))
    capability_index = yaml.safe_load((global_root / entity_index["capabilityIndexPath"]).read_text(encoding="utf-8"))
    api_index = yaml.safe_load((global_root / entity_index["apiIndexPath"]).read_text(encoding="utf-8"))
    page_index = yaml.safe_load((global_root / entity_index["pageIndexPath"]).read_text(encoding="utf-8"))

    context = next(item for item in context_index if item["contextId"] == "workspace")
    entity = next(item for item in context["entities"] if item["entityId"] == "ENT-PROJECT")

    assert set(context) == {"contextId", "contextName", "entities"}
    assert set(entity) == {"entityName", "entityId", "targetPath", "relatedPathsPath"}
    assert entity["targetPath"] == "assets/entity_inventory/Workspace And Project/workspace/Project.yaml"
    assert entity["relatedPathsPath"] == (
        "assets/entity_inventory/Workspace And Project/workspace/Project_related_paths.yaml"
    )

    capability = next(item for item in capability_index if item["capabilityId"] == "CAP-L2-CORE-04-02")
    assert set(capability) == {"capabilityId", "capabilityName", "entities"}
    assert entity in capability["entities"]

    api = next(item for item in api_index if item["apiId"] == "api_get_api_clients_by_client_id_projects")
    assert set(api) == {"apiId", "entities"}
    assert entity in api["entities"]

    page = next(item for item in page_index if item["pageId"] == "PAGE-WORKSPACE-FILES")
    assert set(page) == {"pageId", "pageName", "entities"}
    assert entity in page["entities"]

    related = yaml.safe_load((global_root / entity["relatedPathsPath"]).read_text(encoding="utf-8"))[0]
    assert related["entityId"] == "ENT-PROJECT"
    assert related["sourceRefs"]
    assert any(item["capabilityId"] == "CAP-L2-CORE-04-02" for item in related["relatedCapabilities"])
    assert any(item["apiId"] == api["apiId"] for item in related["relatedApis"])
    assert any(item["pageId"] == page["pageId"] for item in related["relatedPages"])


def test_acas_exports_expose_referenceable_business_ids() -> None:
    capability = load_acas_asset(
        ARTIFACTS_ROOT
        / "capability_map_artifact"
        / "instances"
        / "global"
        / "assets"
        / "capability_map_current.yaml"
    )
    capability_export = _load_json(
        ARTIFACTS_ROOT / "capability_map_artifact" / "instances" / "global" / "export.json"
    )
    capability_refs = {
        ref["id"]: ref for ref in capability_export.get("references", []) if ref["kind"].startswith("capability.")
    }
    capability_ids = {
        item["capabilityId"] for item in capability["capabilityMap"]["capabilities"]
    }
    assert capability_ids <= set(capability_refs)
    assert {ref["kind"] for ref in capability_refs.values()} >= {"capability.l1", "capability.l2"}

    entity = load_acas_asset(
        ARTIFACTS_ROOT
        / "entity_artifact"
        / "instances"
        / "global"
        / "assets"
        / "entity_inventory.yaml"
    )
    entity_export = _load_json(
        ARTIFACTS_ROOT / "entity_artifact" / "instances" / "global" / "export.json"
    )
    entity_refs = {ref["id"]: ref for ref in entity_export.get("references", [])}
    assert {group["groupId"] for group in entity["entityGroups"]} <= set(entity_refs)
    assert {item["entityId"] for item in entity["entities"]} <= set(entity_refs)

    api_inventory = load_acas_asset(
        ARTIFACTS_ROOT
        / "api_artifact"
        / "instances"
        / "global"
        / "assets"
        / "api_inventory.yaml"
    )
    api_export = _load_json(
        ARTIFACTS_ROOT / "api_artifact" / "instances" / "global" / "export.json"
    )
    api_refs = {ref["id"]: ref for ref in api_export.get("references", [])}
    assert {group["groupId"] for group in api_inventory["groups"]} <= set(api_refs)
    assert {endpoint["apiId"] for endpoint in api_inventory["endpoints"]} <= set(api_refs)

    pages = load_acas_asset(
        ARTIFACTS_ROOT
        / "page_artifact"
        / "instances"
        / "global"
        / "assets"
        / "page_wireframe_inventory.yaml"
    )
    page_export = _load_json(
        ARTIFACTS_ROOT / "page_artifact" / "instances" / "global" / "export.json"
    )
    page_refs = {ref["id"]: ref for ref in page_export.get("references", [])}
    assert {group["group"] for group in pages["groups"]} <= set(page_refs)
    assert {page["pageId"] for page in _flatten_pages(pages["pages"])} <= set(page_refs)

    for export_path in (
        ARTIFACTS_ROOT / artifact_dir / "instances" / "global" / "export.json"
        for artifact_dir in REQUIRED_SHARDED_ASSETS
    ):
        export = _load_json(export_path)
        for ref in export.get("references", []):
            assert ref["id"]
            assert ref["kind"]
            assert (export_path.parent / ref["path"]).resolve().is_file(), ref


def test_acas_renderers_load_asset_shards_progressively() -> None:
    for artifact_dir in REQUIRED_SHARDED_ASSETS:
        renderer = (
            ARTIFACTS_ROOT / artifact_dir / "definition" / "renderer" / "index.html"
        ).read_text(encoding="utf-8")

        assert "loadShardedYaml" in renderer, artifact_dir
        assert "sharded_asset_loader.js" in renderer, artifact_dir
        if artifact_dir == "capability_map_artifact":
            assert "capabilityIndexPath" in renderer
            assert "ensureCapabilityDetail" in renderer
            assert "layoutTreeMarkup" in renderer
            assert "tree-zone" in renderer
            assert "detail-drawer" in renderer
            assert ".current-map-shell.simple" in renderer
            assert "optimizeZonePacking" in renderer
            assert "scheduleZonePacking" in renderer
            assert "chooseZoneColumns" in renderer
            assert "current-toolbar" in renderer
        else:
            assert "loadShardRefs" in renderer, artifact_dir


def test_acas_browser_shard_loader_supports_deep_merge_fragments() -> None:
    loader = (ARTIFACTS_ROOT / "sharded_asset_loader.js").read_text(encoding="utf-8")
    manifest = _asset_manifest(
        ARTIFACTS_ROOT
        / "api_artifact"
        / "instances"
        / "global"
        / "assets"
        / "api_inventory.yaml"
    )

    assert "deepMerge" in loader
    assert any(fragment["merge"] == "deepMerge" for fragment in manifest["fragments"])
