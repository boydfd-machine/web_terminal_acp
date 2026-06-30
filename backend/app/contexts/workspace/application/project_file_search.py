from __future__ import annotations

import posixpath
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_runtime.application.broker import TerminalRuntimeUnavailable
from app.contexts.terminal_runtime.application.runtime_provider import RemoteClientUnavailable
from app.contexts.terminal_runtime.domain.types import RuntimeFileEntry
from app.contexts.workspace.application.project_files import (
    ProjectPathError,
    normalize_project_path,
    relative_path_from_project,
)
from app.contexts.workspace.application.project_queries import list_terminal_projects
from app.contexts.terminal_runtime.application.git_worktree_queries import (
    list_client_git_bindings_for_project_root,
)

MAX_SEARCH_FILE_BYTES = 256 * 1024
MAX_SEARCHED_FILES = 1000
MAX_DIRECTORY_VISITS = 500
MAX_MATCHES_PER_FILE = 5
MAX_TOTAL_MATCHES = 500
MAX_SNIPPET_CHARS = 240
ProjectFileSearchMode = Literal["all", "content", "filename"]
SKIPPED_DIRECTORY_NAMES = {
    ".cache",
    ".git",
    ".hg",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    ".worktrees",
    ".web-terminal-acp",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "venv",
}


class ProjectFileSearchRuntime:
    async def list_file_entries(self, client_id: UUID, path: str) -> list[RuntimeFileEntry]:
        raise NotImplementedError

    async def read_file_bytes(self, client_id: UUID, path: str, *, max_bytes: int | None = None) -> bytes:
        raise NotImplementedError


@dataclass
class ProjectFileSearchMatch:
    field: str
    start: int
    end: int


@dataclass
class ProjectFileSearchResult:
    project_path: str
    path: str
    line: int | None
    snippet: str
    matches: list[ProjectFileSearchMatch]


@dataclass
class ProjectFileSearchPage:
    query: str
    results: list[ProjectFileSearchResult]
    total: int
    limit: int
    offset: int
    has_more: bool
    scanned_files: int
    truncated: bool


@dataclass
class _SearchState:
    query: str
    mode: ProjectFileSearchMode
    limit: int
    offset: int
    matches_seen: int = 0
    scanned_files: int = 0
    visited_directories: int = 0
    truncated: bool = False


@dataclass
class _ProjectSearchRoot:
    main_root: str
    worktree_roots: set[str]
    skip_if_root_is_worktree: bool = False


