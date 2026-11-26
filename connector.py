"""Starter implementation of your custom Stovo Connector.

Replace the example in-memory logic with calls to your external service (e.g. Jira, Notion, Slack).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from stovo_connector_sdk import (
    AuthorizationDecision,
    AuthorizationOperation,
    BackfillResponse,
    BaseConnector,
    CitationResolution,
    EventsResponse,
    ResourceSnapshot,
    SourceEvent,
    SourceEventKind,
    TextLocator,
)


class CustomSourceConnector(BaseConnector):
    """Template connector for integrating an external data source into Stovo Insight."""

    def __init__(self) -> None:
        # TODO: Initialize clients for your third-party API (e.g., NotionClient, JiraClient)
        pass

    async def get_scopes(self) -> list[tuple[str, str]]:
        """Return the active (tenant_id, connection_id) pairs this connector serves.

        Example: [("workspace-acme", "conn-jira-prod")]
        """
        # TODO: Return actual tenant and connection IDs
        return [("tenant-default", "connection-default")]

    async def begin_backfill(
        self, tenant_id: str, connection_id: str, *, page_size: int = 100
    ) -> BackfillResponse:
        """Fetch the first page of historical documents/messages.

        Must return:
        - snapshots: list of ResourceSnapshot items
        - cursor: opaque string token for continue_backfill (or None if backfill is complete)
        - fence_cursor: event replay cursor corresponding to this snapshot point-in-time
        """
        # TODO: Query your external system for the initial page of documents
        now = datetime.now(timezone.utc)
        snapshots = [
            ResourceSnapshot(
                tenant_id=tenant_id,
                connection_id=connection_id,
                resource_id="sample-item-1",
                revision_id="v1",
                content_revision_id="v1",
                metadata_revision_id="v1",
                observed_at=now,
                content="This is sample content indexed by your custom connector.",
                metadata={"title": "Sample Document", "container_id": "general"},
            )
        ]
        return BackfillResponse(
            snapshots=snapshots[:page_size],
            cursor="page_token_2",
            fence_cursor="fence_init",
        )

    async def continue_backfill(
        self,
        cursor: str,
        *,
        page_size: int = 100,
        backfill_id: str | None = None,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> BackfillResponse:
        """Fetch subsequent pages of historical documents until cursor is None."""
        # TODO: Fetch next page using cursor
        return BackfillResponse(snapshots=[], cursor=None)

    async def list_events(
        self,
        cursor: str,
        *,
        limit: int = 100,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> EventsResponse:
        """Stream incremental updates (create, update, delete, acl_change).

        Order events with strictly positive source_sequence values.
        """
        # TODO: Fetch incremental changelog/events from your external source
        return EventsResponse(events=[], cursor=cursor, has_more=False)

    async def get_snapshot(
        self,
        resource_id: str,
        revision_id: str,
        *,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> ResourceSnapshot:
        """Fetch the exact content revision for a single document."""
        # TODO: Fetch item by ID and revision from your external system
        return ResourceSnapshot(
            tenant_id=tenant_id or "tenant-default",
            connection_id=connection_id or "connection-default",
            resource_id=resource_id,
            revision_id=revision_id,
            content_revision_id=revision_id,
            metadata_revision_id=revision_id,
            observed_at=datetime.now(timezone.utc),
            content="Exact revision snapshot content",
            metadata={"title": resource_id},
        )

    async def bulk_authorize(
        self,
        principal_id: str,
        operation: AuthorizationOperation,
        resource_ids: Sequence[str],
        *,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> list[AuthorizationDecision]:
        """Source-authoritative ACL verification.

        IMPORTANT: Stovo Insight never stores third-party ACL matrices.
        When a user queries the index, Insight calls this method to confirm
        whether principal_id has access to each requested resource ID right now.
        """
        # TODO: Check permissions in external system for principal_id
        return [
            AuthorizationDecision(
                resource_id=r_id,
                allowed=True,
                reason="authorized_member",
            )
            for r_id in resource_ids
        ]

    async def resolve_citation(
        self,
        resource_id: str,
        revision_id: str,
        locator: TextLocator,
        *,
        tenant_id: str | None = None,
        connection_id: str | None = None,
    ) -> CitationResolution:
        """Return the user-facing URL and title for citing this resource in chat answers."""
        # TODO: Construct deep-link URL into your third-party service
        return CitationResolution(
            resource_id=resource_id,
            revision_id=revision_id,
            url=f"https://your-service.local/items/{resource_id}#offset={locator.start}",
            title=f"Item {resource_id}",
        )
