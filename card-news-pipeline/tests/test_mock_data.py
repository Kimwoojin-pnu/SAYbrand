from cardnews.mock_data import load_sample_threats
from cardnews.models import ThreatRecord


def test_load_sample_threats_returns_threat_records():
    threats = load_sample_threats()

    assert len(threats) >= 3
    assert all(isinstance(threat, ThreatRecord) for threat in threats)
    assert all(threat.summary for threat in threats)
    assert all(1 <= threat.impact_score <= 10 for threat in threats)


def test_load_sample_threats_returns_a_fresh_copy_each_time():
    first_call = load_sample_threats()
    second_call = load_sample_threats()

    assert first_call == second_call
    assert first_call is not second_call
