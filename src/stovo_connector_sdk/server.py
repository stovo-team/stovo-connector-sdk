"""FastAPI HTTP service mounting Stovo Connector Protocol endpoints."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Callable
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request, status
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


def _build_auth_verifier(auth_token: str | None) -> Callable[..., Any]:
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

    return verify_auth


def create_connector_router(
    connector: BaseConnector,
    verify_auth: Any | None = None,
) -> APIRouter:
    """Create an APIRouter implementing the Stovo Connector Protocol for a single connector."""
    dependencies = [Depends(verify_auth)] if verify_auth else []
    router = APIRouter(dependencies=dependencies)

    @router.get("/scopes", response_model=dict[str, list[ScopeItem]])
    async def get_scopes():
        scopes = await connector.get_scopes()
        return {"scopes": [ScopeItem(tenant_id=t, connection_id=c) for t, c in scopes]}

    @router.get("/backfill/begin", response_model=BackfillResponse)
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

    @router.get("/backfill/continue", response_model=BackfillResponse)
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

    @router.get("/events", response_model=EventsResponse)
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

    @router.get("/changes")
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

    @router.get("/resources/{resource_id}/snapshot", response_model=ResourceSnapshot)
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

    @router.post("/authorization:check", response_model=AuthorizeResponse)
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

    @router.post("/citations:resolve", response_model=CitationResolution)
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

    return router


def create_connector_app(connector: BaseConnector, auth_token: str | None = None) -> FastAPI:
    """Create a FastAPI application serving the Stovo Connector Protocol for a single connector."""
    app = FastAPI(title="Stovo External Connector", version="0.1.0")
    verify_auth = _build_auth_verifier(auth_token)
    router = create_connector_router(connector, verify_auth=verify_auth)
    app.include_router(router)
    return app


def create_multi_connector_app(
    connectors: Mapping[str, BaseConnector] | Sequence[BaseConnector],
    auth_token: str | None = None,
) -> FastAPI:
    """Create a FastAPI application serving multiple connectors in a single process.

    Each connector is accessible under `/connectors/{kind}/*`.
    In addition, root endpoints can route using `X-Connector-Kind` header.
    """
    app = FastAPI(title="Stovo Multi-Connector Host", version="0.1.0")
    verify_auth = _build_auth_verifier(auth_token)

    # Normalize to dictionary {kind: connector}
    connector_map: dict[str, BaseConnector] = {}
    if isinstance(connectors, Mapping):
        connector_map = dict(connectors)
    else:
        for c in connectors:
            k = getattr(c, "kind", None) or c.__class__.__name__.lower().removesuffix("connector")
            connector_map[k] = c

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "connectors": list(connector_map.keys()),
        }

    @app.get("/connectors", dependencies=[Depends(verify_auth)])
    async def list_connectors():
        return {
            "connectors": list(connector_map.keys()),
        }

    # Mount per-connector routers under /connectors/{kind}
    for kind, conn in connector_map.items():
        router = create_connector_router(conn, verify_auth=verify_auth)
        app.include_router(router, prefix=f"/connectors/{kind}", tags=[kind])

    # Helper to resolve connector for root fallback
    def _resolve_connector(
        x_connector_kind: str | None = None,
        connector_param: str | None = None,
    ) -> BaseConnector:
        target_kind = x_connector_kind or connector_param
        if target_kind:
            if target_kind not in connector_map:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Connector '{target_kind}' not found on this host",
                )
            return connector_map[target_kind]

        if len(connector_map) == 1:
            return next(iter(connector_map.values()))

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Connector-Kind header is required when multiple connectors are hosted",
        )

    # Root fallback endpoints with header-based dispatch
    @app.get("/scopes", response_model=dict[str, list[ScopeItem]], dependencies=[Depends(verify_auth)])
    async def root_scopes(
        x_connector_kind: Annotated[str | None, Header(alias="X-Connector-Kind")] = None,
        connector: str | None = Query(default=None),
    ):
        conn = _resolve_connector(x_connector_kind, connector)
        scopes = await conn.get_scopes()
        return {"scopes": [ScopeItem(tenant_id=t, connection_id=c) for t, c in scopes]}

    @app.get("/backfill/begin", response_model=BackfillResponse, dependencies=[Depends(verify_auth)])
    async def root_begin_backfill(
        page_size: int = Query(default=100, ge=1, le=1000),
        x_connector_kind: Annotated[str | None, Header(alias="X-Connector-Kind")] = None,
        connector: str | None = Query(default=None),
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        conn = _resolve_connector(x_connector_kind, connector)
        if not x_tenant_id or not x_connection_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Tenant-ID and X-Connection-ID headers are required for backfill",
            )
        return await conn.begin_backfill(x_tenant_id, x_connection_id, page_size=page_size)

    @app.get("/backfill/continue", response_model=BackfillResponse, dependencies=[Depends(verify_auth)])
    async def root_continue_backfill(
        cursor: str = Query(...),
        page_size: int = Query(default=100, ge=1, le=1000),
        backfill_id: str | None = Query(default=None),
        x_connector_kind: Annotated[str | None, Header(alias="X-Connector-Kind")] = None,
        connector: str | None = Query(default=None),
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        conn = _resolve_connector(x_connector_kind, connector)
        return await conn.continue_backfill(
            cursor,
            page_size=page_size,
            backfill_id=backfill_id,
            tenant_id=x_tenant_id,
            connection_id=x_connection_id,
        )

    @app.get("/events", response_model=EventsResponse, dependencies=[Depends(verify_auth)])
    async def root_list_events(
        cursor: str = Query(...),
        limit: int = Query(default=100, ge=1, le=1000),
        x_connector_kind: Annotated[str | None, Header(alias="X-Connector-Kind")] = None,
        connector: str | None = Query(default=None),
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        conn = _resolve_connector(x_connector_kind, connector)
        return await conn.list_events(
            cursor,
            limit=limit,
            tenant_id=x_tenant_id,
            connection_id=x_connection_id,
        )

    @app.post("/authorization:check", response_model=AuthorizeResponse, dependencies=[Depends(verify_auth)])
    async def root_bulk_authorize(
        req: AuthorizeRequest,
        x_connector_kind: Annotated[str | None, Header(alias="X-Connector-Kind")] = None,
        connector: str | None = Query(default=None),
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        conn = _resolve_connector(x_connector_kind, connector)
        decisions = await conn.bulk_authorize(
            req.principal_id,
            req.operation,
            req.resource_ids,
            tenant_id=x_tenant_id,
            connection_id=x_connection_id,
        )
        return AuthorizeResponse(decisions=decisions)

    @app.post("/citations:resolve", response_model=CitationResolution, dependencies=[Depends(verify_auth)])
    async def root_resolve_citation(
        req: CitationRequest,
        x_connector_kind: Annotated[str | None, Header(alias="X-Connector-Kind")] = None,
        connector: str | None = Query(default=None),
        x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
        x_connection_id: Annotated[str | None, Header(alias="X-Connection-ID")] = None,
    ):
        conn = _resolve_connector(x_connector_kind, connector)
        locator = TextLocator(start=req.start, end=req.end)
        return await conn.resolve_citation(
            req.resource_id,
            req.revision_id,
            locator,
            tenant_id=x_tenant_id,
            connection_id=x_connection_id,
        )

    return app
