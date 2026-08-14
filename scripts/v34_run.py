"""Thin V3.4 runner that fixes the M15 frame alias without changing study rules."""
import sys
import v34_market_intelligence_challengers as v34

_original_annotate = v34.annotate_setup

def _annotate_with_alias(setup, frames):
    if "m15" not in frames and "15m" in frames:
        frames = {**frames, "m15": frames["15m"]}
    return _original_annotate(setup, frames)

v34.annotate_setup = _annotate_with_alias

if __name__ == "__main__":
    v34.main()
