from __future__ import annotations

import sys

from app.contexts.clients import application as _application
from app.contexts.clients.application import api_service as _api_service
from app.contexts.clients.application import bootstrap_service as _bootstrap_service
from app.contexts.clients.application import crud_service as _crud_service
from app.contexts.clients.application import errors as _errors
from app.contexts.clients.application import events as _events
from app.contexts.clients.application import listing_service as _listing_service
from app.contexts.clients.application import registration_service as _registration_service
from app.contexts.clients.application import update_service as _update_service
from app.contexts.clients.infrastructure import connections as _connections
from app.contexts.clients.infrastructure import runners as _runners

sys.modules[__name__] = _application
sys.modules[f"{__name__}.api_service"] = _api_service
sys.modules[f"{__name__}.bootstrap_service"] = _bootstrap_service
sys.modules[f"{__name__}.connections"] = _connections
sys.modules[f"{__name__}.crud_service"] = _crud_service
sys.modules[f"{__name__}.errors"] = _errors
sys.modules[f"{__name__}.events"] = _events
sys.modules[f"{__name__}.listing_service"] = _listing_service
sys.modules[f"{__name__}.registration_service"] = _registration_service
sys.modules[f"{__name__}.runners"] = _runners
sys.modules[f"{__name__}.update_service"] = _update_service
