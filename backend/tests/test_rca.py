"""
Unit tests for RCA validation logic and state machine transitions.
Run with: pytest backend/tests/ -v
"""
import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError

from models.schemas import RCASubmission
from workflow.states import validate_transition, get_state


# ── RCA Validation ────────────────────────────────────────────────────────────

class TestRCAValidation:

    def _valid_rca(self, **overrides):
        base = dict(
            incident_start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            incident_end=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
            root_cause_category="Infrastructure Failure",
            fix_applied="Restarted the database cluster and applied hotfix.",
            prevention_steps="Add automated failover; increase disk monitoring alerts.",
        )
        base.update(overrides)
        return base

    def test_valid_rca_passes(self):
        rca = RCASubmission(**self._valid_rca())
        assert rca.root_cause_category == "Infrastructure Failure"

    def test_empty_fix_applied_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            RCASubmission(**self._valid_rca(fix_applied=""))
        assert "empty" in str(exc_info.value).lower()

    def test_empty_prevention_steps_rejected(self):
        with pytest.raises(ValidationError):
            RCASubmission(**self._valid_rca(prevention_steps="   "))

    def test_empty_root_cause_rejected(self):
        with pytest.raises(ValidationError):
            RCASubmission(**self._valid_rca(root_cause_category=""))

    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            RCASubmission(**self._valid_rca(
                incident_start=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
                incident_end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            ))
        assert "after" in str(exc_info.value).lower()

    def test_end_equal_start_rejected(self):
        t = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
        with pytest.raises(ValidationError):
            RCASubmission(**self._valid_rca(incident_start=t, incident_end=t))

    def test_whitespace_stripped(self):
        rca = RCASubmission(**self._valid_rca(fix_applied="  patched the server  "))
        assert rca.fix_applied == "patched the server"


# ── State Machine ─────────────────────────────────────────────────────────────

class TestStateMachine:

    def test_open_to_investigating(self):
        validate_transition("OPEN", "INVESTIGATING")   # should not raise

    def test_investigating_to_resolved(self):
        validate_transition("INVESTIGATING", "RESOLVED")

    def test_resolved_to_closed(self):
        validate_transition("RESOLVED", "CLOSED")

    def test_open_cannot_go_to_closed(self):
        with pytest.raises(ValueError):
            validate_transition("OPEN", "CLOSED")

    def test_open_cannot_go_to_resolved(self):
        with pytest.raises(ValueError):
            validate_transition("OPEN", "RESOLVED")

    def test_closed_is_terminal(self):
        state = get_state("CLOSED")
        assert state.next_allowed() == []

    def test_closed_cannot_transition_anywhere(self):
        for target in ("OPEN", "INVESTIGATING", "RESOLVED"):
            with pytest.raises(ValueError):
                validate_transition("CLOSED", target)

    def test_resolved_sets_resolved_at(self):
        state = get_state("RESOLVED")
        result = state.on_enter({})
        assert "resolved_at" in result
        assert result["resolved_at"] is not None

    def test_closed_calculates_mttr(self):
        state = get_state("CLOSED")
        created = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
        result = state.on_enter({"created_at": created})
        assert "mttr_seconds" in result
        assert result["mttr_seconds"] > 0

    def test_investigating_can_revert_to_open(self):
        validate_transition("INVESTIGATING", "OPEN")


# ── Alerting Strategy ─────────────────────────────────────────────────────────

class TestAlertingStrategy:

    def test_rdbms_gets_p0(self):
        from workflow.alerting import AlertContext, evaluate_alert
        ctx = AlertContext("DB_01", "RDBMS", "CONNECTION_REFUSED", "DB down")
        result = evaluate_alert(ctx)
        assert result.severity == "P0"

    def test_cache_gets_p2(self):
        from workflow.alerting import AlertContext, evaluate_alert
        ctx = AlertContext("CACHE_01", "CACHE", "TIMEOUT", "Cache miss spike")
        result = evaluate_alert(ctx)
        assert result.severity == "P2"

    def test_unknown_gets_p3(self):
        from workflow.alerting import AlertContext, evaluate_alert
        ctx = AlertContext("UNKNOWN_01", "IOT_SENSOR", "ERR", "wat")
        result = evaluate_alert(ctx)
        assert result.severity == "P3"

    def test_api_gets_p1(self):
        from workflow.alerting import AlertContext, evaluate_alert
        ctx = AlertContext("API_GW", "API", "500", "Gateway error")
        result = evaluate_alert(ctx)
        assert result.severity == "P1"
