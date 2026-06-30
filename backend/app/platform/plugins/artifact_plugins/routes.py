from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.platform.plugins.artifact_plugins.management import (
    ArtifactPluginDomain,
    ArtifactPluginSource,
    delete_artifact_plugin_source,
    get_artifact_plugin_source,
    list_artifact_plugin_sources,
    save_artifact_plugin_components,
    save_artifact_plugin_source,
)
from app.platform.plugins.artifact_plugins.preview import (
    render_component_preview_html,
    render_source_preview_html,
)
from app.platform.plugins.artifact_plugins.registry import reset_artifact_plugin_registries
from app.platform.plugins.artifact_plugins.schemas import (
    ArtifactPluginDescriptorOut,
    ArtifactPluginListOut,
    ArtifactPluginPutIn,
    ArtifactPluginSourceOut,
)
from app.platform.html_security import ARTIFACT_HTML_CSP, artifact_html_headers
from app.platform.plugins.artifact_plugins.user_settings_repository import (
    persist_artifact_plugin_files,
    restore_artifact_plugin_files_to_disk,
)
from app.platform.ui_events import ui_event_hub_from_state

router = APIRouter(prefix="/api/artifact-plugins", tags=["artifact-plugins"])
ARTIFACT_PLUGIN_PREVIEW_HTML_CSP = ARTIFACT_HTML_CSP


@router.get("", response_model=ArtifactPluginListOut, response_model_exclude_none=True)
async def list_artifact_plugins(
    session: AsyncSession = Depends(get_session),
) -> ArtifactPluginListOut:
    settings_home = await restore_artifact_plugin_files_to_disk(session)
    await session.commit()
    return ArtifactPluginListOut(
        plugins=[_descriptor_out(source) for source in list_artifact_plugin_sources(home=settings_home)]
    )


@router.get(
    "/{domain}/{artifact_kind}",
    response_model=ArtifactPluginSourceOut,
    response_model_exclude_none=True,
)
async def read_artifact_plugin(
    domain: ArtifactPluginDomain,
    artifact_kind: str,
    session: AsyncSession = Depends(get_session),
) -> ArtifactPluginSourceOut:
    settings_home = await restore_artifact_plugin_files_to_disk(session)
    await session.commit()
    source = _get_source_or_404(domain, artifact_kind, home=settings_home)
    return _source_out(source)


