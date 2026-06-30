from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.agent_profiles.domain import AgentProfileUpdate
from app.contexts.windows.domain.remote_agents import RemoteAgentCatalog
from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.windows.application.remote_agent_resolution import require_remote_agent_id
from app.models import ClientRuntime
from app.contexts.clients.application.client_lookup import get_client
from app.contexts.agent_profiles.api.schemas import (
    AgentConfigOut,
    AgentProfileCreateIn,
    AgentProfileListOut,
    AgentProfileOut,
)
from app.contexts.agent_profiles.infrastructure import profile_store as local_profiles
from app.contexts.agent_profiles.infrastructure import profile_import_export
from app.contexts.agent_profiles.infrastructure import system_settings_repository
from app.contexts.agent_profiles.infrastructure import profile_settings_repository
from app.contexts.agent_profiles.application import system_config as system_config_service
from app.contexts.agent_profiles.application.capabilities import (
    AgentClientCapabilityError,
    canonical_provider,
    require_local_agent_capability,
    require_supported_agent_capability,
)
from app.contexts.agent_profiles.application.config_projection import agent_config_out
from app.contexts.agent_profiles.infrastructure import builtin_profiles
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.runtime_provider import RemoteClientUnavailable, RemoteRuntime, RemoteTerminalError


class AgentProfileApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class AgentProfileApiService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        registry: ClientConnectionRegistry | None = None,
    ) -> None:
        self._session = session
        self._registry = registry

    async def list_profiles(self, client_id: UUID | None = None) -> AgentProfileListOut:
        remote_runtime = await self._remote_runtime(client_id)
        if remote_runtime is None:
            home = await self._restore_local_profile_files()
            profiles = await self._local_call(local_profiles.list_agent_profiles, home=home)
            return AgentProfileListOut(
                profiles=[profile_out(profile) for profile in profiles + builtin_profiles.builtin_agent_profiles()]
            )
        return AgentProfileListOut.model_validate(
            await self._remote_call(remote_runtime.list_agent_profiles)
        )

    async def create_profile(
        self,
        payload: AgentProfileCreateIn,
        *,
        client_id: UUID | None = None,
    ) -> AgentProfileOut:
        remote_runtime = await self._remote_runtime(client_id)
        if remote_runtime is not None:
            await self._require_remote_create_capabilities(remote_runtime, payload)
            return AgentProfileOut.model_validate(
                await self._remote_call(
                    remote_runtime.create_agent_profile,
                    payload.model_dump(mode="json"),
                    system_config_files=await self._system_config_files_for_remote(),
                )
            )

        self._require_local_create_capabilities(payload)
        home = await self._restore_local_profile_files()
        await self._restore_local_system_config_files(home=home)
        try:
            profile = await self._local_call(
                local_profiles.create_agent_profile,
                name=payload.name,
                description=payload.description,
                default_agent_client=payload.default_agent_client,
                source_agent_client=payload.source_agent_client,
                home=home,
            )
            await self._persist_local_profile_files(home)
            return profile_out(profile)
        except ValueError as exc:
            raise AgentProfileApiError(400, str(exc)) from exc

    async def get_profile(self, profile_id: str, *, client_id: UUID | None = None) -> AgentProfileOut:
        remote_runtime = await self._remote_runtime(client_id)
        if remote_runtime is not None:
            profiles = await self.list_profiles(client_id)
            for profile in profiles.profiles:
                if profile.id == profile_id:
                    return profile
            raise AgentProfileApiError(404, "agent profile not found")
        builtin_profile = builtin_profiles.get_builtin_agent_profile(profile_id)
        if builtin_profile is not None:
            return profile_out(builtin_profile)
        try:
            home = await self._restore_local_profile_files()
            return profile_out(await self._local_call(local_profiles.get_agent_profile, profile_id, home=home))
        except ValueError as exc:
            raise AgentProfileApiError(404, str(exc)) from exc

    async def update_profile(
        self,
        profile_id: str,
        update: AgentProfileUpdate,
        *,
        client_id: UUID | None = None,
    ) -> AgentProfileOut:
        if builtin_profiles.is_builtin_profile_id(profile_id):
            raise AgentProfileApiError(400, "built-in agent profile is read-only")
        remote_runtime = await self._remote_runtime(client_id)
        if remote_runtime is not None:
            await self._require_remote_update_capabilities(remote_runtime, update)
            return AgentProfileOut.model_validate(
                await self._remote_call(
                    remote_runtime.update_agent_profile,
                    profile_id,
                    update.remote_patch(),
                    system_config_files=await self._system_config_files_for_remote(),
                )
            )

        self._require_local_update_capabilities(update)
        try:
            home = await self._restore_local_profile_files()
            profile = await self._local_call(
                local_profiles.update_agent_profile,
                profile_id,
                name=update.name,
                description=update.description,
                default_agent_client=update.default_agent_client,
                agent_md=update.agent_md,
                home=home,
            )
            await self._persist_local_profile_files(home)
            return profile_out(profile)
        except ValueError as exc:
            raise AgentProfileApiError(400, str(exc)) from exc

    async def delete_profile(self, profile_id: str, *, client_id: UUID | None = None) -> None:
        if builtin_profiles.is_builtin_profile_id(profile_id):
            raise AgentProfileApiError(400, "built-in agent profile is read-only")
        remote_runtime = await self._remote_runtime(client_id)
        if remote_runtime is not None:
            await self._remote_call(remote_runtime.delete_agent_profile, profile_id)
            return
        try:
            home = await self._restore_local_profile_files()
            await self._local_call(local_profiles.delete_agent_profile, profile_id, home=home)
            await self._persist_local_profile_files(home)
        except ValueError as exc:
            raise AgentProfileApiError(404, str(exc)) from exc

    async def export_profile_bundle(
        self,
        profile_id: str,
        *,
        client_id: UUID | None = None,
    ) -> dict[str, object]:
        if builtin_profiles.is_builtin_profile_id(profile_id):
            if client_id is not None:
                client = await get_client(self._session, client_id)
                if client is None:
                    raise AgentProfileApiError(404, "client not found")
            home = await self._restore_local_profile_files()
            return await self._local_call(
                profile_import_export.export_agent_profile_bundle,
                profile_id,
                home=home,
            )
        if await self._remote_runtime(client_id) is not None:
            raise AgentProfileApiError(400, "agent profile export is only supported for local clients")
        try:
            home = await self._restore_local_profile_files()
            return await self._local_call(
                profile_import_export.export_agent_profile_bundle,
                profile_id,
                home=home,
            )
        except ValueError as exc:
            raise AgentProfileApiError(404, str(exc)) from exc

    async def import_profile_bundle(
        self,
        payload: object,
        *,
        client_id: UUID | None = None,
    ) -> AgentProfileOut:
        if await self._remote_runtime(client_id) is not None:
            raise AgentProfileApiError(400, "agent profile import is only supported for local clients")
        try:
            home = await self._restore_local_profile_files()
            profile = await self._local_call(
                profile_import_export.import_agent_profile_bundle,
                payload,
                home=home,
            )
            await self._persist_local_profile_files(home)
            return profile_out(profile)
        except ValueError as exc:
            raise AgentProfileApiError(400, str(exc)) from exc

    async def get_profile_config(
        self,
        profile_id: str,
        agent: str,
        *,
        client_id: UUID,
    ) -> AgentConfigOut:
        remote_runtime = await self._remote_runtime(client_id)
        if remote_runtime is None:
            local_agent = self._require_supported_local_agent(agent, "profile_config")
            home = await self._restore_local_profile_files()
            await self._restore_local_system_config_files(home=home)
            try:
                config = builtin_profiles.builtin_profile_config(profile_id, local_agent, home=home)
                if config is not None:
                    return agent_config_out(config)
                config = await self._local_call(
                    local_profiles.list_agent_profile_config,
                    profile_id,
                    local_agent,
                    home=home,
                )
                return agent_config_out(config)
            except ValueError as exc:
                raise AgentProfileApiError(404, str(exc)) from exc

        remote_agent = await self._remote_agent_for_capability(remote_runtime, agent, "profile_config")
        return agent_config_out(
            await self._remote_call(
                remote_runtime.get_agent_profile_config,
                profile_id=profile_id,
                agent=remote_agent,
                system_config_files=await self._system_config_files_for_remote(),
            )
        )

    async def set_profile_config_item_enabled(
        self,
        profile_id: str,
        agent: str,
        section_id: str,
        item_id: str,
        enabled: bool,
        *,
        client_id: UUID | None = None,
    ) -> AgentConfigOut:
        remote_runtime = await self._remote_runtime(client_id)
        if remote_runtime is not None:
            remote_agent = await self._remote_agent_for_capability(
                remote_runtime,
                agent,
                "profile_config",
            )
            return agent_config_out(
                await self._remote_call(
                    remote_runtime.set_agent_profile_config_enabled,
                    profile_id=profile_id,
                    agent=remote_agent,
                    section_id=section_id,
                    item_id=item_id,
                    enabled=enabled,
                    system_config_files=await self._system_config_files_for_remote(),
                )
            )

        local_agent = self._require_supported_local_agent(agent, "profile_config")
        home = await self._restore_local_profile_files()
        await self._restore_local_system_config_files(home=home)
        try:
            if builtin_profiles.is_builtin_profile_id(profile_id):
                config = await self._local_call(
                    builtin_profiles.set_builtin_profile_config_item_enabled,
                    profile_id,
                    local_agent,
                    section_id,
                    item_id,
                    enabled,
                    home=home,
                )
                await self._persist_local_profile_files(home)
                return agent_config_out(config)
            config = await self._local_call(
                local_profiles.set_agent_profile_config_item_enabled,
                profile_id,
                local_agent,
                section_id,
                item_id,
                enabled,
                home=home,
            )
            await self._persist_local_profile_files(home)
            return agent_config_out(
                config
            )
        except ValueError as exc:
            raise AgentProfileApiError(400, str(exc)) from exc

    async def _remote_runtime(self, client_id: UUID | None) -> RemoteRuntime | None:
        if client_id is None:
            return None
        client = await get_client(self._session, client_id)
        if client is None:
            raise AgentProfileApiError(404, "client not found")
        if client.runtime is ClientRuntime.local:
            return None
        if self._registry is None:
            raise AgentProfileApiError(503, "remote runtime unavailable")
        return RemoteRuntime(client_id=client_id, registry=self._registry)

    def _require_local_create_capabilities(self, payload: AgentProfileCreateIn) -> None:
        self._require_local_agent(payload.default_agent_client, "launch")
        self._require_local_agent(
            payload.source_agent_client or payload.default_agent_client,
            "profile_config",
        )

    def _require_local_update_capabilities(self, update: AgentProfileUpdate) -> None:
        if update.default_agent_client is not None:
            self._require_local_agent(update.default_agent_client, "launch")

    async def _require_remote_create_capabilities(
        self,
        remote_runtime: RemoteRuntime,
        payload: AgentProfileCreateIn,
    ) -> None:
        catalog = await self._remote_agent_catalog(remote_runtime)
        self._require_remote_agent(catalog, payload.default_agent_client, "launch")
        self._require_remote_agent(
            catalog,
            payload.source_agent_client or payload.default_agent_client,
            "profile_config",
        )

    async def _require_remote_update_capabilities(
        self,
        remote_runtime: RemoteRuntime,
        update: AgentProfileUpdate,
    ) -> None:
        if update.default_agent_client is None:
            return
        catalog = await self._remote_agent_catalog(remote_runtime)
        self._require_remote_agent(catalog, update.default_agent_client, "launch")

    async def _remote_agent_for_capability(
        self,
        remote_runtime: RemoteRuntime,
        agent: str,
        capability,
    ) -> str:
        catalog = await self._remote_agent_catalog(remote_runtime)
        return self._require_remote_agent(catalog, agent, capability)

    async def _remote_agent_catalog(self, remote_runtime: RemoteRuntime) -> RemoteAgentCatalog:
        return RemoteAgentCatalog.from_payload(
            await self._remote_call(remote_runtime.list_agent_clients)
        )

    @staticmethod
    def _require_remote_agent(catalog: RemoteAgentCatalog, agent: str, capability) -> str:
        try:
            return require_remote_agent_id(catalog, agent, capability)
        except WindowServiceError as exc:
            raise AgentProfileApiError(exc.status_code, exc.detail) from exc

    @staticmethod
    def _require_local_agent(agent: str, capability) -> str:
        try:
            return require_local_agent_capability(agent, capability)
        except AgentClientCapabilityError as exc:
            raise AgentProfileApiError(exc.status_code, exc.detail) from exc

    async def _restore_local_system_config_files(self, *, home=None) -> None:
        await system_settings_repository.restore_system_agent_config_files_to_disk(self._session, home=home)
        await self._session.commit()

    async def _system_config_files_for_remote(self) -> dict[str, object]:
        payload = await system_config_service.system_agent_config_files_payload(self._session)
        await self._session.commit()
        return payload

    async def _restore_local_profile_files(self):
        home = await profile_settings_repository.restore_agent_profile_files_to_disk(self._session)
        await self._session.commit()
        return home

    async def _persist_local_profile_files(self, home) -> None:
        await profile_settings_repository.persist_agent_profile_files(self._session, home=home)
        await self._session.commit()

    @staticmethod
    def _require_supported_local_agent(agent: str, capability) -> str:
        try:
            return require_supported_agent_capability(canonical_provider(agent), capability)
        except AgentClientCapabilityError as exc:
            raise AgentProfileApiError(exc.status_code, exc.detail) from exc

    @staticmethod
    async def _remote_call(func, /, *args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except RemoteClientUnavailable as exc:
            raise AgentProfileApiError(503, "remote runtime unavailable") from exc
        except RemoteTerminalError as exc:
            raise AgentProfileApiError(502, str(exc)) from exc

    @staticmethod
    async def _local_call(func, /, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)


def profile_out(profile: local_profiles.AgentProfile) -> AgentProfileOut:
    return AgentProfileOut(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        default_agent_client=profile.default_agent_client,
        agent_md=profile.agent_md,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
