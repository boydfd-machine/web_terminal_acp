from __future__ import annotations

import json
from pathlib import Path
import sys

import yaml
from fastapi.routing import APIRoute, APIWebSocketRoute

from app.main import app


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS_ROOT = REPO_ROOT / "artifacts"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from acas_sharded_assets import load_acas_asset  # noqa: E402

CAPABILITY_ASSETS = ARTIFACTS_ROOT / "capability_map_artifact" / "instances" / "global" / "assets"
API_ARTIFACT = ARTIFACTS_ROOT / "api_artifact"
API_ASSETS = API_ARTIFACT / "instances" / "global" / "assets"
API_RENDERER_PATH = API_ARTIFACT / "definition" / "renderer" / "index.html"


def _load_yaml(path: Path) -> dict:
    loaded = load_acas_asset(path)
    assert isinstance(loaded, dict)
    return loaded


def _load_json(path: Path) -> dict:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _registered_route_keys() -> set[str]:
    keys: set[str] = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in sorted((route.methods or set()) - {"HEAD", "OPTIONS"}):
                keys.add(f"{method} {route.path}")
        elif isinstance(route, APIWebSocketRoute):
            keys.add(f"WEBSOCKET {route.path}")
    return keys


def test_acas_api_inventory_matches_registered_fastapi_routes():
    inventory = _load_yaml(API_ASSETS / "api_inventory.yaml")
    endpoint_keys = {endpoint["key"] for endpoint in inventory["endpoints"]}

    assert inventory["kind"] == "ApiInventory"
    assert endpoint_keys == _registered_route_keys()
    assert inventory["summary"]["totalEndpoints"] == len(endpoint_keys)
    assert "openapi" in inventory
    assert inventory["openapi"]["paths"]


def test_acas_api_capability_map_covers_every_inventory_endpoint_and_file():
    inventory = _load_yaml(API_ASSETS / "api_inventory.yaml")
    current = _load_yaml(API_ASSETS / "api_capability_map_current.yaml")
    capability_map = _load_yaml(CAPABILITY_ASSETS / "capability_map_current.yaml")

    endpoint_ids = {endpoint["apiId"] for endpoint in inventory["endpoints"]}
    mapped_ids = {mapping["apiId"] for mapping in current["apiMappings"]}
    capability_ids = {
        capability["capabilityId"]
        for capability in capability_map["capabilityMap"]["capabilities"]
    }

    assert current["kind"] == "ApiCapabilityMapCurrent"
    assert mapped_ids == endpoint_ids
    file_sets = {file_set["fileSetId"]: file_set for file_set in current["fileSets"]}
    for mapping in current["apiMappings"]:
        assert mapping["capabilityIds"]
        assert set(mapping["capabilityIds"]).issubset(capability_ids)
        entrypoint = mapping["relatedFiles"]["entrypoint"]
        file_set = file_sets[mapping["relatedFiles"]["fileSetId"]]
        assert entrypoint in file_set["files"]
        assert mapping["relatedFiles"]["fileCount"] == len(file_set["files"])
        for file_path in file_set["files"]:
            assert (REPO_ROOT / file_path).exists(), file_path


def test_acas_api_structure_splits_api_l1_and_l2_under_context_api_dirs():
    manifest = yaml.safe_load((API_ASSETS / "api_structure.yaml").read_text(encoding="utf-8"))
    index = _load_json(API_ARTIFACT / "instances" / "global" / "index.json")
    global_root = API_ARTIFACT / "instances" / "global"
    context_index = yaml.safe_load((global_root / index["apiIndex"]["contextIndexPath"]).read_text(encoding="utf-8"))
    context = next(
        item for item in context_index if item["contextId"] == "agent-profiles"
    )
    api = next(item for item in context["apis"] if item["apiName"] == "GET /api/agent-profiles/{profile_id}")

    main_path = global_root / api["mainPath"]
    related_path = global_root / api["relatedFilesPath"]
    main = yaml.safe_load(main_path.read_text(encoding="utf-8"))[0]
    detail = yaml.safe_load(related_path.read_text(encoding="utf-8"))[0]

    assert manifest["kind"] == "ApiStructureCurrent"
    assert manifest["assetManifest"]["fragmentRoot"] == "./api_structure/"
    assert main["context"]["contextId"] == "agent-profiles"
    assert main["contract"]["responses"]
    assert main["contract"]["errorResponses"]
    assert main["paths"]["main"].endswith("/main.yaml")
    assert main["paths"]["relatedFiles"].endswith("/related_files.yaml")
    assert "/api_get_" not in main["paths"]["main"]
    assert detail["relatedFiles"]["entrypoint"] == main["source"]["file"]
    assert main["source"]["file"] in detail["relatedFiles"]["files"]
    assert detail["relatedMethods"]["methods"]
    assert detail["paths"] == main["paths"]
    assert main_path.is_file()
    assert related_path.is_file()
    assert main["name"] == api["apiName"]
    assert detail["name"] == api["apiName"]


