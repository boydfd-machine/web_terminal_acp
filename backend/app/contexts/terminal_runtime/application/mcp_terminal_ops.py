from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.local_runtime_factory import create_local_terminal_runtime
from app.contexts.terminal_runtime.application.runtime_binding import RuntimeWindowBinding
from app.contexts.terminal_runtime.infrastructure.remote import RemoteRuntime
from app.contexts.terminal_runtime.infrastructure.tmux_manager import TmuxManager
from app.models import Client, ClientRuntime, LOCAL_CLIENT_ID, VirtualWindow


@dataclass(frozen=True)
class TerminalCapture:
    text: str
    truncated: bool


class TerminalRuntimeNotReady(RuntimeError):
    pass


class McpTerminalRuntime:
    def __init__(
        self,
        *,
        app_state: object,
        tmux_manager: TmuxManager,
        registry: ClientConnectionRegistry,
    ) -> None:
        self._app_state = app_state
        self._tmux_manager = tmux_manager
        self._registry = registry

    def _broker_for(self, client: Client) -> TerminalBroker:
        broker = getattr(self._app_state, "terminal_broker", None)
        if broker is None:
            broker = TerminalBroker()
            self._app_state.terminal_broker = broker

        if client.runtime is ClientRuntime.local:
            if broker.runtime_for(LOCAL_CLIENT_ID) is None:
                local_runtime = getattr(self._app_state, "local_terminal_runtime", None)
                if local_runtime is None:
                    from app.db import SessionLocal

                    local_runtime = create_local_terminal_runtime(
                        self._tmux_manager,
                        session_factory=SessionLocal,
                    )
                    self._app_state.local_terminal_runtime = local_runtime
                broker.register_runtime(LOCAL_CLIENT_ID, local_runtime)
            return broker

        broker.register_runtime(client.id, RemoteRuntime(client_id=client.id, registry=self._registry))
        return broker

    async def send_input(
        self,
        *,
        client: Client,
        window: VirtualWindow,
        data: bytes,
    ) -> None:
        binding = self._require_binding(window)
        await self._broker_for(client).send_input_direct(
            client.id,
            window.id,
            binding.runtime_window,
            data,
        )

    async def capture_output(
        self,
        *,
        client: Client,
        window: VirtualWindow,
        history_lines: int | None = None,
        max_bytes: int | None = None,
    ) -> TerminalCapture:
        binding = self._require_binding(window)
        output = await self._broker_for(client).capture_output_bytes(
            client.id,
            window.id,
            binding.runtime_window,
            history_lines=history_lines,
        )
        truncated = False
        if max_bytes is not None and max_bytes >= 0 and len(output) > max_bytes:
            output = output[-max_bytes:]
            truncated = True
        return TerminalCapture(
            text=output.decode("utf-8", errors="replace"),
            truncated=truncated,
        )

    async def wait_for_output(
        self,
        *,
        client: Client,
        window: VirtualWindow,
        contains: str,
        timeout_seconds: float,
        poll_interval_seconds: float,
        history_lines: int | None = None,
    ) -> TerminalCapture:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        last_capture = TerminalCapture(text="", truncated=False)
        while True:
            last_capture = await self.capture_output(
                client=client,
                window=window,
                history_lines=history_lines,
            )
            if contains in last_capture.text:
                return last_capture
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return last_capture
            await asyncio.sleep(min(poll_interval_seconds, remaining))

    @staticmethod
    def _require_binding(window: VirtualWindow) -> RuntimeWindowBinding:
        binding = RuntimeWindowBinding.from_virtual_window(window)
        if binding is None:
            raise TerminalRuntimeNotReady("terminal runtime is not ready")
        return binding
