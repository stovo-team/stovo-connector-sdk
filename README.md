# Stovo Connector SDK & Multi-Connector Host

[![CI](https://github.com/stovo-team/stovo-connector-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/stovo-team/stovo-connector-sdk/actions/workflows/ci.yml)
[![Template](https://img.shields.io/badge/GitHub-Template_Repository-blue.svg)](https://github.com/stovo-team/stovo-connector-sdk/generate)

Python SDK and multi-tenant host runner for building **out-of-process data source connectors** (Jira, Notion, Slack, Google Drive, Confluence, GitLab, etc.) for **Stovo Insight**.

Connectors connect to an already-running Stovo Insight instance over standard HTTP/JSON or Unix Domain Sockets — **no modifications or recompilation of Stovo Insight core required**.

---

## Key Features

1. **Multi-Connector Host (Zero Container Bloat)**:
   Host 10–50 connectors in a **single lightweight process/container** (~50MB RAM). No heavy Docker container per connector.
2. **Zero Core Recompilation**:
   Connectors are standalone modules. You can add or update connectors dynamically without touching the Rust worker or core indexing engine.
3. **Unix Domain Socket (UDS) & HTTP Support**:
   Connectors can run over local Unix sockets (`/var/run/stovo/connectors.sock`) for near-zero latency and zero open network ports, or standard HTTP.
4. **Source-Authoritative Real-Time Authorization**:
   Stovo Insight asks your connector (`POST /authorization:check`) in real time (2–5ms) on search queries.

---

## Architecture

```
   ┌────────────────────────────────┐                    ┌──────────────────────────────────────────┐
   │        Stovo Insight           │                    │         Stovo Connector Host             │
   │         (Core Engine)          │                    │     (Single Process / ~50MB RAM)         │
   │                                │                    │                                          │
   │  ┌──────────────────────────┐  │   HTTP or UDS      │  ┌────────────────────────────────────┐  │
   │  │   RemoteSourceAdapter    │──┼───────────────────>│  │ Multi-Connector ASGI Router        │  │
   │  └──────────────────────────┘  │                    │  └──────┬──────────────┬──────────────┘  │
   │                                │                    │         │              │                 │
   │                                │                    │  ┌──────▼──────┐┌──────▼──────┐          │
   │                                │                    │  │ JiraConnector││NotionConnector│ ...   │
   │                                │                    │  └─────────────┘└─────────────┘          │
   └────────────────────────────────┘                    └──────────────────────────────────────────┘
```

---

## Quick Start: Creating a New Connector

### 1. Scaffold a project in 2 seconds

```bash
pip install stovo-connector-sdk
stovo-connector init jira
```

This generates:
```text
stovo-connector-jira/
├── connector.py           # Core implementation inheriting BaseConnector
├── pyproject.toml         # Packaging & entry point registration
├── README.md
└── tests/
    └── test_connector.py  # Unit tests
```

### 2. Implement your connector logic in `connector.py`

```python
from stovo_connector_sdk import BaseConnector, ScopeItem, BackfillResponse, EventsResponse, ResourceSnapshot

class JiraConnector(BaseConnector):
    kind = "jira"

    async def get_scopes(self) -> list[tuple[str, str]]:
        return [("workspace-acme", "conn-jira-prod")]

    async def begin_backfill(self, tenant_id: str, connection_id: str, *, page_size: int = 100) -> BackfillResponse:
        ...

    async def list_events(self, cursor: str, *, limit: int = 100, **kwargs) -> EventsResponse:
        ...

    async def bulk_authorize(self, principal_id: str, operation, resource_ids, **kwargs):
        ...
```

---

## Running with the Multi-Connector Host

### Option A: Via CLI (Local / Development)

Place your connector modules in a `./connectors` folder:

```bash
# Scan directory and host all connectors on HTTP
stovo-connector host --dir ./connectors --port 8080 --token my-secret

# Or run over a Unix Domain Socket (zero open ports)
stovo-connector host --dir ./connectors --uds /var/run/stovo/connectors.sock --token my-secret
```

Each connector is automatically mounted at `/connectors/{kind}/*`:
- `GET  /connectors/jira/scopes`
- `GET  /connectors/jira/backfill/begin`
- `POST /connectors/jira/authorization:check`

Clients sending `X-Connector-Kind: jira` can also query the root endpoints directly.

### Option B: Via Docker Compose (Single Container)

```yaml
services:
  connectors-host:
    image: stovo-connector-host:latest
    ports:
      - "8080:8080"
    volumes:
      - ./connectors:/connectors:ro
    environment:
      - CONNECTOR_AUTH_TOKEN=my-secret
    restart: unless-stopped
```

---

## Validating with the SDK CLI

Before connecting to Stovo Insight, validate your connector against the protocol suite:

```bash
stovo-connector test http://localhost:8080/connectors/jira --token my-secret
```

Output:
```text
Validating connector at: http://localhost:8080/connectors/jira

  [PASS] GET /scopes (1 scopes discovered)
  [PASS] GET /backfill/begin (1 snapshots returned)
  [PASS] GET /events
  [PASS] GET /resources/sample-1/snapshot
  [PASS] POST /authorization:check
  [PASS] POST /citations:resolve

Summary: 6 passed, 0 failed
```

---

## Connecting to Stovo Insight

In Stovo Insight:
- **Connector Type**: `custom` (or `RemoteSourceAdapter`)
- **Endpoint URL**: `http://connectors-host:8080/connectors/jira` (or `unix:///var/run/stovo/connectors.sock`)
- **Bearer Token**: `my-secret`

---

## Automated Tests

Run test suite:
```bash
pytest
```

---

## License

Apache-2.0