@router.get("/{domain}/{artifact_kind}/download", response_class=Response)
async def download_artifact_plugin(
    domain: ArtifactPluginDomain,
    artifact_kind: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    settings_home = await restore_artifact_plugin_files_to_disk(session)
    await session.commit()
    source = _get_source_or_404(domain, artifact_kind, home=settings_home)
    if source.plugin_format == "template":
        return Response(
            _component_bundle_json(source),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{source.artifact_kind}.json"'},
        )
    return Response(
        source.source or "",
        media_type="text/x-python; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{source.artifact_kind}.py"'},
    )


@router.get("/{domain}/{artifact_kind}/preview/html", response_class=Response)
async def preview_saved_artifact_plugin(
    domain: ArtifactPluginDomain,
    artifact_kind: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    settings_home = await restore_artifact_plugin_files_to_disk(session)
    await session.commit()
    source = _get_source_or_404(domain, artifact_kind, home=settings_home)
    try:
        html = render_source_preview_html(source)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _html_response(html)


@router.post("/{domain}/preview/html", response_class=Response)
async def preview_artifact_plugin(domain: ArtifactPluginDomain, payload: ArtifactPluginPutIn) -> Response:
    if (
        payload.python_source is None
        or payload.prompt_template is None
        or payload.html_template is None
        or payload.json_schema is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="artifact plugin components are incomplete",
        )
    try:
        html = render_component_preview_html(
            python_source=payload.python_source,
            prompt_template=payload.prompt_template,
            html_template=payload.html_template,
            json_schema=payload.json_schema,
            preview_content_json=payload.preview_content_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _html_response(html)


@router.post(
    "/{domain}",
    response_model=ArtifactPluginSourceOut,
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_none=True,
)
async def create_artifact_plugin(
    domain: ArtifactPluginDomain,
    payload: ArtifactPluginPutIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ArtifactPluginSourceOut:
    settings_home = await restore_artifact_plugin_files_to_disk(session)
    try:
        source = _save_payload(domain, payload, allow_overwrite=False, home=settings_home)
    except FileExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await persist_artifact_plugin_files(session, home=settings_home)
    await session.commit()
    reset_artifact_plugin_registries()
    await _publish_artifact_plugin_invalidation(request, "artifact_plugin_created")
    return _source_out(source)


@router.put(
    "/{domain}/{artifact_kind}",
    response_model=ArtifactPluginSourceOut,
    response_model_exclude_none=True,
)
async def update_artifact_plugin(
    domain: ArtifactPluginDomain,
    artifact_kind: str,
    payload: ArtifactPluginPutIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ArtifactPluginSourceOut:
    settings_home = await restore_artifact_plugin_files_to_disk(session)
    try:
        source = _save_payload(
            domain,
            payload,
            expected_artifact_kind=artifact_kind,
            allow_overwrite=True,
            require_existing=True,
            home=settings_home,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await persist_artifact_plugin_files(session, home=settings_home)
    await session.commit()
    reset_artifact_plugin_registries()
    await _publish_artifact_plugin_invalidation(request, "artifact_plugin_updated")
    return _source_out(source)


@router.delete("/{domain}/{artifact_kind}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artifact_plugin(
    domain: ArtifactPluginDomain,
    artifact_kind: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    settings_home = await restore_artifact_plugin_files_to_disk(session)
    try:
        delete_artifact_plugin_source(domain, artifact_kind, home=settings_home)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await persist_artifact_plugin_files(session, home=settings_home)
    await session.commit()
    reset_artifact_plugin_registries()
    await _publish_artifact_plugin_invalidation(request, "artifact_plugin_deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _get_source_or_404(
    domain: ArtifactPluginDomain,
    artifact_kind: str,
    *,
    home: Path | None = None,
) -> ArtifactPluginSource:
    try:
        return get_artifact_plugin_source(domain, artifact_kind, home=home)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _descriptor_out(source: ArtifactPluginSource) -> ArtifactPluginDescriptorOut:
    return ArtifactPluginDescriptorOut(
        domain=source.domain,
        artifact_kind=source.artifact_kind,
        label=source.label,
        default_title=source.default_title,
        origin=source.origin,
        editable=source.editable,
        plugin_format=source.plugin_format,
        path=str(source.path) if source.path is not None else None,
        validation_error=source.validation_error,
    )


def _source_out(source: ArtifactPluginSource) -> ArtifactPluginSourceOut:
    return ArtifactPluginSourceOut(
        **_descriptor_out(source).model_dump(),
        source=source.source,
        python_source=source.python_source,
        prompt_template=source.prompt_template,
        html_template=source.html_template,
        json_schema=source.json_schema,
        preview_content_json=source.preview_content_json,
        preview_content_json_by_locale=source.preview_content_json_by_locale,
    )


def _save_payload(
    domain: ArtifactPluginDomain,
    payload: ArtifactPluginPutIn,
    *,
    expected_artifact_kind: str | None = None,
    allow_overwrite: bool,
    require_existing: bool = False,
    home: Path | None = None,
) -> ArtifactPluginSource:
    if payload.source is not None and payload.python_source is None:
        return save_artifact_plugin_source(
            domain,
            payload.source,
            expected_artifact_kind=expected_artifact_kind,
            allow_overwrite=allow_overwrite,
            require_existing=require_existing,
            home=home,
        )
    if (
        payload.python_source is None
        or payload.prompt_template is None
        or payload.html_template is None
        or payload.json_schema is None
    ):
        raise ValueError("artifact plugin components are incomplete")
    return save_artifact_plugin_components(
        domain,
        python_source=payload.python_source,
        prompt_template=payload.prompt_template,
        html_template=payload.html_template,
        json_schema=payload.json_schema,
        preview_content_json=payload.preview_content_json,
        expected_artifact_kind=expected_artifact_kind,
        allow_overwrite=allow_overwrite,
        require_existing=require_existing,
        home=home,
    )


def _component_bundle_json(source: ArtifactPluginSource) -> str:
    return ArtifactPluginSourceOut(
        **_source_out(source).model_dump(),
    ).model_dump_json(indent=2)


def _html_response(html: str) -> Response:
    return Response(
        html,
        media_type="text/html; charset=utf-8",
        headers=artifact_html_headers(),
    )


async def _publish_artifact_plugin_invalidation(request: Request, reason: str) -> None:
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["artifact_plugins"],
        reason=reason,
    )
