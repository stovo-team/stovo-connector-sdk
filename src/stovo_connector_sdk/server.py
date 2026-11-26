"""FastAPI HTTP service mounting Stovo Connector Protocol endpoints."""

from __future__ import annotations

from typing import Annotated
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse

from .base import BaseConnector
from .models import (
    AuthorizeRequest,
    AuthorizeResponse,
    BackfillResponse,
    CitationRequest,
    CitationResolution,
    EventsResponse,
    ResourceSnapshot,
    ScopeItem,
    TextLocator,
)


def create_connector_app(connector: BaseConnector, auth_token: str | None = None) -> FastAPI:
    """Create a FastAPI application serving the Stovo Connector Protocol."""
    app = FastAPI(title="Stovo External Connector", version="0.1.0")

    async def verify_auth(authorization: Annotated[str | None, Header()] = None) -> None:
        if auth_token is None:
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Bearer authorization header",
            )
        token = authorization.removeprefix("Bearer ").strip()
        if token != auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization token",
            )

    @app.get("/scopes", response_model=dict[str, list[ScopeItem]], dependencies=[Depends(verify_auth)])
    async def get_scopes():
        scopes = await connector.get_scopes()
        return {"scopes": [ScopeItem(tenant_id=t, connection_id=c) for t, c in scopes]}

    @app.get("/backfill/begin", response_model=BackfillResponse, dependencies=[Depends(verify_auth)])
    async def begin_backfill(
        page_size: int = Query(default=100, ge=1, le=1000),
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        if not x_tenant_id or not x_connection_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Tenant-ID and X-Connection-ID headers are required for backfill",
            )
        return await connector.begin_backfill(x_tenant_id, x_connection_id, page_size=page_size)

    @app.get("/backfill/continue", response_model=BackfillResponse, dependencies=[Depends(verify_auth)])
    async def continue_backfill(
        cursor: str = Query(...),
        page_size: int = Query(default=100, ge=1, le=1000),
        backfill_id: str | None = Query(default=None),
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        return await connector.continue_backfill(
            cursor,
            page_size=page_size,
            backfill_id=backfill_id,
            tenant_id=x_tenant_id,
            connection_id=x_connection_id,
        )

    @app.get("/events", response_model=EventsResponse, dependencies=[Depends(verify_auth)])
    async def list_events(
        cursor: str = Query(...),
        limit: int = Query(default=100, ge=1, le=1000),
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        return await connector.list_events(
            cursor,
            limit=limit,
            tenant_id=x_tenant_id,
            connection_id=x_connection_id,
        )

    @app.get("/changes", dependencies=[Depends(verify_auth)])
    async def list_changes(
        after_sequence: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1000),
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        if not x_tenant_id or not x_connection_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Tenant-ID and X-Connection-ID headers are required for list_changes",
            )
        events = await connector.list_changes(
            x_tenant_id, x_connection_id, after_sequence=after_sequence, limit=limit
        )
        return {"events": [e.model_dump(mode="json") for e in events]}

    @app.get(
        "/resources/{resource_id}/snapshot",
        response_model=ResourceSnapshot,
        dependencies=[Depends(verify_auth)],
    )
    async def get_snapshot(
        resource_id: str,
        revision_id: str = Query(...),
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        return await connector.get_snapshot(
            resource_id,
            revision_id,
            tenant_id=x_tenant_id,
            connection_id=x_connection_id,
        )

    @app.post(
        "/authorization:check",
        response_model=AuthorizeResponse,
        dependencies=[Depends(verify_auth)],
    )
    async def bulk_authorize(
        req: AuthorizeRequest,
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        decisions = await connector.bulk_authorize(
            req.principal_id,
            req.operation,
            req.resource_ids,
            tenant_id=x_tenant_id,
            connection_id=x_connection_id,
        )
        return AuthorizeResponse(decisions=decisions)

    @app.post(
        "/citations:resolve",
        response_model=CitationResolution,
        dependencies=[Depends(verify_auth)],
    )
    async def resolve_citation(
        req: CitationRequest,
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        locator = TextLocator(start=req.start, end=req.end)
        return await connector.resolve_citation(
            req.resource_id,
            req.revision_id,
            locator,
            tenant_id=x_tenant_id,
            connection_id=x_connection_id,
        )

    return app
