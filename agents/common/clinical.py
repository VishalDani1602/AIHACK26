"""Clinical evidence sources (real, public, no API key).

  - Recruiting clinical trials: ClinicalTrials.gov API v2
  - Drug-safety / interactions: openFDA drug-label API

Both are cached in Redis (shared across agent processes) and degrade gracefully.
This is navigation/education only — not medical advice.
"""
from __future__ import annotations

from typing import List

import requests

from . import store
from .models import DrugNote, Trial

CTGOV_URL = "https://clinicaltrials.gov/api/v2/studies"
OPENFDA_URL = "https://api.fda.gov/drug/label.json"
TIMEOUT = 12


def search_trials(condition: str, state: str = "", city: str = "", limit: int = 3,
                  cache_ttl: int = 3600) -> List[Trial]:
    """Recruiting trials for a condition near a location (state preferred)."""
    if not condition:
        return []
    locn = state or city
    cache_key = "ctgov:" + store.hash_key(condition.lower(), locn.lower(), limit)
    cached = store.cache_get_json(cache_key)
    if cached is not None:
        store.incr_stat("ctgov_cache_hit")
        return [Trial(**t) for t in cached]

    params = {
        "query.cond": condition,
        "filter.overallStatus": "RECRUITING",
        "pageSize": limit,
        "format": "json",
    }
    if locn:
        params["query.locn"] = locn

    resp = requests.get(CTGOV_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    trials: List[Trial] = []
    for s in data.get("studies", []):
        ps = s.get("protocolSection", {})
        ident = ps.get("identificationModule", {})
        nct = ident.get("nctId", "")
        if not nct:
            continue
        phases = ps.get("designModule", {}).get("phases", []) or []
        locs = ps.get("contactsLocationsModule", {}).get("locations", []) or []
        loc0 = ""
        if locs:
            loc0 = ", ".join(p for p in [locs[0].get("city", ""), locs[0].get("state", "")] if p)
        trials.append(Trial(
            nct_id=nct,
            title=ident.get("briefTitle", "")[:140],
            status=ps.get("statusModule", {}).get("overallStatus", ""),
            phase=", ".join(phases).replace("PHASE", "Phase ") if phases else "N/A",
            location=loc0,
            url=f"https://clinicaltrials.gov/study/{nct}",
        ))
        if len(trials) >= limit:
            break

    store.incr_stat("ctgov_api_call")
    store.cache_set_json(cache_key, [t.dict() for t in trials], ttl=cache_ttl)
    return trials


def drug_safety(drug: str, cache_ttl: int = 86400) -> List[DrugNote]:
    """openFDA label: drug-interaction / warning summary for a medication."""
    drug = (drug or "").strip()
    if not drug:
        return []
    cache_key = "openfda:" + store.hash_key(drug.lower())
    cached = store.cache_get_json(cache_key)
    if cached is not None:
        store.incr_stat("openfda_cache_hit")
        return [DrugNote(**n) for n in cached]

    notes: List[DrugNote] = []
    try:
        resp = requests.get(OPENFDA_URL, params={
            "search": f'openfda.generic_name:"{drug}" openfda.brand_name:"{drug}"'.replace(" openfda", "+openfda"),
            "limit": 1,
        }, timeout=TIMEOUT)
        if resp.status_code != 200:
            resp = requests.get(OPENFDA_URL, params={"search": f'openfda.generic_name:{drug}', "limit": 1}, timeout=TIMEOUT)
        resp.raise_for_status()
        res = (resp.json().get("results") or [{}])[0]
        info = (res.get("drug_interactions") or res.get("warnings") or res.get("boxed_warning") or [""])[0]
        if info:
            notes.append(DrugNote(drug=drug.title(), info=" ".join(info.split())[:300],
                                  url="https://www.accessdata.fda.gov/scripts/cder/daf/"))
    except Exception:
        return []

    store.incr_stat("openfda_api_call")
    store.cache_set_json(cache_key, [n.dict() for n in notes], ttl=cache_ttl)
    return notes
