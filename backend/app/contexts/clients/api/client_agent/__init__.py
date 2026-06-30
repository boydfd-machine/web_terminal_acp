from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType

_connection = import_module("app.contexts.clients.api.client_agent.connection")
_message_handlers = import_module("app.contexts.clients.api.client_agent.message_handlers")
_bulk_websocket = import_module("app.contexts.clients.api.client_agent.bulk_websocket")
_single_websocket = import_module("app.contexts.clients.api.client_agent.single_websocket")
_MODULES = (_connection, _message_handlers, _bulk_websocket, _single_websocket)

_exports = {}
for _module in _MODULES:
    _exports.update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )
globals().update(_exports)

for _module in _MODULES:
    _module.__dict__.update(_exports)

sys.modules["app.routers.client_agent.connection"] = _connection
sys.modules["app.routers.client_agent.message_handlers"] = _message_handlers
sys.modules["app.routers.client_agent.bulk_websocket"] = _bulk_websocket
sys.modules["app.routers.client_agent.single_websocket"] = _single_websocket


class _ClientAgentApiPackage(ModuleType):
    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        for module in _MODULES:
            if hasattr(module, name):
                setattr(module, name, value)


sys.modules[__name__].__class__ = _ClientAgentApiPackage

__all__ = [name for name in globals() if not name.startswith("__")]
