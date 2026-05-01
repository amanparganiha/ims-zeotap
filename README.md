# Incident Management System (IMS)

> **Zeotap Infrastructure / SRE Intern Assignment**
> Submitted by: Aman

**GitHub:** `<!-- ADD YOUR GITHUB LINK HERE -->`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PRODUCERS                                   │
│         (APIs, MCP Hosts, Caches, Queues, RDBMS, NoSQL)            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  HTTP POST /api/signals  (rate-limited)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    INGESTION LAYER (FastAPI)                         │
│  • Validates payload (Pydantic)                                      │
│  • Rate limiter: 6,000 req/min (slowapi)                            │
│  • Pushes to Redis Stream — returns 202 immediately                 │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  xadd  (max 100k entries, ~LRU eviction)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    REDIS STREAMS  (Buffer)                           │
│  • Absorbs 10,000+ signals/sec without blocking the HTTP layer      │
│  • Consumer group ensures at-least-once delivery                    │
│  • Acts as backpressure valve between ingestion & persistence       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  xreadgroup (batch=100, block=1s)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PROCESSOR (Async Consumer)                        │
│                                                                      │
│  ┌─ Debounce Logic ────────────────────────────────────────────┐   │
│  │  If Redis key "ims:debounce:<component_id>" exists:         │   │
│  │    → link signal to existing WorkItem (no new row)          │   │
│  │  Else:                                                       │   │
│  │    → evaluate alert strategy → create WorkItem in Postgres  │   │
│  │    → set Redis key with 10s TTL                             │   │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ Write Paths ───────────────────────────────────────────────┐   │
│  │  MongoDB  ← raw signal document (audit log)                 │   │
│  │  Postgres ← WorkItem row (source of truth, transactional)   │   │
│  │  Redis    ← dashboard cache hash per WorkItem               │   │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
         │                     │                    │
         ▼                     ▼                    ▼
  ┌────────────┐       ┌─────────────┐      ┌────────────────┐
  │  MongoDB   │       │  PostgreSQL  │      │  Redis Cache   │
  │            │       │ +TimescaleDB │      │                │
  │ Raw signal │       │  WorkItems   │      │ Dashboard hash │
  │ audit log  │       │  RCA Records │      │ Debounce keys  │
  │ (NoSQL)    │       │  Timeseries  │      │ (Hot-path)     │
  └────────────┘       └─────────────┘      └────────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │        REST API (FastAPI)        │
              │  GET  /api/incidents             │
              │  GET  /api/incidents/:id         │
              │  GET  /api/incidents/:id/signals │
              │  PATCH /api/incidents/:id/status │
              │  POST  /api/incidents/:id/rca    │
              │  GET  /health                    │
              └────────────────┬───────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │       React Frontend            │
              │  Live Feed (5s poll)            │
              │  Incident Detail + Signals      │
              │  RCA Form                       │
              └────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend framework | FastAPI + uvicorn | Async-native, auto OpenAPI docs |
| Signal buffer | Redis Streams | Handles burst traffic; consumer groups give at-least-once guarantees |
| NoSQL (audit log) | MongoDB 7 | Schema-flexible; high write throughput for raw signals |
| RDBMS (source of truth) | PostgreSQL 15 + TimescaleDB | ACID transactions for state; hypertable for timeseries aggregations |
| Cache (hot-path) | Redis Hashes | Sub-ms reads for dashboard; avoids Postgres query on every UI refresh |
| Frontend | React 18 + Vite + Tailwind | Fast dev, small bundle |
| Container orchestration | Docker Compose | Single-command startup |

---

## How Backpressure Is Handled

This is the core resilience design decision:

```
Producer → [FastAPI] → Redis Stream → [Consumer] → Postgres / Mongo
               ↑                           ↑
          Always fast                 Can be slow
          (202 Accepted)         (DB writes, retries)
```

1. **Redis Streams as a decoupling buffer** — the ingestion API writes to Redis (`xadd`) and immediately returns `202 Accepted`. It never waits for Postgres or MongoDB.
2. **Stream size cap** — `MAXLEN ~100_000` prevents unbounded memory growth. Oldest unprocessed entries are evicted under extreme load.
3. **Consumer group** — `xreadgroup` with `block=1000ms` means the consumer yields the event loop when idle. Under load it reads in batches of 100 for efficiency.
4. **At-least-once delivery** — signals are only `xack`'d after successful processing. A DB failure leaves the message in the pending list for redelivery.
5. **Rate limiter** — 6,000 req/min (100/sec) on the ingestion API prevents a single client from overwhelming the system.

