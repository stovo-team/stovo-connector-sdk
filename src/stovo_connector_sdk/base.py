"""Base class interface for custom Stovo Connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from .models import (
    AuthorizationDecision,
    AuthorizationOperation,
    BackfillResponse,
    CitationResolution,
    EventsResponse,
    ResourceSnapshot,
    SourceEvent,
    TextLocator,
)


class BaseConnector(ABC):
    """Abstract base class for building an external data source connector for Stovo Insight."""

    kind: str = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "kind", None):
            name = cls.__name__.lower()
            if name.endswith("connector") and len(name) > 9:
                name = name[:-9]
            cls.kind = name

    @abstractmethod
    async def get_scopes(self) -> list[tuple[str, str]]:
        """Return the active (tenant_id, connection_id) pairs this connector serves."""
        raise NotImplementedError

    @abstractmethod
    async def begin_backfill(
        self, tenant_id: str, connection_id: str, *, page_size: int = 100
    ) -> BackfillResponse:
        """Start a historical snapshot backfill for a given connection scope."""
        raise NotImplementedError

    @abstractmethod
    async def continue_backfill(
        self,
        cursor: str,
        *,
        page_size: int = 100,
        backfill_id: str | None = None,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> BackfillResponse:
        """Continue a historical backfill using an opaque cursor."""
        raise NotImplementedError

    @abstractmethod
    async def list_events(
        self,
        cursor: str,
        *,
        limit: int = 100,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> EventsResponse:
        """Stream incremental change events (create, update, delete, etc.) using an opaque cursor."""
        raise NotImplementedError

    async def list_changes(
        self, tenant_id: str, connection_id: str, *, after_sequence: int = 0, limit: int = 100
    ) -> list[SourceEvent]:
        """Optionally return changes strictly after a sequence number."""
        return []

    @abstractmethod
    async def get_snapshot(
        self,
        resource_id: str,
        revision_id: str,
        *,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> ResourceSnapshot:
        """Fetch the exact content and metadata snapshot for a specific resource revision."""
        raise NotImplementedError

    @abstractmethod
    async def bulk_authorize(
        self,
        principal_id: str,
        operation: AuthorizationOperation,
        resource_ids: Sequence[str],
        *,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> list[AuthorizationDecision]:
        """Authorize access for a principal to a set of resources. Must check source-authoritative ACL."""
        raise NotImplementedError

    async def resolve_citation(
        self,
        resource_id: str,
        revision_id: str,
        locator: TextLocator,
        *,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> CitationResolution:
        """Resolve a cited text span into an external URL/source reference."""
        return CitationResolution(
            resource_id=resource_id,
            revision_id=revision_id,
            url=f"https://source.local/items/{resource_id}",
            title=resource_id,
        )

    @classmethod
    def serve(
        cls,
        *,
        host: str = "0.0.0.0",
        port: int = 8080,
        auth_token: str | None = None,
        log_level: str = "info",
    ) -> None:
        """Convenience method to launch this connector as an HTTP service."""
        import uvicorn
        from .server import create_connector_app

        instance = cls()
        app = create_connector_app(instance, auth_token=auth_token)
        uvicorn.run(app, host=host, port=port, log_level=log_level)