async def search_project_files(
    session: AsyncSession,
    runtime: ProjectFileSearchRuntime,
    *,
    client_id: UUID,
    query: str,
    mode: ProjectFileSearchMode = "all",
    project_path: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> ProjectFileSearchPage:
    normalized_query = query.strip()
    if not normalized_query:
        return ProjectFileSearchPage(
            query=normalized_query,
            results=[],
            total=0,
            limit=limit,
            offset=offset,
            has_more=False,
            scanned_files=0,
            truncated=False,
        )

    project_roots = await _search_project_roots(session, client_id, project_path)
    state = _SearchState(
        query=normalized_query,
        mode=mode,
        limit=limit,
        offset=offset,
    )
    results: list[ProjectFileSearchResult] = []
    for root in project_roots:
        await _search_project_root(runtime, client_id, root, state, results)
        if _should_stop_search(state):
            break

    return ProjectFileSearchPage(
        query=normalized_query,
        results=results,
        total=state.matches_seen,
        limit=limit,
        offset=offset,
        has_more=state.matches_seen > offset + len(results) or state.truncated,
        scanned_files=state.scanned_files,
        truncated=state.truncated,
    )


async def _search_project_roots(
    session: AsyncSession,
    client_id: UUID,
    project_path: str | None,
) -> list[_ProjectSearchRoot]:
    if project_path is not None:
        return [
            await _canonical_project_search_root(
                session,
                client_id,
                normalize_project_path(project_path),
                explicit=True,
            )
        ]

    roots: dict[str, _ProjectSearchRoot] = {}
    for project in await list_terminal_projects(session, client_id, visible_since=None):
        try:
            root = await _canonical_project_search_root(session, client_id, project.project_path)
        except ProjectPathError:
            continue
        existing = roots.get(root.main_root)
        if existing is None:
            roots[root.main_root] = root
        else:
            existing.worktree_roots.update(root.worktree_roots)
    return list(roots.values())


async def _canonical_project_search_root(
    session: AsyncSession,
    client_id: UUID,
    root: str,
    *,
    explicit: bool = False,
) -> _ProjectSearchRoot:
    normalized_root = normalize_project_path(root)
    bindings = await list_client_git_bindings_for_project_root(session, client_id, normalized_root)
    main_root = next(
        (
            binding.main_repo_root
            for binding in bindings
            if normalized_root in {binding.main_repo_root, binding.worktree_root}
        ),
        normalized_root,
    )
    worktree_roots = {
        normalize_project_path(binding.worktree_root)
        for binding in bindings
        if binding.main_repo_root == main_root and binding.worktree_root != main_root
    }
    return _ProjectSearchRoot(
        main_root=main_root,
        worktree_roots=worktree_roots,
        skip_if_root_is_worktree=not explicit and main_root == normalized_root,
    )


async def _search_project_root(
    runtime: ProjectFileSearchRuntime,
    client_id: UUID,
    root: _ProjectSearchRoot,
    state: _SearchState,
    results: list[ProjectFileSearchResult],
) -> None:
    project_root = root.main_root
    pending_dirs = [project_root]
    while pending_dirs and not _should_stop_search(state):
        directory = pending_dirs.pop(0)
        state.visited_directories += 1
        if state.visited_directories > MAX_DIRECTORY_VISITS:
            state.truncated = True
            return

        try:
            entries = await runtime.list_file_entries(client_id, directory)
        except (RemoteClientUnavailable, TerminalRuntimeUnavailable):
            raise
        except Exception:
            continue

        if (directory != project_root or root.skip_if_root_is_worktree) and _entries_indicate_nested_git_checkout(entries):
            continue

        for entry in entries:
            if entry.kind == "directory":
                if _should_search_directory(entry, root.worktree_roots):
                    pending_dirs.append(entry.path)
                continue
            if entry.kind != "file":
                continue
            state.scanned_files += 1
            if state.scanned_files > MAX_SEARCHED_FILES:
                state.truncated = True
                return
            relative_path = relative_path_from_project(project_root, entry.path)
            path_match_count = 0
            if _should_search_filename(state):
                path_match_count = _search_file_path(project_root, relative_path, state, results)
            if _should_stop_search(state):
                return
            if not _should_search_content(state) or not _should_search_file(entry):
                continue
            await _search_file(
                runtime,
                client_id,
                project_root,
                relative_path,
                entry,
                state,
                results,
                existing_match_count=path_match_count,
            )
            if _should_stop_search(state):
                return


def _should_stop_search(state: _SearchState) -> bool:
    return state.matches_seen >= state.offset + state.limit + 1 or state.matches_seen >= MAX_TOTAL_MATCHES


def _should_search_directory(
    entry: RuntimeFileEntry,
    worktree_roots: set[str],
) -> bool:
    return not _should_skip_directory(entry.name) and not _is_under_any_root(entry.path, worktree_roots)


def _should_skip_directory(name: str) -> bool:
    return name in SKIPPED_DIRECTORY_NAMES


def _entries_indicate_nested_git_checkout(entries: list[RuntimeFileEntry]) -> bool:
    return any(entry.name == ".git" and entry.kind == "file" for entry in entries)


def _should_search_filename(state: _SearchState) -> bool:
    return state.mode in {"all", "filename"}


def _should_search_content(state: _SearchState) -> bool:
    return state.mode in {"all", "content"}


def _is_under_any_root(path: str, roots: set[str]) -> bool:
    normalized = posixpath.normpath(path)
    return any(normalized == root or normalized.startswith(f"{root}/") for root in roots)


def _should_search_file(entry: RuntimeFileEntry) -> bool:
    return entry.size is None or entry.size <= MAX_SEARCH_FILE_BYTES


def _search_file_path(
    project_root: str,
    relative_path: str,
    state: _SearchState,
    results: list[ProjectFileSearchResult],
) -> int:
    path_matches = _matches_for_text(relative_path, state.query, field="path")
    if not path_matches:
        return 0
    _append_match(
        state,
        results,
        ProjectFileSearchResult(
            project_path=project_root,
            path=relative_path,
            line=None,
            snippet=relative_path,
            matches=path_matches,
        ),
    )
    return 1


async def _search_file(
    runtime: ProjectFileSearchRuntime,
    client_id: UUID,
    project_root: str,
    relative_path: str,
    entry: RuntimeFileEntry,
    state: _SearchState,
    results: list[ProjectFileSearchResult],
    *,
    existing_match_count: int = 0,
) -> None:
    try:
        data = await runtime.read_file_bytes(client_id, entry.path, max_bytes=MAX_SEARCH_FILE_BYTES)
    except (RemoteClientUnavailable, TerminalRuntimeUnavailable):
        raise
    except Exception:
        return
    if len(data) > MAX_SEARCH_FILE_BYTES:
        state.truncated = True
        data = data[:MAX_SEARCH_FILE_BYTES]
    if _looks_binary(data):
        return
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return

    lines = text.splitlines()
    file_match_count = existing_match_count
    for line_index, line in enumerate(lines, start=1):
        snippet_matches = _matches_for_text(line, state.query, field="snippet")
        if not snippet_matches:
            continue
        snippet, adjusted_matches = _snippet_for_line(line, snippet_matches)
        _append_match(
            state,
            results,
            ProjectFileSearchResult(
                project_path=project_root,
                path=relative_path,
                line=line_index,
                snippet=snippet,
                matches=adjusted_matches,
            ),
        )
        file_match_count += 1
        if _should_stop_search(state):
            return
        if file_match_count >= MAX_MATCHES_PER_FILE:
            return


def _append_match(
    state: _SearchState,
    results: list[ProjectFileSearchResult],
    result: ProjectFileSearchResult,
) -> None:
    state.matches_seen += 1
    if state.matches_seen <= state.offset:
        return
    if len(results) < state.limit:
        results.append(result)


def _matches_for_text(text: str, query: str, *, field: str) -> list[ProjectFileSearchMatch]:
    lowered_text = text.lower()
    lowered_query = query.lower()
    matches: list[ProjectFileSearchMatch] = []
    start = 0
    while len(matches) < 20:
        index = lowered_text.find(lowered_query, start)
        if index < 0:
            break
        matches.append(ProjectFileSearchMatch(field=field, start=index, end=index + len(query)))
        start = index + max(len(query), 1)
    return matches


def _snippet_for_line(
    line: str,
    matches: list[ProjectFileSearchMatch],
) -> tuple[str, list[ProjectFileSearchMatch]]:
    if len(line) <= MAX_SNIPPET_CHARS:
        return line, matches
    first_match = matches[0]
    half_width = MAX_SNIPPET_CHARS // 2
    start = max(0, first_match.start - half_width)
    end = min(len(line), start + MAX_SNIPPET_CHARS)
    start = max(0, end - MAX_SNIPPET_CHARS)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(line) else ""
    snippet = f"{prefix}{line[start:end]}{suffix}"
    offset = start - len(prefix)
    adjusted = [
        ProjectFileSearchMatch(
            field=match.field,
            start=max(0, match.start - offset),
            end=max(0, match.end - offset),
        )
        for match in matches
        if match.end > start and match.start < end
    ]
    return snippet, adjusted


def _looks_binary(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data:
        return True
    control_count = sum(1 for value in data if value < 32 and value not in {7, 8, 9, 10, 12, 13, 27})
    return control_count / len(data) > 0.30