---

## Design Patterns Used

### Strategy Pattern — Alerting
`backend/workflow/alerting.py`

Each component type has its own `AlertStrategy` subclass. Adding a new component type requires zero changes to existing code — just add a new strategy and register it.

```python
class AlertStrategy(ABC):
    def evaluate(self, ctx: AlertContext) -> AlertResult: ...

class RDBMSAlertStrategy(AlertStrategy):  # → P0
class MCPHostAlertStrategy(AlertStrategy): # → P1
class CacheAlertStrategy(AlertStrategy):   # → P2
class APIAlertStrategy(AlertStrategy):     # → P1
```

### State Pattern — Incident Lifecycle
`backend/workflow/states.py`

Legal transitions are encoded in each state object. The `CLOSED` state is terminal. Transitioning to `CLOSED` without an RCA is rejected at the API layer before the state machine is even consulted.

```
OPEN → INVESTIGATING → RESOLVED → CLOSED (terminal)
              ↑______________↑  (can revert if needed)
```

---

## Non-Functional Items (Bonus Points)

| Feature | Implementation |
|---|---|
| **Rate Limiting** | `slowapi` decorator on `/api/signals` — 6,000 req/min |
| **Throughput Observability** | Background task logs `signals/sec` every 5 seconds |
| **Health Endpoint** | `GET /health` checks Postgres, MongoDB, Redis connectivity |
| **Retry on DB failure** | Signals not `xack`'d on `SQLAlchemyError` → auto-redelivered |
| **CORS** | Configurable via `CORS_ORIGINS` env var |
| **TimescaleDB** | `signal_metrics` hypertable enables efficient time-range queries |
| **Connection pooling** | Postgres: pool_size=20; Redis: max_connections=50; Mongo: maxPoolSize=50 |
| **Idempotent RCA** | Duplicate RCA submissions return `409 Conflict` |
| **Docker health checks** | All services have healthchecks; backend waits for healthy DBs |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (for running scripts locally)

### 1. Clone and start

```bash
git clone <YOUR_GITHUB_URL>
cd ims
docker compose up --build
```

Services start in order: Postgres → Mongo → Redis → Backend → Frontend

### 2. Verify everything is running

```bash
curl http://localhost:8000/health
# {"status":"healthy","postgres":"ok","mongo":"ok","redis":"ok",...}
```

Open the dashboard: **http://localhost:5173**
API docs: **http://localhost:8000/docs**

### 3. Run the mock failure scenario

```bash
pip install httpx
python scripts/mock_failure.py --url http://localhost:8000 --scenario full
```

This simulates:
- RDBMS primary outage (150 signals → 1 WorkItem due to debounce)
- MCP Host cascade failure
- Cache stampede (80 signals → 1 WorkItem)
- API gateway errors

### 4. Run unit tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_URL` | `postgresql+asyncpg://...` | Postgres connection string |
| `MONGO_URL` | `mongodb://...` | MongoDB connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `DEBOUNCE_WINDOW_SECONDS` | `10` | Debounce window per component |
| `DEBOUNCE_THRESHOLD` | `100` | Signals before dedup kicks in |
| `RATE_LIMIT_PER_MINUTE` | `6000` | Max requests per minute on ingestion |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Repository Structure

```
ims/
├── backend/
│   ├── api/            # FastAPI routers (incidents, health)
│   ├── core/           # Config, DB connection lifecycle
│   ├── ingestion/      # Signal ingestion endpoint + metrics
│   ├── models/         # SQLAlchemy ORM + Pydantic schemas
│   ├── processor/      # Redis stream consumer + debounce logic
│   ├── tests/          # Unit tests (RCA, state machine, alerting)
│   ├── workflow/       # State pattern + Strategy pattern
│   ├── main.py         # App entrypoint, lifecycle hooks
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/        # Axios client
│       ├── components/ # SeverityBadge, HealthBar
│       ├── hooks/      # useIncidents, useHealth
│       └── pages/      # Dashboard, IncidentDetail, RCAForm
├── scripts/
│   ├── init_postgres.sql   # DB schema + TimescaleDB setup
│   └── mock_failure.py     # Failure simulator
├── docker-compose.yml
└── README.md
```

---

## Prompts & Planning

All planning notes, prompts used, and architecture decisions are documented in [`docs/PROMPTS.md`](docs/PROMPTS.md).
