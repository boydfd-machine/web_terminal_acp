from tests.integration.test_window_api_support import *


@pytest.mark.asyncio
async def test_manual_work_status_overrides_window_and_activity_cache(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        window_id = str(window.id)
        await session.commit()

    first_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert first_response.status_code == 200
    assert first_response.json()["work_status"]["state"] == "LONG_IDLE"

    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_id}/work-status",
        json={"state": "WORKING"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["state"] == "WORKING"
    assert patch_response.json()["source"] == "manual"
    assert patch_response.json()["manual_updated_at"] is not None

    detail_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert detail_response.status_code == 200
    detail_status = detail_response.json()["work_status"]
    assert detail_status["state"] == "WORKING"
    assert detail_status["source"] == "manual"

    activity_response = await db_client.get(f"/api/clients/{client_id}/windows/activity")
    assert activity_response.status_code == 200
    activity_window = next(
        item for item in activity_response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["work_status"]["state"] == "WORKING"
    assert activity_window["work_status"]["source"] == "manual"
    assert activity_window["last_agent_task_status"] is None

    clear_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_id}/work-status",
        json={"state": None},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["state"] == "LONG_IDLE"
    assert clear_response.json()["source"] == "activity"

    cleared_detail_response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}")
    assert cleared_detail_response.status_code == 200
    assert cleared_detail_response.json()["work_status"]["state"] == "LONG_IDLE"
    assert cleared_detail_response.json()["work_status"]["source"] == "activity"


@pytest.mark.asyncio
async def test_manual_finished_work_status_drives_task_status_and_notifications(db_client):
    client_id = await get_local_client_id(db_client)
    async with db_client.session_factory() as session:
        client = await ensure_local_client(session)
        window = await create_window(session, client.id, cwd="/tmp", shell_command="/bin/bash")
        window_id = str(window.id)
        await session.commit()

    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_id}/work-status",
        json={"state": "FINISHED"},
    )
    assert patch_response.status_code == 200
    manual_updated_at = patch_response.json()["manual_updated_at"]

    activity_response = await db_client.get(f"/api/clients/{client_id}/windows/activity")
    assert activity_response.status_code == 200
    activity_window = next(
        item for item in activity_response.json()["windows"] if item["window_id"] == window_id
    )
    assert activity_window["work_status"]["state"] == "FINISHED"
    assert parse_response_datetime(activity_window["last_agent_task_completed_at"]) == parse_response_datetime(
        manual_updated_at
    )
    assert activity_window["last_agent_task_status"] == "FINISHED"
    assert parse_response_datetime(activity_window["last_agent_task_status_at"]) == parse_response_datetime(
        manual_updated_at
    )

    notifications_response = await db_client.get(f"/api/clients/{client_id}/terminal-notifications")
    assert notifications_response.status_code == 200
    notification = notifications_response.json()["notifications"][0]
    assert notification["window_id"] == window_id
    assert notification["status"] == "FINISHED"
    assert parse_response_datetime(notification["completed_at"]) == parse_response_datetime(manual_updated_at)
