#!/usr/bin/env python3
"""
Mock Failure Simulator
======================
Simulates a realistic cascade:
  1. RDBMS outage (P0) — fires 150 signals over 12 seconds
  2. MCP Host failure (P1) — triggered by DB unavailability
  3. Cache invalidation storm (P2) — cache tries to compensate
  4. API gateway errors (P1) — customer-facing impact

Usage:
    python scripts/mock_failure.py --url http://localhost:8000 --scenario full
"""
import argparse
import asyncio
import json
import random
import time
import httpx


BASE_URL = "http://localhost:8000"

# ── Signal templates ──────────────────────────────────────────────────────────
SCENARIOS = {
    "rdbms_outage": [
        {
            "component_id": "RDBMS_PRIMARY_01",
            "component_type": "RDBMS",
            "error_code": "CONNECTION_REFUSED",
            "message": "Primary database connection refused on port 5432",
            "latency_ms": None,
            "metadata": {"host": "db-primary-01", "port": 5432, "db": "prod"},
        },
        {
            "component_id": "RDBMS_REPLICA_01",
            "component_type": "RDBMS",
            "error_code": "REPLICATION_LAG",
            "message": "Replica lag exceeded 30s — read queries failing",
            "latency_ms": 30000,
            "metadata": {"host": "db-replica-01", "lag_seconds": 30},
        },
    ],
    "mcp_failure": [
        {
            "component_id": "MCP_HOST_CLUSTER_A",
            "component_type": "MCP_HOST",
            "error_code": "UPSTREAM_UNAVAILABLE",
            "message": "MCP host cannot reach upstream RDBMS — circuit breaker OPEN",
            "latency_ms": None,
            "metadata": {"circuit_breaker": "OPEN", "upstream": "RDBMS_PRIMARY_01"},
        },
    ],
    "cache_storm": [
        {
            "component_id": "CACHE_CLUSTER_01",
            "component_type": "CACHE",
            "error_code": "CACHE_STAMPEDE",
            "message": "Cache stampede detected — 10k simultaneous misses",
            "latency_ms": 850,
            "metadata": {"miss_rate": "98%", "evictions_per_sec": 5000},
        },
    ],
    "api_errors": [
        {
            "component_id": "API_GATEWAY_PROD",
            "component_type": "API",
            "error_code": "HTTP_503",
            "message": "API Gateway returning 503 — upstream DB unavailable",
            "latency_ms": 5001,
            "metadata": {"endpoint": "/api/v1/users", "error_rate": "87%"},
        },
        {
            "component_id": "API_GATEWAY_PROD",
            "component_type": "API",
            "error_code": "HTTP_500",
            "message": "NullPointerException in payment service — DB connection pool exhausted",
            "latency_ms": 4200,
            "metadata": {"endpoint": "/api/v1/payments", "pool_size": 0},
        },
    ],
}


async def send_signal(client: httpx.AsyncClient, signal: dict, label: str = ""):
    try:
        resp = await client.post(f"{BASE_URL}/api/signals", json=signal, timeout=5)
        status = "✓" if resp.status_code == 202 else f"✗ {resp.status_code}"
        print(f"  {status}  {label or signal['component_id']}")
    except Exception as exc:
        print(f"  ✗ ERROR: {exc}")


async def burst_signals(client: httpx.AsyncClient, template: dict, count: int, label: str):
    """Send `count` copies of a signal with small random jitter."""
    tasks = []
    for i in range(count):
        signal = {**template, "metadata": {**(template.get("metadata") or {}), "burst_seq": i}}
        tasks.append(send_signal(client, signal, f"{label} #{i+1}"))
    await asyncio.gather(*tasks)


async def run_full_scenario(base_url: str):
    print("\n🔥 IMS Mock Failure Simulator")
    print("=" * 50)

    async with httpx.AsyncClient(base_url=base_url) as client:
        # Phase 1: RDBMS outage
        print("\n[Phase 1] RDBMS Primary outage — 150 signals over 12 seconds")
        print("          (Only 1 WorkItem should be created due to debounce)")
        template = SCENARIOS["rdbms_outage"][0]
        await burst_signals(client, template, 150, "RDBMS signal")
        await asyncio.sleep(1)

        # Phase 2: MCP cascade
        print("\n[Phase 2] MCP Host cascade failure")
        for sig in SCENARIOS["mcp_failure"]:
            await send_signal(client, sig, "MCP_HOST_CLUSTER_A")
        await asyncio.sleep(0.5)

        # Phase 3: Cache stampede
        print("\n[Phase 3] Cache invalidation storm — 80 signals")
        await burst_signals(client, SCENARIOS["cache_storm"][0], 80, "CACHE signal")
        await asyncio.sleep(0.5)

        # Phase 4: API errors
        print("\n[Phase 4] Customer-facing API errors")
        for sig in SCENARIOS["api_errors"]:
            for _ in range(5):
                await send_signal(client, sig)
        await asyncio.sleep(1)

        # Summary
        print("\n[Summary] Fetching created incidents...")
        try:
            resp = await client.get(f"{base_url}/api/incidents?limit=20", timeout=10)
            if resp.status_code == 200:
                incidents = resp.json()
                print(f"\n  Created {len(incidents)} Work Items:\n")
                for inc in incidents:
                    print(f"  [{inc['severity']}] {inc['title'][:70]}")
                    print(f"        Status: {inc['status']} | Signals: {inc['signal_count']} | ID: {inc['id']}")
                    print()
            else:
                print(f"  Could not fetch incidents: {resp.status_code}")
        except Exception as exc:
            print(f"  Could not fetch incidents: {exc}")

    print("\n✅ Mock failure scenario complete!")
    print(f"   View dashboard: http://localhost:5173")
    print(f"   API docs:       {base_url}/docs\n")


async def run_quick(base_url: str):
    """Quick smoke test — 5 signals."""
    async with httpx.AsyncClient(base_url=base_url) as client:
        print("Sending 5 quick test signals...")
        for sig in [*SCENARIOS["rdbms_outage"], *SCENARIOS["api_errors"]]:
            await send_signal(client, sig)
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMS Mock Failure Simulator")
    parser.add_argument("--url", default=BASE_URL, help="Backend base URL")
    parser.add_argument(
        "--scenario",
        choices=["full", "quick"],
        default="full",
        help="Scenario to run",
    )
    args = parser.parse_args()

    runner = run_full_scenario if args.scenario == "full" else run_quick
    asyncio.run(runner(args.url))
