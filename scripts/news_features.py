"""Recent-news feature collector for research and shadow scoring.

GDELT DOC 2.0 is useful for recent rolling news. Historical model training should
use GDELT bulk GKG/Event archives or another point-in-time licensed archive.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import requests

GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"

@dataclass(frozen=True)
class NewsQuery:
    name: str
    query: str

QUERIES = [
    NewsQuery("geopolitical_conflict", '(war OR conflict OR missile OR invasion OR ceasefire)'),
    NewsQuery("central_banks", '(Federal Reserve OR ECB OR BOE OR interest rates OR rate cut OR rate hike)'),
    NewsQuery("inflation_growth", '(inflation OR CPI OR payrolls OR unemployment OR recession)'),
    NewsQuery("energy_shock", '(oil OR crude OR OPEC OR Strait of Hormuz OR energy supply)'),
]


def recent_timeline(query: str, days: int = 30) -> dict:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = {
        "query": query,
        "mode": "timelinevolraw",
        "format": "json",
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.strftime("%Y%m%d%H%M%S"),
    }
    response = requests.get(GDELT_DOC, params=params, timeout=30)
    response.raise_for_status()
    return response.json()