def test_acas_api_global_index_exposes_lightweight_index_paths():
    index = _load_json(API_ARTIFACT / "instances" / "global" / "index.json")
    api_index = index["apiIndex"]

    assert api_index["assetId"] == "api_structure"
    assert api_index["path"] == "assets/api_structure.yaml"
    assert api_index["summary"]["totalApis"] > 0
    assert api_index["contextIndexPath"] == "assets/api_structure/index/by_context.yaml"
    assert api_index["capabilityIndexPath"] == "assets/api_structure/index/by_capability_map.yaml"
    assert "contextIndex" not in api_index
    assert "capabilityIndex" not in api_index


def test_acas_api_structure_indexes_are_lightweight_mappings():
    global_root = API_ARTIFACT / "instances" / "global"
    index = _load_json(global_root / "index.json")
    context_index = yaml.safe_load((global_root / index["apiIndex"]["contextIndexPath"]).read_text(encoding="utf-8"))
    capability_index = yaml.safe_load((global_root / index["apiIndex"]["capabilityIndexPath"]).read_text(encoding="utf-8"))

    context = next(item for item in context_index if item["contextId"] == "agent-profiles")
    api = next(item for item in context["apis"] if item["apiName"] == "GET /api/agent-profiles/{profile_id}")

    assert set(context) == {"contextId", "contextName", "apis"}
    assert set(api) == {"apiName", "mainPath", "relatedFilesPath"}
    assert api["mainPath"].endswith("/main.yaml")
    assert api["relatedFilesPath"].endswith("/related_files.yaml")

    capability = next(
        item
        for item in capability_index
        if item["capabilityId"] == "CAP-L2-CORE-03-02"
    )
    capability_api = next(
        item for item in capability["apis"] if item["apiName"] == "GET /api/agent-profiles/{profile_id}"
    )
    assert set(capability) == {"capabilityId", "capabilityName", "apis"}
    assert set(capability_api) == {"apiName", "mainPath", "relatedFilesPath"}
    assert capability_api == api
    assert all("description" not in item for item in context["apis"])
    assert all("capabilityIds" not in item for item in context["apis"])


def test_acas_api_renderer_exposes_required_tabs_and_cross_filters():
    renderer = API_RENDERER_PATH.read_text(encoding="utf-8")

    assert "data-tab=\"openapi\"" in renderer
    assert "data-tab=\"endpoints\"" in renderer
    assert "data-tab=\"capability-links\"" in renderer
    assert "ensureOpenApiDetails" in renderer
    assert "openapiDetailLoaded" in renderer
    assert "openapi_paths" in renderer
    assert "swagger-ui-dist@5/swagger-ui.css" in renderer
    assert "swagger-ui-dist@5/swagger-ui-bundle.js" in renderer
    assert "SwaggerUIBundle" in renderer
    assert "prepareOpenApiSpec" in renderer
    assert "openApiGroupTags" in renderer
    assert 'tagsSorter:"alpha"' in renderer
    assert 'operationsSorter:"alpha"' in renderer
    assert "openApiApiId" in renderer
    assert "ensureCapabilityMap" in renderer
    assert "apiInventoryPath" in renderer
    assert "apiCurrentPath" in renderer
    assert "data-resizer" in renderer
    assert "selectCapability" in renderer
    assert "selectApi" in renderer
    assert "selectFile" in renderer
    assert "methodSets" in renderer
    assert "methodIndex" in renderer
    assert "methodList" in renderer


def test_acas_api_renderer_places_method_call_tree_in_file_panel_and_cross_highlights():
    renderer = API_RENDERER_PATH.read_text(encoding="utf-8")

    assert "methodCallPanel" in renderer
    assert "methodCallDag" in renderer
    assert "methodDagSvg" in renderer
    assert "methodDagEdge" in renderer
    assert "methodDagNode" in renderer
    assert "methodPathCount" in renderer
    assert "methodFocusClass" in renderer
    assert "selectedMethodIds" in renderer
    assert "selectMethod" in renderer
    assert "data-method" in renderer
    assert "data-method-file" in renderer
    assert "selectedCapabilityIds" in renderer
    assert "activeCapabilityIds" in renderer
    assert "allCapabilityIds" in renderer
    assert "selectedMethodIds(idx)" in renderer
    assert 'S.selectedKind==="file"' in renderer
    assert 'S.selectedKind==="api")mappingMethods' not in renderer
    assert "methodCallPanel(idx,files,methods)+fileList(idx,files)+methodList(idx,apiIds)" in renderer
    assert ".method-dag-svg{display:block;width:100%;max-width:100%" in renderer
    assert "data-api=\"'+esc(m.apiId)+'\"" in renderer
    assert 'block.setAttribute("data-api",apiId)' in renderer
    assert "methodPanelApis" in renderer
    assert "api.relatedMethods?.entrypoint" in renderer
    assert "const queue=[...roots]" in renderer
    assert "levels[child]" in renderer
    assert "methodFocusRank" in renderer
    assert ".method-dag-node.support" in renderer
    assert ".method-dag-edge.support" in renderer
    assert "auth_context" in renderer
    assert "keycloak" in renderer
    assert "cache_backend" in renderer


