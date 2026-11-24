"""Client for the openFDA drug label API (https://open.fda.gov/apis/drug/label/)."""
import os
import time

import requests

API_URL = "https://api.fda.gov/drug/label.json"
TTL_SECONDS = 3600
_cache = {}


def _field(item, key, limit=400):
    value = item.get(key)
    if not value:
        return None
    text = " ".join(value) if isinstance(value, list) else str(value)
    return text[:limit]


# def drug_info(name):
#     """Return label info for a drug. Never raises: failures become available=False."""
#     key = name.strip().lower()[:80].replace(chr(34), "")
#     if not key:
#         return {"available": False, "reason": "Empty drug name"}
#     hit = _cache.get(key)
#     if hit and time.time() - hit[0] < TTL_SECONDS:
#         return hit[1]
#     quoted = chr(34) + key + chr(34)
#     params = {
#         "search": f"openfda.generic_name:{quoted} OR openfda.brand_name:{quoted}",
#         "limit": 1,
#     }
#     if os.getenv("OPENFDA_API_KEY"):
#         params["api_key"] = os.getenv("OPENFDA_API_KEY")
#     try:
#         resp = requests.get(API_URL, params=params, timeout=5)
#         if resp.status_code == 404:
#             info = {"available": False, "reason": "No FDA label found for this drug"}
#         elif resp.status_code != 200:
#             return {"available": False, "reason": f"openFDA returned HTTP {resp.status_code}"}
#         else:
#             item = resp.json()["results"][0]
#             info = {
#                 "available": True,
#                 "source": "openFDA",
#                 "purpose": _field(item, "purpose") or _field(item, "indications_and_usage"),
#                 "warnings": _field(item, "warnings"),
#                 "adverse_reactions": _field(item, "adverse_reactions"),
#             }
#     except (requests.RequestException, ValueError, KeyError, IndexError):
#         return {"available": False, "reason": "openFDA is temporarily unavailable"}
#     _cache[key] = (time.time(), info)
#     return info