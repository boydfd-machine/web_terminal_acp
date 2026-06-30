from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import UUID, uuid4

import pytest

from app.config import Settings
from app.contexts.workspace.infrastructure.project_todo_attachments_repository import (
    object_key_for_attachment,
    safe_attachment_filename,
    validate_attachment_content_type,
)
from app.contexts.workspace.infrastructure.project_todo_object_storage import ProjectTodoObjectStorage


def test_safe_attachment_filename_strips_paths_and_unsafe_characters() -> None:
    assert safe_attachment_filename(r"..\screens/ bad name @ 1.png ") == "bad-name-1.png"
    assert safe_attachment_filename("...") == "attachment"
    assert len(safe_attachment_filename("a" * 300 + ".png")) == 255


def test_validate_attachment_content_type_accepts_standard_file_types() -> None:
    assert validate_attachment_content_type("IMAGE/PNG; charset=utf-8") == "image/png"
    assert validate_attachment_content_type(" application/pdf ") == "application/pdf"
    assert validate_attachment_content_type("TEXT/PLAIN ; charset=utf-8") == "text/plain"

    with pytest.raises(ValueError, match="valid content type"):
        validate_attachment_content_type("")

    with pytest.raises(ValueError, match="valid content type"):
        validate_attachment_content_type("not-a-mime-type")


def test_validate_attachment_content_type_allows_html_and_text_types() -> None:
    assert validate_attachment_content_type("text/html") == "text/html"
    assert validate_attachment_content_type("TEXT/HTML; charset=utf-8") == "text/html"
    assert validate_attachment_content_type("application/xhtml+xml") == "application/xhtml+xml"
    assert validate_attachment_content_type("image/svg+xml") == "image/svg+xml"
    assert validate_attachment_content_type("text/markdown") == "text/markdown"
    assert validate_attachment_content_type("text/csv") == "text/csv"
    assert validate_attachment_content_type("application/json") == "application/json"
    assert validate_attachment_content_type("text/yaml") == "text/yaml"
    assert validate_attachment_content_type("application/xml") == "application/xml"


def test_object_key_for_attachment_scopes_by_client_todo_and_attachment() -> None:
    client_id = UUID("00000000-0000-0000-0000-000000000001")
    todo_id = UUID("00000000-0000-0000-0000-000000000002")
    attachment_id = UUID("00000000-0000-0000-0000-000000000003")
    todo = SimpleNamespace(client_id=client_id, id=todo_id)

    assert object_key_for_attachment(todo, attachment_id, "../screen shot.png") == (
        "project-todos/"
        "00000000-0000-0000-0000-000000000001/"
        "00000000-0000-0000-0000-000000000002/"
        "00000000-0000-0000-0000-000000000003/"
        "screen-shot.png"
    )


def test_project_todo_object_storage_presigns_upload_for_public_endpoint() -> None:
    settings = Settings(
        _env_file=None,
        project_todo_attachment_s3_endpoint_url="http://storage.example:9000",
        project_todo_attachment_s3_region="test-region",
        project_todo_attachment_s3_bucket="todo-images",
        project_todo_attachment_s3_access_key="access-key",
        project_todo_attachment_s3_secret_key="secret-key",
        project_todo_attachment_presign_ttl_seconds=600,
    )
    storage = ProjectTodoObjectStorage(settings)
    before = datetime.now(UTC)

    presigned = storage.presign_upload(f"project-todos/{uuid4()}/image one.png", content_type="image/png")

    after = datetime.now(UTC)
    url = urlsplit(presigned.url)
    query = parse_qs(url.query)
    assert url.scheme == "http"
    assert url.netloc == "storage.example:9000"
    assert unquote(url.path).startswith("/todo-images/project-todos/")
    assert unquote(url.path).endswith("/image one.png")
    assert presigned.headers == {"Content-Type": "image/png"}
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert query["X-Amz-Expires"] == ["600"]
    assert query["X-Amz-SignedHeaders"] == ["host"]
    assert query["X-Amz-Credential"][0].startswith("access-key/")
    assert "/test-region/s3/aws4_request" in query["X-Amz-Credential"][0]
    assert len(query["X-Amz-Signature"][0]) == 64
    assert before + timedelta(seconds=600) <= presigned.expires_at <= after + timedelta(seconds=600)


def test_project_todo_object_storage_presigns_upload_for_proxy_path_without_loopback_host() -> None:
    settings = Settings(
        _env_file=None,
        project_todo_attachment_s3_endpoint_url="/minio",
        project_todo_attachment_s3_internal_endpoint_url="http://minio:9000",
        project_todo_attachment_s3_region="test-region",
        project_todo_attachment_s3_bucket="todo-images",
        project_todo_attachment_s3_access_key="access-key",
        project_todo_attachment_s3_secret_key="secret-key",
    )
    storage = ProjectTodoObjectStorage(settings)

    presigned = storage.presign_upload(
        "project-todos/00000000-0000-0000-0000-000000000001/image.png",
        content_type="image/png",
    )

    url = urlsplit(presigned.url)
    assert url.scheme == ""
    assert url.netloc == ""
    assert unquote(url.path) == (
        "/minio/todo-images/project-todos/"
        "00000000-0000-0000-0000-000000000001/image.png"
    )
    assert "127.0.0.1" not in presigned.url
    assert "localhost" not in presigned.url
    assert parse_qs(url.query)["X-Amz-SignedHeaders"] == ["host"]


def test_project_todo_object_storage_uses_local_minio_for_internal_presign_when_public_endpoint_is_proxy_path() -> None:
    settings = Settings(
        _env_file=None,
        project_todo_attachment_s3_endpoint_url="/minio",
        project_todo_attachment_s3_region="test-region",
        project_todo_attachment_s3_bucket="todo-images",
        project_todo_attachment_s3_access_key="access-key",
        project_todo_attachment_s3_secret_key="secret-key",
    )
    storage = ProjectTodoObjectStorage(settings)

    presigned = storage._presign(
        "HEAD",
        "project-todos/00000000-0000-0000-0000-000000000001/image.png",
        endpoint_url=storage._internal_endpoint(),
        headers={},
    )

    url = urlsplit(presigned.url)
    assert url.scheme == "http"
    assert url.netloc == "127.0.0.1:19000"
    assert unquote(url.path) == (
        "/todo-images/project-todos/"
        "00000000-0000-0000-0000-000000000001/image.png"
    )
