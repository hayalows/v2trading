import pytest
from v2trading.features import assert_no_leakage, BASE_FEATURES


def test_base_features_are_entry_time_safe():
    assert_no_leakage(BASE_FEATURES)


def test_realized_outcome_is_rejected():
    with pytest.raises(ValueError):
        assert_no_leakage(["symbol", "net_r"])


def test_recovered_setup_score_is_rejected():
    with pytest.raises(ValueError):
        assert_no_leakage(["m15_v2_setup_score"])
