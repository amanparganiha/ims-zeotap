# Planning Notes & Prompts

This document records the design decisions, prompts, and reasoning used to build the IMS.

## Approach

The assignment was broken down into layers:
1. **Data flow first** — designed the signal path (Ingestion → Redis → Consumer → DBs) before writing code
2. **Failure modes second** — designed for what happens when Postgres is slow, when Redis is full, when signals burst
3. **Patterns third** — mapped Strategy and State patterns to the specific problem

## Key Design Decisions

### Why Redis Streams over Kafka?
Kafka would be production-grade here, but Redis Streams gives:
- Zero additional infrastructure (Redis is already used for cache)
- Consumer groups with at-least-once delivery
- Simple `xadd`/`xreadgroup` API
- Sufficient for 10k signals/sec on a single node

### Why TimescaleDB over a dedicated TSDB?
TimescaleDB runs as a Postgres extension — no extra container. Hypertables give time-based partitioning and `time_bucket()` for aggregations. Adding InfluxDB would add ops overhead for marginal benefit at this scale.

### Debounce Implementation
Used Redis SETEX (key with TTL) rather than a sorted set or Lua script for simplicity:
- `ims:debounce:<component_id>` → `<work_item_uuid>`, TTL=10s
- Atomic get-then-set isn't needed here since we're just reading an ID

### MTTR Calculation
Calculated at `CLOSED` state entry: `now - work_item.created_at`. `created_at` represents the first signal received (the real incident start from the system's perspective), not the RCA `incident_start` which is human-reported.

## Prompts Used
- System design walkthrough with Claude to validate tech stack choices
- Claude used to scaffold boilerplate (FastAPI lifespan, SQLAlchemy async session pattern)
- All business logic (debounce, state machine, strategy pattern) hand-written
