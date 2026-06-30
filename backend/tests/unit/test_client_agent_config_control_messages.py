from tests.unit.test_client_agent_config_support import *

async def test_send_terminal_selection_includes_view_id_when_present() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    view_id = UUID("11111111-2222-3333-4444-555555555555")
    sent_messages: list[dict[str, object]] = []

    writer = _CollectingControlWriter(sent_messages)

    await client_agent_runner._send_terminal_selection(
        writer,
        client_id,
        window_id,
        view_id=view_id,
    )

    assert sent_messages[0]["payload"] == {"view_id": str(view_id)}

async def test_send_terminal_attach_result_uses_request_id() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    sent_messages: list[dict[str, object]] = []

    writer = _CollectingControlWriter(sent_messages)

    await client_agent_runner._send_terminal_attach_result(
        writer,
        client_id,
        window_id,
        request_id="attach-1",
    )

    assert sent_messages == [
        {
            "type": "terminal_attach_result",
            "client_id": str(client_id),
            "window_id": str(window_id),
            "request_id": "attach-1",
            "payload": {"ok": True},
        }
    ]

async def test_send_terminal_error_uses_request_id_and_message() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    sent_messages: list[dict[str, object]] = []

    writer = _CollectingControlWriter(sent_messages)

    await client_agent_runner._send_terminal_error(
        writer,
        client_id,
        window_id,
        request_id="attach-1",
        message="tmux attach failed",
    )

    assert sent_messages == [
        {
            "type": "terminal_error",
            "client_id": str(client_id),
            "window_id": str(window_id),
            "request_id": "attach-1",
            "payload": {"message": "tmux attach failed"},
        }
    ]

async def test_send_terminal_error_includes_view_id_when_present() -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    view_id = UUID("11111111-2222-3333-4444-555555555555")
    sent_messages: list[dict[str, object]] = []

    writer = _CollectingControlWriter(sent_messages)

    await client_agent_runner._send_terminal_error(
        writer,
        client_id,
        window_id,
        request_id=None,
        message="resize failed",
        view_id=view_id,
    )

    assert sent_messages[0]["payload"] == {
        "message": "resize failed",
        "view_id": str(view_id),
    }
