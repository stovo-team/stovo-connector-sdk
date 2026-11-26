# Stovo Connector Template & SDK

[![CI](https://github.com/stovo-team/stovo-connector-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/stovo-team/stovo-connector-sdk/actions/workflows/ci.yml)
[![Template](https://img.shields.io/badge/GitHub-Template_Repository-blue.svg)](https://github.com/stovo-team/stovo-connector-sdk/generate)

Starter template repository and Python SDK for building **out-of-process data source connectors** (Jira, Notion, Slack, Google Drive, Confluence, GitLab, etc.) for **Stovo Insight**.

Connectors built with this template run as independent microservices and connect to an already-running Stovo Insight instance over standard HTTP/JSON — **no modifications to Stovo Insight core required**.

---

## How It Works

```
   ┌────────────────────────────────┐                    ┌────────────────────────────────┐
   │        Stovo Insight           │                    │     Your Custom Connector      │
   │         (Core RAG)             │                    │     (Built from Template)      │
   │                                │                    │                                │
   │  ┌──────────────────────────┐  │    1. Backfill     │  ┌──────────────────────────┐  │
   │  │   RemoteSourceAdapter    │──┼───────────────────>│  │ GET  /backfill/begin     │  │
   │  └──────────────────────────┘  │    2. Incremental  │  │ GET  /events             │  │
   │                                │                    │  └──────────────────────────┘  │
   │                                │    3. Live Access  │  ┌──────────────────────────┐  │
   │                                │───────────────────>│  │ POST /authorization:check│  │
   │                                │     (on search)    │  └──────────────────────────┘  │
   └────────────────────────────────┘                    └────────────────────────────────┘
```

1. **Standalone Microservice**: Deploy anywhere (Docker container, Kubernetes pod, or serverless VM).
2. **Source-Authoritative Security**: Stovo Insight never stores third-party ACL matrices. When a user runs a search query, Insight asks your connector (`POST /authorization:check`) in real time to verify whether the user is allowed to read the cited resources.
3. **Point-in-Time Provenance**: Every document revision carries container identifiers and observation timestamps for grounded answers.

---

## Getting Started

### 1. Create your repository from this template

Click the green **[Use this template](https://github.com/stovo-team/stovo-connector-sdk/generate)** button on GitHub, or clone locally:

```bash
git clone https://github.com/stovo-team/stovo-connector-sdk.git my-jira-connector
cd my-jira-connector
```

### 2. Set up environment

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment configuration
cp .env.example .env
```

### 3. Implement your connector logic in `connector.py`

Open [`connector.py`](connector.py) and fill in the methods for your target system:

| Method to implement | Description |
|---|---|
| `get_scopes()` | Return active `(tenant_id, connection_id)` pairs served by this connector. |
| `begin_backfill()` | Fetch the first page of historical documents/messages and return snapshots + cursor. |
| `continue_backfill()` | Fetch subsequent pages of historical data using opaque cursors until `cursor is None`. |
| `list_events()` | Stream incremental change events (`CREATE`, `UPDATE`, `DELETE`, `ACL_CHANGE`). |
| `get_snapshot()` | Fetch the exact content and metadata for a specific document revision. |
| `bulk_authorize()` | Verify in real time whether `principal_id` has access to each resource ID. |
| `resolve_citation()` | Return deep-link URLs and titles for cited resources in chat answers. |

### 4. Run the connector locally

```bash
python main.py
```

The service will start on `http://0.0.0.0:8080`.

---

## Validating with the SDK CLI

Before connecting to a live Stovo Insight instance, test your connector against the full protocol conformance test suite:

```bash
stovo-connector test http://localhost:8080 --token test-secret
```

Output:
```text
Validating connector at: http://localhost:8080

  [PASS] GET /scopes (1 scopes discovered)
  [PASS] GET /backfill/begin (1 snapshots returned)
  [PASS] GET /events 
  [PASS] GET /resources/sample-item-1/snapshot 
  [PASS] POST /authorization:check 
  [PASS] POST /citations:resolve 

Summary: 6 passed, 0 failed
```

---

## Production Deployment

### Using Docker Compose

```bash
# Build and run container in background
docker compose up -d
```

### Dockerfile

A production-ready minimal container image is provided in [`Dockerfile`](Dockerfile). Build with:

```bash
docker build -t my-custom-connector .
docker run -p 8080:8080 -e CONNECTOR_AUTH_TOKEN="my-secret" my-custom-connector
```

---

## Connecting to Stovo Insight

Once your connector is running:

1. Open Stovo Insight Admin Console or call the Connections API:
   - **Connector Type**: `custom` (or your registered `ConnectorKind`)
   - **Endpoint URL**: `http://my-connector-host:8080` (or `https://...`)
   - **Bearer Token**: `my-shared-secret`
2. Stovo Insight's `RemoteSourceAdapter` will immediately:
   - Discover scopes via `GET /scopes`
   - Ingest historical data via `GET /backfill/begin`
   - Stream real-time changes via `GET /events`
   - Validate live user permissions via `POST /authorization:check` on every search query.

---

## Protocol Specification

Your connector service implements these HTTP/JSON endpoints:

| Endpoint | Method | Headers | Description |
|---|---|---|---|
| `/scopes` | `GET` | `Authorization: Bearer <token>` | Discovers active tenant and connection scopes. |
| `/backfill/begin` | `GET` | `X-Tenant-ID`, `X-Connection-ID` | Starts historical snapshot backfill. |
| `/backfill/continue` | `GET` | `X-Tenant-ID`, `X-Connection-ID` | Continues backfill via `?cursor=...`. |
| `/events` | `GET` | `X-Tenant-ID`, `X-Connection-ID` | Polls incremental change stream via `?cursor=...`. |
| `/resources/{id}/snapshot` | `GET` | `X-Tenant-ID`, `X-Connection-ID` | Fetches exact content for revision `?revision_id=...`. |
| `/authorization:check` | `POST` | `X-Tenant-ID`, `X-Connection-ID` | Checks real-time ACL permissions for a principal. |
| `/citations:resolve` | `POST` | `X-Tenant-ID`, `X-Connection-ID` | Resolves text offset locators to source URLs. |

---

## Running Automated Tests

```bash
PYTHONPATH=src:. pytest tests/
```

---

## License

Apache-2.0
