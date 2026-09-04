from core.config import MIN_MATCH_SCORE, RecoveryConfig


def test_recovery_config_defaults_match_original_hardcoded_values():
    config = RecoveryConfig()
    assert config.threshold == 90
    assert config.check_http_status is True
    assert config.max_workers == 10
    assert config.http_timeout == 10
    assert config.base_domain == "https://www.bemol.com.br"
    assert config.legacy_redirect == "/superoferta"


def test_recovery_config_round_trips_through_dict():
    config = RecoveryConfig(threshold=80, check_http_status=False)
    restored = RecoveryConfig.from_dict(config.to_dict())
    assert restored == config


def test_recovery_config_from_dict_fills_missing_fields_with_defaults():
    restored = RecoveryConfig.from_dict({"threshold": 82})
    assert restored.threshold == 82
    assert restored.max_workers == 10


def test_recovery_config_clamps_threshold_to_min_match_score():
    """A caller (CLI flag, web UI, API payload) must never be able to weaken the accuracy
    floor by requesting a threshold below MIN_MATCH_SCORE."""
    assert MIN_MATCH_SCORE == 80
    assert RecoveryConfig(threshold=0).threshold == MIN_MATCH_SCORE
    assert RecoveryConfig(threshold=50).threshold == MIN_MATCH_SCORE
    assert RecoveryConfig.from_dict({"threshold": 10}).threshold == MIN_MATCH_SCORE
    assert RecoveryConfig(threshold=95).threshold == 95
