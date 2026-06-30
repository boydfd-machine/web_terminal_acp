from app.contexts.windows.api.schemas import GitWorktreeRunOut


def to_git_worktree_run_out(run) -> GitWorktreeRunOut:
    run_type = "tracking" if str(run.command_sequence).startswith("worktree:") else "agent"
    return GitWorktreeRunOut(
        id=run.id,
        virtual_window_id=run.virtual_window_id,
        command_sequence=run.command_sequence,
        agent_provider=run.agent_provider,
        status=run.status,
        run_type=run_type,
        worktree_root=run.worktree_root,
        main_repo_root=run.main_repo_root,
        discovery_method=run.discovery_method,
        start_snapshot_json=run.start_snapshot_json,
        end_snapshot_json=run.end_snapshot_json,
        session_diff_json=run.session_diff_json,
        pending_commit=run.pending_commit,
        resolved_at=run.resolved_at,
        started_at=run.started_at,
        ended_at=run.ended_at,
    )
