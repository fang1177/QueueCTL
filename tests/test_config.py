"""
QueueCTL Configuration System Unit Tests.

Tests setting runtime config values, retrieving consolidated configs, and type validation rules.
"""

import pytest
from queuectl.core.exceptions import ConfigError


def test_config_defaults(config_service):
    """Tests loading default configurations."""
    configs = config_service.get_all_configs()
    assert configs["max_retries"] == 3
    assert configs["backoff_base"] == 2.0
    assert configs["heartbeat_interval"] == 5.0
    assert configs["recovery_timeout"] == 30.0


def test_config_set_and_get(config_service):
    """Tests updating configuration settings dynamically."""
    res = config_service.set_config("max_retries", "5")
    assert res["value"] == "5"

    val = config_service.get_config("max_retries")
    assert val == "5"

    updated_configs = config_service.get_all_configs()
    assert updated_configs["max_retries"] == 5


def test_config_validation_rules(config_service):
    """Tests validation of invalid configuration values."""
    with pytest.raises(ConfigError):
        config_service.set_config("max_retries", "-1")

    with pytest.raises(ConfigError):
        config_service.set_config("backoff_base", "invalid_float")

    with pytest.raises(ConfigError):
        config_service.set_config("unknown_key_xyz", "123")
