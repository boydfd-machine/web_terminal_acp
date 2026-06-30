from uuid import uuid4

import pytest

from elastic_transport import TransportError

from app.main import app

from app.models import LOCAL_CLIENT_ID

from app.routers import search as search_router

from app.services.search_index import (
    AI_EVENTS_INDEX,
    INDEX_MAPPINGS,
    MAX_INDEXED_RAW_BYTES,
    MAX_INDEXED_TEXT_CHARS,
    SUMMARIES_INDEX,
    TERMINAL_INDEX,
    ai_event_doc,
    ensure_indexes,
    index_ai_event,
    index_terminal_chunk,
    index_terminal_chunk_without_event,
    is_flood_stage_index_block,
    search_all,
    summary_doc,
    terminal_chunk_doc,
)

class FakeIndices:
    def __init__(self, existing_indexes):
        self.existing_indexes = set(existing_indexes)
        self.created = []
        self.updated_mappings = []

    async def exists(self, index):
        return index in self.existing_indexes

    async def create(self, index, **body):
        self.created.append((index, body))
        self.existing_indexes.add(index)

    async def put_mapping(self, index, **body):
        self.updated_mappings.append((index, body))

class FakeIndexClient:
    def __init__(self, existing_indexes=()):
        self.indices = FakeIndices(existing_indexes)
        self.indexed_documents = []

    async def index(self, **kwargs):
        self.indexed_documents.append(kwargs)
        return {"result": "created"}

class FakeSearchClient:
    def __init__(self, hits=None):
        self.calls = []
        self.hits = hits or [
            {
                "_index": TERMINAL_INDEX,
                "_score": 2.5,
                "_source": {"text": "nginx 403 permission denied"},
            },
            {
                "_index": SUMMARIES_INDEX,
                "_score": None,
                "_source": {"title": "Nginx incident"},
            },
        ]

    async def search(self, **kwargs):
        self.calls.append(kwargs)
        return {"hits": {"hits": self.hits}}

class FakeRouteClient:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True

__all__ = [name for name in globals() if not name.startswith("__")]
