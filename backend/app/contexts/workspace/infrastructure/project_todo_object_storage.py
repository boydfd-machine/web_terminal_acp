from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import SplitResult, quote, urlencode, urlsplit, urlunsplit

import httpx

from app.config import Settings, get_settings

DEFAULT_LOCAL_MINIO_ENDPOINT = "http://127.0.0.1:19000"


@dataclass(frozen=True)
class PresignedObjectUrl:
    url: str
    expires_at: datetime
    headers: dict[str, str]


@dataclass(frozen=True)
class _EndpointParts:
    public_parts: SplitResult
    signing_parts: SplitResult


class ProjectTodoObjectStorage:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def presign_upload(self, object_key: str, *, content_type: str) -> PresignedObjectUrl:
        headers = {"Content-Type": content_type}
        return self._presign("PUT", object_key, endpoint_url=self._public_endpoint(), headers=headers)

    def presign_download(self, object_key: str) -> PresignedObjectUrl:
        return self._presign("GET", object_key, endpoint_url=self._public_endpoint(), headers={})

    async def object_head(self, object_key: str) -> httpx.Headers:
        presigned = self._presign("HEAD", object_key, endpoint_url=self._internal_endpoint(), headers={})
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.head(presigned.url, headers=presigned.headers)
        response.raise_for_status()
        return response.headers

    async def read_object(self, object_key: str) -> bytes:
        presigned = self._presign("GET", object_key, endpoint_url=self._internal_endpoint(), headers={})
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(presigned.url, headers=presigned.headers)
        response.raise_for_status()
        return response.content

    async def delete_object(self, object_key: str) -> None:
        presigned = self._presign("DELETE", object_key, endpoint_url=self._internal_endpoint(), headers={})
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.delete(presigned.url, headers=presigned.headers)
        if response.status_code not in {200, 202, 204, 404}:
            response.raise_for_status()

    def _public_endpoint(self) -> str:
        return self._settings.project_todo_attachment_s3_endpoint_url

    def _internal_endpoint(self) -> str:
        if self._settings.project_todo_attachment_s3_internal_endpoint_url:
            return self._settings.project_todo_attachment_s3_internal_endpoint_url
        public_parts = urlsplit(self._settings.project_todo_attachment_s3_endpoint_url)
        if public_parts.scheme and public_parts.netloc:
            return self._settings.project_todo_attachment_s3_endpoint_url
        return DEFAULT_LOCAL_MINIO_ENDPOINT

    def _presign(
        self,
        method: str,
        object_key: str,
        *,
        endpoint_url: str,
        headers: dict[str, str],
    ) -> PresignedObjectUrl:
        now = datetime.now(UTC)
        expires = int(self._settings.project_todo_attachment_presign_ttl_seconds)
        expires_at = now + timedelta(seconds=expires)
        endpoint = self._endpoint_parts(endpoint_url)
        host = endpoint.signing_parts.netloc
        bucket = self._settings.project_todo_attachment_s3_bucket
        canonical_uri = "/" + "/".join(
            quote(part, safe="")
            for part in [bucket, *object_key.split("/")]
        )
        credential_scope = f"{now:%Y%m%d}/{self._settings.project_todo_attachment_s3_region}/s3/aws4_request"
        query = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self._settings.project_todo_attachment_s3_access_key}/{credential_scope}",
            "X-Amz-Date": f"{now:%Y%m%dT%H%M%SZ}",
            "X-Amz-Expires": str(expires),
            "X-Amz-SignedHeaders": "host",
        }
        canonical_query = urlencode(sorted(query.items()), quote_via=quote, safe="-_.~")
        canonical_request = "\n".join(
            [
                method,
                canonical_uri,
                canonical_query,
                f"host:{host}\n",
                "host",
                "UNSIGNED-PAYLOAD",
            ]
        )
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                query["X-Amz-Date"],
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            _signing_key(
                self._settings.project_todo_attachment_s3_secret_key,
                f"{now:%Y%m%d}",
                self._settings.project_todo_attachment_s3_region,
            ),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        query["X-Amz-Signature"] = signature
        final_query = urlencode(sorted(query.items()), quote_via=quote, safe="-_.~")
        public_uri = _join_url_path(endpoint.public_parts.path, canonical_uri)
        return PresignedObjectUrl(
            url=urlunsplit(
                (
                    endpoint.public_parts.scheme,
                    endpoint.public_parts.netloc,
                    public_uri,
                    final_query,
                    "",
                )
            ),
            expires_at=expires_at,
            headers=headers,
        )

    def _endpoint_parts(self, endpoint_url: str) -> _EndpointParts:
        public_parts = urlsplit(endpoint_url.rstrip("/"))
        if public_parts.scheme and public_parts.netloc:
            return _EndpointParts(public_parts=public_parts, signing_parts=public_parts)

        signing_parts = urlsplit(self._internal_endpoint().rstrip("/"))
        return _EndpointParts(public_parts=public_parts, signing_parts=signing_parts)


def _signing_key(secret_key: str, date: str, region: str) -> bytes:
    key = hmac.new(f"AWS4{secret_key}".encode("utf-8"), date.encode("utf-8"), hashlib.sha256).digest()
    key = hmac.new(key, region.encode("utf-8"), hashlib.sha256).digest()
    key = hmac.new(key, b"s3", hashlib.sha256).digest()
    return hmac.new(key, b"aws4_request", hashlib.sha256).digest()


def _join_url_path(prefix: str, path: str) -> str:
    normalized_prefix = prefix.rstrip("/")
    if not normalized_prefix:
        return path
    return f"{normalized_prefix}/{path.lstrip('/')}"