def test_agent_profile_apis_map_to_agent_configuration_capabilities():
    current = _load_yaml(API_ASSETS / "api_capability_map_current.yaml")
    mappings = [
        mapping
        for mapping in current["apiMappings"]
        if mapping["group"] == "agent-profiles"
    ]

    assert mappings
    for mapping in mappings:
        assert "CAP-L1-FOUND-01" not in mapping["capabilityIds"]
        assert any(
            capability_id.startswith("CAP-L2-CORE-03-")
            for capability_id in mapping["capabilityIds"]
        )


def test_acas_api_related_files_do_not_over_expand_to_client_agent_shell_hooks():
    current = _load_yaml(API_ASSETS / "api_capability_map_current.yaml")
    file_sets = {file_set["fileSetId"]: file_set for file_set in current["fileSets"]}
    zsh_hook_file = "backend/app/client_agent/shell_hook/zsh_hooks.py"

    mapped_keys = [
        mapping["key"]
        for mapping in current["apiMappings"]
        if zsh_hook_file in file_sets[mapping["relatedFiles"]["fileSetId"]]["files"]
    ]

    assert len(mapped_keys) <= 5
    assert not any(key.startswith("GET /api/agent-profiles") for key in mapped_keys)


def test_acas_api_related_methods_trace_endpoint_call_graph():
    current = _load_yaml(API_ASSETS / "api_capability_map_current.yaml")
    method_sets = {method_set["methodSetId"]: method_set for method_set in current["methodSets"]}
    method_index = {method["methodId"]: method for method in current["methodIndex"]}
    file_sets = {file_set["fileSetId"]: file_set for file_set in current["fileSets"]}
    mapping = next(
        item
        for item in current["apiMappings"]
        if item["key"] == "GET /api/agent-profiles"
    )
    method_set = method_sets[mapping["relatedMethods"]["methodSetId"]]
    method_ids = set(method_set["methodIds"])

    assert "app.contexts.agent_profiles.api.routes.read_agent_profiles" in method_ids
    assert "app.contexts.agent_profiles.api.routes._service" in method_ids
    assert "app.contexts.agent_profiles.application.api_service.AgentProfileApiService.list_profiles" in method_ids
    assert method_ids.issubset(method_index)
    assert mapping["relatedMethods"]["methodCount"] == len(method_set["methodIds"])

    files = set(file_sets[mapping["relatedFiles"]["fileSetId"]]["files"])
    assert "backend/app/contexts/agent_profiles/api/routes.py" in files
    assert "backend/app/contexts/agent_profiles/application/api_service.py" in files
    assert "backend/app/contexts/terminal_runtime/infrastructure/tmux_manager.py" not in files


def test_acas_api_related_methods_trace_agent_preview_service_chain():
    current = _load_yaml(API_ASSETS / "api_capability_map_current.yaml")
    method_sets = {method_set["methodSetId"]: method_set for method_set in current["methodSets"]}
    method_index = {method["methodId"]: method for method in current["methodIndex"]}
    file_sets = {file_set["fileSetId"]: file_set for file_set in current["fileSets"]}
    mapping = next(
        item
        for item in current["apiMappings"]
        if item["key"] == "GET /api/agent-ops/clients/{client_id}/windows/{window_id}/agent-preview"
    )
    method_set = method_sets[mapping["relatedMethods"]["methodSetId"]]
    method_ids = set(method_set["methodIds"])

    assert "app.contexts.mcp_acp.api.routes.agent_ops_read_agent_preview" in method_ids
    assert "app.contexts.mcp_acp.api.routes._service" in method_ids
    assert "app.contexts.mcp_acp.application.source_ops_service.McpSourceOpsMixin.read_agent_preview" in method_ids
    assert "app.contexts.mcp_acp.application.service.McpAcpService._require_window" in method_ids
    assert "app.contexts.mcp_acp.application.source_ops_reads.read_agent_preview" in method_ids
    assert "app.contexts.mcp_acp.application.source_ops_reads._agent_preview_detail" in method_ids
    assert "app.contexts.windows.infrastructure.repository.get_window_for_client" in method_ids
    assert "app.contexts.windows.application.agent_record_projection.load_compact_agent_chat_messages" in method_ids
    assert method_ids.issubset(method_index)
    assert {
        (
            "app.contexts.mcp_acp.api.routes.agent_ops_read_agent_preview",
            "app.contexts.mcp_acp.application.source_ops_service.McpSourceOpsMixin.read_agent_preview",
        ),
        (
            "app.contexts.mcp_acp.application.source_ops_service.McpSourceOpsMixin.read_agent_preview",
            "app.contexts.mcp_acp.application.source_ops_reads.read_agent_preview",
        ),
    }.issubset({(edge["from"], edge["to"]) for edge in method_set["callEdges"]})

    files = set(file_sets[mapping["relatedFiles"]["fileSetId"]]["files"])
    assert "backend/app/contexts/mcp_acp/application/source_ops_service.py" in files
    assert "backend/app/contexts/mcp_acp/application/source_ops_reads.py" in files
    assert "backend/app/contexts/windows/application/agent_record_projection.py" in files
    assert "backend/app/contexts/windows/infrastructure/repository.py" in files
