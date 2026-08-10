from pathlib import Path


def test_v14_protocol_markers_present():
    script = Path('scripts/v14_poi_waiting_time_study.py').read_text()
    protocol = Path('reports/v14/V14_POI_WAITING_TIME_PROTOCOL.md').read_text()
    for marker in ['HORIZONS = [8, 12, 16, 24, 32, 48]', 'MAX_FOLLOW = max(HORIZONS)', 'right-censored', 'shallow_zone_touch_before_midpoint']:
        assert marker in script
    for marker in ['Time alone should not be labelled `invalidated`', 'at least 5 percentage points', 'at least 30 resolved fills', 'positive mean net R']:
        assert marker in protocol
