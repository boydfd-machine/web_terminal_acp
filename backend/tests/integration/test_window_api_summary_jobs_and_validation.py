from tests.integration.test_window_api_support import *

@pytest.mark.asyncio
async def test_get_window_agent_record_projects_generic_cursor_and_legacy_alias_claude_events(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    window_id = UUID(window_response.json()["id"])

    async with db_client.session_factory() as session:
        claude_session = AiSession(
            client_id=UUID(client_id),
            provider="claude",
            source_id="claude-alias-session",
            virtual_window_id=window_id,
        )
        session.add(claude_session)
        await session.flush()
        base_time = datetime.now(timezone.utc)
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="cursor-session-1",
                    kind="assistant_message",
                    virtual_window_id=window_id,
                    payload_json={
                        "provider": "cursor_cli",
                        "role": "assistant",
                        "text": "Cursor rendered this",
                    },
                    fingerprint="agent-record-cursor-projection",
                    created_at=base_time,
                ),
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.agent_tool_record,
                    source_id="claude-alias-session",
                    kind="user_message",
                    virtual_window_id=window_id,
                    ai_session_id=claude_session.id,
                    payload_json={"type": "user", "message": {"content": "Legacy Claude alias"}},
                    fingerprint="agent-record-claude-alias-projection",
                    created_at=base_time + timedelta(milliseconds=1),
                ),
            ]
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}/agent-record/detail")

    assert response.status_code == 200
    projections = [event["projection"] for event in response.json()["events"]]
    expected = [
        {
            "tone": "agent",
            "label": "Agent response",
            "body": "Cursor rendered this",
            "body_format": "markdown",
            "subtype": "assistant_message",
        },
        {
            "tone": "user-input",
            "label": "User input",
            "body": "Legacy Claude alias",
            "body_format": "markdown",
            "subtype": "user_message",
        },
    ]
    for projection, expected_projection in zip(projections, expected, strict=True):
        assert projection | expected_projection == projection

@pytest.mark.asyncio
async def test_get_window_agent_record_paginates_events(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/tmp/project", "shell_command": "/bin/bash"},
    )
    window_id = UUID(window_response.json()["id"])
    base_time = datetime(2026, 5, 22, tzinfo=timezone.utc)

    async with db_client.session_factory() as session:
        session.add_all(
            [
                Event(
                    client_id=UUID(client_id),
                    source_type=EventSourceType.terminal,
                    source_id=str(window_id),
                    kind="terminal_input_command",
                    virtual_window_id=window_id,
                    payload_json={"command": f"cmd-{index}"},
                    fingerprint=f"agent-record-page-{index}",
                    created_at=base_time + timedelta(seconds=index),
                )
                for index in range(3)
            ]
        )
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{client_id}/windows/{window_id}/agent-record?events_limit=2&events_offset=1"
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["payload_json"]["command"] for item in body["events"]] == ["cmd-1", "cmd-2"]
    assert body["events_total"] == 3
    assert body["events_limit"] == 2
    assert body["events_offset"] == 1
    assert body["events_has_more"] is False

@pytest.mark.asyncio
async def test_patch_window_accepts_disconnected_status(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )

    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}",
        json={"status": "DISCONNECTED"},
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "DISCONNECTED"

