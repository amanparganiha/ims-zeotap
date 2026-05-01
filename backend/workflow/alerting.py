"""
Strategy Pattern: Different alert strategies per component type.
Determines severity (P0-P3) and alert behaviour.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AlertContext:
    component_id: str
    component_type: str
    error_code: str
    message: str


@dataclass
class AlertResult:
    severity: str          # P0 | P1 | P2 | P3
    title: str
    notify_channels: list[str]


class AlertStrategy(ABC):
    @abstractmethod
    def evaluate(self, ctx: AlertContext) -> AlertResult:
        ...


class RDBMSAlertStrategy(AlertStrategy):
    """P0 - database failures are always critical."""

    def evaluate(self, ctx: AlertContext) -> AlertResult:
        return AlertResult(
            severity="P0",
            title=f"[P0] RDBMS Failure on {ctx.component_id}: {ctx.error_code}",
            notify_channels=["pagerduty", "slack-critical", "email"],
        )


class MCPHostAlertStrategy(AlertStrategy):
    """P1 - MCP host failures affect entire service mesh."""

    def evaluate(self, ctx: AlertContext) -> AlertResult:
        return AlertResult(
            severity="P1",
            title=f"[P1] MCP Host Down: {ctx.component_id}",
            notify_channels=["slack-critical", "email"],
        )


class CacheAlertStrategy(AlertStrategy):
    """P2 - cache failures degrade performance but system stays up."""

    def evaluate(self, ctx: AlertContext) -> AlertResult:
        return AlertResult(
            severity="P2",
            title=f"[P2] Cache Degraded: {ctx.component_id}",
            notify_channels=["slack-warnings"],
        )


class QueueAlertStrategy(AlertStrategy):
    """P2 - async queue failures cause delays, not outages."""

    def evaluate(self, ctx: AlertContext) -> AlertResult:
        return AlertResult(
            severity="P2",
            title=f"[P2] Queue Issue: {ctx.component_id}",
            notify_channels=["slack-warnings"],
        )


class APIAlertStrategy(AlertStrategy):
    """P1 - API failures are customer-facing."""

    def evaluate(self, ctx: AlertContext) -> AlertResult:
        return AlertResult(
            severity="P1",
            title=f"[P1] API Error: {ctx.component_id} — {ctx.error_code}",
            notify_channels=["slack-critical", "email"],
        )


class DefaultAlertStrategy(AlertStrategy):
    """P3 - unknown component types get lowest severity."""

    def evaluate(self, ctx: AlertContext) -> AlertResult:
        return AlertResult(
            severity="P3",
            title=f"[P3] Signal from {ctx.component_id}: {ctx.error_code}",
            notify_channels=["slack-general"],
        )


# ── Strategy resolver ─────────────────────────────────────────────────────────
_STRATEGY_MAP: dict[str, AlertStrategy] = {
    "RDBMS": RDBMSAlertStrategy(),
    "MCP_HOST": MCPHostAlertStrategy(),
    "CACHE": CacheAlertStrategy(),
    "QUEUE": QueueAlertStrategy(),
    "API": APIAlertStrategy(),
}


def resolve_strategy(component_type: str) -> AlertStrategy:
    return _STRATEGY_MAP.get(component_type.upper(), DefaultAlertStrategy())


def evaluate_alert(ctx: AlertContext) -> AlertResult:
    strategy = resolve_strategy(ctx.component_type)
    return strategy.evaluate(ctx)
