from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_runtime.application.git_worktree_queries import (
    list_client_git_bindings_for_project_root,
    list_client_git_bindings_for_roots,
    pending_commit_window_ids,
)
from app.contexts.workspace.api.schemas import ProjectBrowseRootListOut, ProjectBrowseRootOut
from app.contexts.workspace.application.project_files import (
    ProjectPathError,
    ProjectResolvedPath,
    normalize_project_path,
    resolve_project_relative_path,
)


async def resolve_project_browse_path(
    session: AsyncSession,
    client_id: UUID,
    *,
    project_path: str,
    path: str | None,
    browse_root: str | None,
) -> ProjectResolvedPath:
    project_root = normalize_project_path(project_path)
    requested_root = project_root if browse_root is None or not browse_root.strip() else normalize_project_path(browse_root)
    bindings = await list_client_git_bindings_for_roots(session, client_id, [project_root, requested_root])
    binding = next(
        (
            binding
            for binding in bindings
            if (
                project_root in {binding.main_repo_root, binding.worktree_root}
                and requested_root in {binding.main_repo_root, binding.worktree_root}
            )
        ),
        None,
    )
    if requested_root != project_root and binding is None:
        raise ProjectPathError("browse_root is not registered for project")
    canonical_project_root = binding.main_repo_root if binding is not None else project_root
    return resolve_project_relative_path(canonical_project_root, path, browse_root=requested_root)


async def project_browse_root_options(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
) -> ProjectBrowseRootListOut:
    project_root = normalize_project_path(project_path)
    bindings = await list_client_git_bindings_for_project_root(session, client_id, project_root)
    canonical_project_root = next(
        (
            binding.main_repo_root
            for binding in bindings
            if project_root in {binding.main_repo_root, binding.worktree_root}
        ),
        project_root,
    )
    pending_window_ids = await pending_commit_window_ids(
        session,
        [binding.virtual_window_id for binding in bindings],
    )
    roots = [
        ProjectBrowseRootOut(
            kind="main",
            project_path=canonical_project_root,
            browse_root=None,
            pending_commit=False,
        )
    ]
    seen_worktree_roots: set[str] = set()
    for binding in bindings:
        if binding.worktree_root in seen_worktree_roots:
            continue
        seen_worktree_roots.add(binding.worktree_root)
        roots.append(
            ProjectBrowseRootOut(
                kind="worktree",
                project_path=binding.main_repo_root,
                browse_root=binding.worktree_root,
                branch=binding.branch,
                pending_commit=binding.virtual_window_id in pending_window_ids,
            )
        )
    return ProjectBrowseRootListOut(roots=roots)
