# Stovo Connector SDK

Python SDK for building out-of-process data source connectors (Notion, Jira, Slack, Google Drive, GitLab, etc.) that connect directly to an already-running **Stovo Insight** instance without modifying its core code.

---

## Architecture Overview

```
   ┌────────────────────────┐                    ┌────────────────────────┐
   │     Stovo Insight      │                    │    Custom Connector    │
   │      (Core RAG)        │                    │  (e.g., Notion / Jira) │
   │                        │                    │                        │
   │  ┌──────────────────┐  │    HTTP Backfill   │  ┌──────────────────┐  │
   │  │RemoteSourceAdapter│──┼───────────────────>│  │  /backfill/begin │  │
   │  └──────────────────┘  │    Event Stream    │  │  /events         │  │
   │                        │                    │  └──────────────────┘  │
   │                        │   Live ACL Check   │  ┌──────────────────┐  │
   │                        │───────────────────>│  │ /authorization:  │  │
   │                        │    (on search)     │  │   check          │  │
   │                        │                    │  └──────────────────┘  │
   └────────────────────────┘                    └────────────────────────┘
```

1. **Standalone Microservice**: Your connector runs anywhere (Docker container, Kubernetes pod, VM) and exposes standard HTTP endpoints.
2. **Zero Core Modifications**: Stovo Insight connects to your connector endpoint using `RemoteSourceAdapter`.
3. **Source-Authoritative Permissions**: Stovo Insight never stores third-party ACL matrices. When a user performs a search, Insight queries your connector (`/authorization:check`) in real time to verify whether the requesting principal is authorized to see the cited documents.

---

## Installation

```bash
pip install stovo-connector-sdk
```

---

## Quickstart in 3 Steps

### 1. Subclass `BaseConnector`

Create `my_connector.py`:

```python
from datetime import datetime, timezone
from typing import Sequence
from stovo_connector_sdk import (
    BaseConnector,
    ResourceSnapshot,
    BackfillResponse,
    EventsResponse,
    AuthorizationOperation,
    AuthorizationDecision,
    CitationResolution,
    TextLocator,
)

class JiraConnector(BaseConnector):
    async def get_scopes(self) -> list[tuple[str, str]]:
        # Returns (tenant_id, connection_id) pairs
        return [("tenant-myorg", "conn-jira-cloud")]

    async def begin_backfill(
        self, tenant_id: str, connection_id: str, *, page_size: int = 100
    ) -> BackfillResponse:
        # Fetch initial historical issues/pages
        snapshots = [
            ResourceSnapshot(
                tenant_id=tenant_id,
                connection_id=connection_id,
                resource_id="PROJ-101",
                revision_id="rev-1",
                content_revision_id="rev-1",
                metadata_revision_id="rev-1",
                observed_at=datetime.now(timezone.utc),
                content="Bug: Login button unresponsive on mobile viewports.",
                metadata={"title": "PROJ-101: Login Bug", "container_id": "PROJ"},
            )
        ]
        return BackfillResponse(
            snapshots=snapshots,
            cursor="done",
            fence_cursor="fence-101",
        )

    async def continue_backfill(
        self, cursor: str, *, page_size: int = 100, **kwargs
    ) -> BackfillResponse:
        return BackfillResponse(snapshots=[], cursor=None)

    async def list_events(
        self, cursor: str, *, limit: int = 100, **kwargs
    ) -> EventsResponse:
        # Poll Jira changelog for incremental updates
        return EventsResponse(events=[], cursor=cursor, has_more=False)

    async def get_snapshot(
        self, resource_id: str, revision_id: str, **kwargs
    ) -> ResourceSnapshot:
        # Fetch exact version of the issue
        ...

    async def bulk_authorize(
        self,
        principal_id: str,
        operation: AuthorizationOperation,
        resource_ids: Sequence[str],
        **kwargs,
    ) -> list[AuthorizationDecision]:
        # Source-Authoritative ACL check: ask Jira if principal_id has access
        return [
            AuthorizationDecision(
                resource_id=r_id,
                allowed=True,
                reason="jira_project_member",
            )
            for r_id in resource_ids
        ]

    async def resolve_citation(
        self, resource_id: str, revision_id: str, locator: TextLocator, **kwargs
    ) -> CitationResolution:
        return CitationResolution(
            resource_id=resource_id,
            revision_id=revision_id,
            url=f"https://myorg.atlassian.net/browse/{resource_id}",
            title=f"Jira issue {resource_id}",
        )


if __name__ == "__main__":
    JiraConnector.serve(host="0.0.0.0", port=8080, auth_token="my-shared-secret")
```

### 2. Run your connector

```bash
python my_connector.py
```

### 3. Validate with the SDK CLI

Run contract tests against your live connector before connecting to Insight:

```bash
stovo-connector test http://localhost:8080 --token my-shared-secret
```

Output:
```text
Validating connector at: http://localhost:8080

  [PASS] GET /scopes (1 scopes discovered)
  [PASS] GET /backfill/begin (1 snapshots returned)
  [PASS] GET /events 
  [PASS] GET /resources/PROJ-101/snapshot 
  [PASS] POST /authorization:check 
  [PASS] POST /citations:resolve 

Summary: 6 passed, 0 failed
```

---

## Connecting to Stovo Insight

Once your connector is running:
1. In Stovo Insight Admin Console or API, add a new **Connection**.
2. Specify the endpoint URL (e.g. `http://jira-connector:8080`) and your Bearer Auth Token.
3. Insight's `RemoteSourceAdapter` will automatically start ingesting data and querying your service for authorization checks during search.

---

## License

Apache-2.0
