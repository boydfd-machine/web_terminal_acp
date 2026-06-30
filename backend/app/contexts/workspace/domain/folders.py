from __future__ import annotations

from dataclasses import dataclass

MAX_FOLDER_SEGMENT_LENGTH = 255
MAX_FOLDER_PATH_LENGTH = 1024


@dataclass(frozen=True)
class FolderPath:
    value: str
    segments: tuple[str, ...]

    @classmethod
    def parse(cls, raw_path: str) -> "FolderPath":
        stripped_path = raw_path.strip()
        if not stripped_path.startswith("/"):
            raise ValueError("folder path must be absolute")

        segments: list[str] = []
        for raw_segment in stripped_path.split("/"):
            if not raw_segment:
                continue
            if any(ord(character) < 32 or ord(character) == 127 for character in raw_segment):
                raise ValueError("folder path segments must not contain control characters")

            segment = raw_segment.strip()
            if not segment:
                continue
            if segment in {".", ".."}:
                raise ValueError("folder path must not contain . or .. segments")
            if len(segment) > MAX_FOLDER_SEGMENT_LENGTH:
                raise ValueError("folder path segment exceeds 255 characters")
            segments.append(segment)

        if not segments:
            raise ValueError("folder path must contain at least one segment")

        canonical_path = f"/{'/'.join(segments)}"
        if len(canonical_path) > MAX_FOLDER_PATH_LENGTH:
            raise ValueError("folder path exceeds 1024 characters")
        return cls(value=canonical_path, segments=tuple(segments))


def canonicalize_folder_path(path: str) -> str:
    return FolderPath.parse(path).value


def split_folder_path(path: str) -> list[str]:
    return list(FolderPath.parse(path).segments)


@dataclass(frozen=True)
class FolderProjectPathFilter:
    value: str | None

    @classmethod
    def from_query(cls, project_path: str | None) -> "FolderProjectPathFilter":
        if project_path is None:
            return cls(None)
        normalized = project_path.strip()
        return cls(normalized or None)
