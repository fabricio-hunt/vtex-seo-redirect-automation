from core.config import RecoveryConfig


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
    restored = RecoveryConfig.from_dict({"threshold": 75})
    assert restored.threshold == 75
    assert restored.max_workers == 10
