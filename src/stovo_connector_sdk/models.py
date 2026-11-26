"""Data models and schemas for Stovo Connector Protocol."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class SourceEventKind(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACL_CHANGE = "acl_change"
    MOVE = "move"
    RESTORE = "restore"


class AuthorizationOperation(str, Enum):
    READ = "read"
    INGEST = "ingest"
    MODEL_TRANSFER = "model_transfer"
    EXPORT = "export"
    CODEX = "codex"
    REPLY = "reply"


class ScopeItem(BaseModel):
    tenant_id: str
    connection_id: str


class ResourceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    connection_id: str
    resource_id: str
    revision_id: str
    content_revision_id: str
    metadata_revision_id: str
    observed_at: datetime
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "v1"
    event_id: str
    tenant_id: str
    connection_id: str
    resource_id: str
    revision_id: str
    order_token: str
    source_sequence: int
    container_id: str
    observed_at: datetime
    kind: SourceEventKind = SourceEventKind.CREATE
    policy_refs: list[str] = Field(default_factory=list)


class TextLocator(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class AuthorizationDecision(BaseModel):
    resource_id: str
    allowed: bool
    reason: str | None = None
    policy_revision: str = "1"


class CitationResolution(BaseModel):
    resource_id: str
    revision_id: str
    url: str
    title: str = ""
    snippet: str = ""


class BackfillResponse(BaseModel):
    snapshots: list[ResourceSnapshot]
    cursor: str | None = None
    fence_cursor: str | None = None
    scope_reset: bool = False
    backfill_id: str | None = None


class EventsResponse(BaseModel):
    events: list[SourceEvent]
    cursor: str
    has_more: bool = False


class AuthorizeRequest(BaseModel):
    schema_version: str = "v1"
    principal_id: str
    operation: AuthorizationOperation
    resource_ids: list[str]


class AuthorizeResponse(BaseModel):
    decisions: list[AuthorizationDecision]


class CitationRequest(BaseModel):
    resource_id: str
    revision_id: str
    start: int
    end: int
