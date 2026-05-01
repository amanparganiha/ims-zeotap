"""
State Pattern: WorkItem lifecycle transitions.
OPEN → INVESTIGATING → RESOLVED → CLOSED (requires RCA)
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class WorkItemState(ABC):
    @abstractmethod
    def next_allowed(self) -> list[str]:
        ...

    @abstractmethod
    def on_enter(self, work_item: dict) -> dict:
        """Mutate work_item dict with any fields needed on entry."""
        ...


class OpenState(WorkItemState):
    name = "OPEN"

    def next_allowed(self) -> list[str]:
        return ["INVESTIGATING"]

    def on_enter(self, work_item: dict) -> dict:
        return work_item


class InvestigatingState(WorkItemState):
    name = "INVESTIGATING"

    def next_allowed(self) -> list[str]:
        return ["RESOLVED", "OPEN"]

    def on_enter(self, work_item: dict) -> dict:
        return work_item


class ResolvedState(WorkItemState):
    name = "RESOLVED"

    def next_allowed(self) -> list[str]:
        return ["CLOSED", "INVESTIGATING"]

    def on_enter(self, work_item: dict) -> dict:
        work_item["resolved_at"] = datetime.now(timezone.utc)
        return work_item


class ClosedState(WorkItemState):
    name = "CLOSED"

    def next_allowed(self) -> list[str]:
        return []   # terminal state

    def on_enter(self, work_item: dict) -> dict:
        now = datetime.now(timezone.utc)
        work_item["closed_at"] = now
        # MTTR: seconds from first signal to close
        created = work_item.get("created_at")
        if created:
            delta = now - created
            work_item["mttr_seconds"] = int(delta.total_seconds())
        return work_item


# Registry
_STATE_MAP: dict[str, WorkItemState] = {
    "OPEN": OpenState(),
    "INVESTIGATING": InvestigatingState(),
    "RESOLVED": ResolvedState(),
    "CLOSED": ClosedState(),
}


def get_state(status: str) -> WorkItemState:
    state = _STATE_MAP.get(status)
    if not state:
        raise ValueError(f"Unknown status: {status}")
    return state


def validate_transition(current: str, target: str) -> None:
    """Raise ValueError if transition is illegal."""
    state = get_state(current)
    if target not in state.next_allowed():
        raise ValueError(
            f"Invalid transition {current} → {target}. "
            f"Allowed: {state.next_allowed()}"
        )