@pytest.mark.asyncio
async def test_summary_job_enqueued_once_for_repeated_enqueue(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    window_id = window_response.json()["id"]

    first_retry = await db_client.post(f"/api/clients/{client_id}/windows/{window_id}/summary_jobs")
    second_retry = await db_client.post(f"/api/clients/{client_id}/windows/{window_id}/summary_jobs")

    assert first_retry.status_code == 200
    assert second_retry.status_code == 200
    assert second_retry.json()["id"] == window_id

    async with db_client.session_factory() as session:
        jobs = list(
            await session.scalars(
                select(SummaryJob).where(SummaryJob.virtual_window_id == UUID(window_id))
            )
        )

    assert len(jobs) == 1
    assert jobs[0].status is SummaryJobStatus.pending

@pytest.mark.asyncio
async def test_retry_summary_job_accepts_missing_body_and_records_manual_retry(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    window_id = window_response.json()["id"]

    retry_response = await db_client.post(f"/api/clients/{client_id}/windows/{window_id}/summary_jobs")

    assert retry_response.status_code == 200
    body = retry_response.json()
    assert body["summary_job"]["trigger_reason"] == "manual_retry"
    assert body["summary_job"]["allow_title_folder_override"] is False
    assert body["summary_job"]["run_after"] is not None

@pytest.mark.asyncio
async def test_retry_summary_job_with_override_updates_pending_job(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    window_id = window_response.json()["id"]

    retry_response = await db_client.post(
        f"/api/clients/{client_id}/windows/{window_id}/summary_jobs",
        json={"allow_title_folder_override": True},
    )

    assert retry_response.status_code == 200
    body = retry_response.json()
    assert body["summary_job"]["status"] == "PENDING"
    assert body["summary_job"]["trigger_reason"] == "manual_retry"
    assert body["summary_job"]["allow_title_folder_override"] is True

    async with db_client.session_factory() as session:
        job = await session.scalar(select(SummaryJob).where(SummaryJob.virtual_window_id == UUID(window_id)))

    assert job is not None
    assert job.status is SummaryJobStatus.pending
    assert job.trigger_reason == "manual_retry"
    assert job.allow_title_folder_override is True
    assert job.run_after is not None

@pytest.mark.asyncio
async def test_get_window_returns_latest_summary_job_fields(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    window_id = window_response.json()["id"]
    async with db_client.session_factory() as session:
        job = SummaryJob(virtual_window_id=UUID(window_id), status=SummaryJobStatus.pending)
        session.add(job)
        await session.flush()
        job.attempts = 2
        job.last_error = "temporary failure"
        job.trigger_reason = "terminal_input"
        await session.commit()

    get_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")

    assert get_response.status_code == 200
    summary_job = get_response.json()["summary_job"]
    assert UUID(summary_job["id"])
    assert summary_job["status"] == "PENDING"
    assert summary_job["trigger_reason"] == "terminal_input"
    assert summary_job["attempts"] == 2
    assert summary_job["last_error"] == "temporary failure"
    assert summary_job["allow_title_folder_override"] is False
    assert summary_job["updated_at"] is not None

@pytest.mark.asyncio
async def test_summary_job_enqueue_is_idempotent_under_concurrent_requests(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    window_id = window_response.json()["id"]

    async with db_client.session_factory() as session:
        existing_jobs = list(
            await session.scalars(
                select(SummaryJob).where(SummaryJob.virtual_window_id == UUID(window_id))
            )
        )
        for job in existing_jobs:
            job.status = SummaryJobStatus.succeeded
        await session.commit()

    responses = await asyncio.gather(
        *(db_client.post(f"/api/clients/{client_id}/windows/{window_id}/summary_jobs") for _ in range(8))
    )

    assert all(response.status_code < 500 for response in responses)

    async with db_client.session_factory() as session:
        active_jobs = list(
            await session.scalars(
                select(SummaryJob).where(
                    SummaryJob.virtual_window_id == UUID(window_id),
                    SummaryJob.status.in_([SummaryJobStatus.pending, SummaryJobStatus.running]),
                )
            )
        )

    assert len(active_jobs) == 1

@pytest.mark.asyncio
async def test_patch_window_rejects_blank_title(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )

    response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}", json={"title": "   "}
    )

    assert 400 <= response.status_code < 500

@pytest.mark.asyncio
async def test_patch_window_rejects_too_long_title(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )

    response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}", json={"title": "x" * 256}
    )

    assert 400 <= response.status_code < 500

@pytest.mark.asyncio
async def test_patch_window_rejects_invalid_title_tags(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )

    blank_tag_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}", json={"title_tags": ["Claude", "   "]}
    )
    too_many_tags_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}",
        json={"title_tags": [f"tag-{index}" for index in range(21)]},
    )
    too_long_tag_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}", json={"title_tags": ["x" * 65]}
    )

    assert 400 <= blank_tag_response.status_code < 500
    assert 400 <= too_many_tags_response.status_code < 500
    assert 400 <= too_long_tag_response.status_code < 500

@pytest.mark.asyncio
async def test_create_window_rejects_too_long_cwd_and_shell_command(db_client):
    client_id = await get_local_client_id(db_client)
    too_long_value = "x" * 4097

    cwd_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": too_long_value, "shell_command": "/bin/bash"}
    )
    shell_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": too_long_value}
    )

    assert 400 <= cwd_response.status_code < 500
    assert 400 <= shell_response.status_code < 500

@pytest.mark.asyncio
async def test_missing_window_returns_404(db_client):
    client_id = await get_local_client_id(db_client)
    missing_id = "00000000-0000-0000-0000-000000000000"

    get_response = await db_client.get(f"/api/clients/{client_id}/windows/{missing_id}")
    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{missing_id}", json={"title": "missing"}
    )
    retry_response = await db_client.post(f"/api/clients/{client_id}/windows/{missing_id}/summary_jobs")

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert retry_response.status_code == 404

@pytest.mark.asyncio
async def test_window_route_returns_404_for_missing_client(db_client):
    missing_client_id = "00000000-0000-0000-0000-000000000000"
    missing_window_id = "00000000-0000-0000-0000-000000000000"

    create_response = await db_client.post(
        f"/api/clients/{missing_client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )
    get_response = await db_client.get(f"/api/clients/{missing_client_id}/windows/{missing_window_id}")
    patch_response = await db_client.patch(
        f"/api/clients/{missing_client_id}/windows/{missing_window_id}", json={"title": "missing"}
    )
    retry_response = await db_client.post(
        f"/api/clients/{missing_client_id}/windows/{missing_window_id}/summary_jobs"
    )

    assert create_response.status_code == 404
    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert retry_response.status_code == 404

@pytest.mark.asyncio
async def test_invalid_status_returns_client_error(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )

    response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_response.json()['id']}", json={"status": "NOT_A_STATUS"}
    )

    assert 400 <= response.status_code < 500

@pytest.mark.asyncio
async def test_get_window_returns_long_idle_work_status_without_activity(db_client):
    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows", json={"cwd": "/tmp", "shell_command": "/bin/bash"}
    )

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_response.json()['id']}")

    assert response.status_code == 200
    work_status = response.json()["work_status"]
    assert work_status["state"] == "LONG_IDLE"
    assert work_status["label"] == "长时间没有工作了"
    assert work_status["color"] == "gray"
    assert work_status["last_activity_at"] is None
    assert work_status["last_working_activity_at"] is None
