"""Tests para la evaluación de alertas OBD-II."""

from src.obd2.alerts import evaluate


def _sample(**overrides):
    base = {
        "connected": True,
        "_last_update": "2026-01-01T00:00:00Z",
        "RPM": 2000,
        "SPEED": 90,
        "COOLANT_TEMP": 90,
        "ENGINE_LOAD": 40.0,
        "THROTTLE_POS": 20.0,
        "INTAKE_TEMP": 30,
    }
    base.update(overrides)
    return base


def test_evaluate_ok_when_within_thresholds():
    result = evaluate(_sample())
    assert result["level"] == "ok"
    assert result["alerts"] == []


def test_evaluate_warning_when_slightly_above_max():
    # RPM max=5000, warning_margin=500 -> por encima de 5500 es warning.
    result = evaluate(_sample(RPM=5600))
    assert result["level"] == "warning"
    assert any(alert["pid"] == "RPM" for alert in result["alerts"])


def test_evaluate_critical_when_far_above_max():
    # RPM max=5000, critical_margin=1000 -> por encima de 6000 es critical.
    result = evaluate(_sample(RPM=6500))
    assert result["level"] == "critical"
    rpm_alert = next(alert for alert in result["alerts"] if alert["pid"] == "RPM")
    assert rpm_alert["level"] == "critical"


def test_evaluate_warning_when_below_min():
    # COOLANT_TEMP min=80 -> por debajo es warning (motor frío).
    result = evaluate(_sample(COOLANT_TEMP=50))
    assert result["level"] == "warning"
    assert any(alert["pid"] == "COOLANT_TEMP" for alert in result["alerts"])


def test_evaluate_ignores_unknown_and_meta_fields():
    result = evaluate(_sample(SOME_UNKNOWN_PID=123))
    assert result["pids"]["SOME_UNKNOWN_PID"] == {"level": "unknown", "message": None}


def test_evaluate_critical_overrides_global_level_even_if_other_pid_is_warning():
    result = evaluate(_sample(RPM=5600, COOLANT_TEMP=200))
    assert result["level"] == "critical"


def test_recommendations_include_all_known_pids():
    result = evaluate(_sample())
    pids = {rec["pid"] for rec in result["recommendations"]}
    assert "RPM" in pids
    assert "COOLANT_TEMP" in pids
