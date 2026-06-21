"""Real provider lookup via the CMS NPPES NPI Registry API (public, no key).

Docs: https://npiregistry.cms.hhs.gov/api/?version=2.1

NPPES returns real, registered US healthcare providers (name, address, taxonomy,
phone). It does NOT contain appointment availability or insurance acceptance, so
those two fields are *synthesized deterministically* and clearly labeled as such
in the UI/disclaimer.
"""
from __future__ import annotations

import hashlib
from typing import List

import requests

from .models import Provider

NPPES_URL = "https://npiregistry.cms.hhs.gov/api/"
TIMEOUT = 8

_SLOTS = [
    "tomorrow at 9:00 AM",
    "tomorrow at 11:30 AM",
    "tomorrow at 2:15 PM",
    "in 2 days at 10:00 AM",
    "in 2 days at 3:45 PM",
    "in 3 days at 8:30 AM",
]


def _synth_slot(seed: str) -> str:
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    return _SLOTS[h % len(_SLOTS)]


def _synth_accepts(seed: str) -> bool:
    # ~85% accept the given plan, deterministically per provider.
    h = int(hashlib.sha256((seed + "ins").encode()).hexdigest(), 16)
    return (h % 100) < 85


def _format_address(addr: dict) -> str:
    parts = [
        addr.get("address_1", "").strip(),
        addr.get("city", "").strip(),
        addr.get("state", "").strip(),
        addr.get("postal_code", "")[:5].strip(),
    ]
    return ", ".join(p for p in parts if p)


def search_providers(
    taxonomy: str,
    city: str = "",
    state: str = "",
    postal_code: str = "",
    insurance: str = "",
    limit: int = 3,
) -> List[Provider]:
    """Query NPPES; return up to `limit` normalized Provider records.

    Raises requests exceptions on network failure (caller decides on fallback).
    """
    params = {
        "version": "2.1",
        "taxonomy_description": taxonomy,
        "limit": min(max(limit * 4, 10), 50),  # over-fetch, then filter for LOCATION addresses
    }
    if city:
        params["city"] = city
    if state:
        params["state"] = state
    if postal_code:
        params["postal_code"] = postal_code

    resp = requests.get(NPPES_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    providers: List[Provider] = []
    for result in data.get("results", []):
        basic = result.get("basic", {})
        npi = str(result.get("number", ""))

        if basic.get("organization_name"):
            name = basic["organization_name"].title()
        else:
            fn = basic.get("first_name", "").title()
            ln = basic.get("last_name", "").title()
            cred = basic.get("credential", "")
            name = " ".join(p for p in [fn, ln] if p)
            if cred:
                name = f"{name}, {cred}"
        if not name:
            continue

        # Prefer the practice LOCATION address; fall back to first available.
        addresses = result.get("addresses", [])
        loc = next((a for a in addresses if a.get("address_purpose") == "LOCATION"), None)
        loc = loc or (addresses[0] if addresses else {})
        address = _format_address(loc)
        phone = loc.get("telephone_number", "")

        taxonomies = result.get("taxonomies", [])
        primary_tax = next((t for t in taxonomies if t.get("primary")), taxonomies[0] if taxonomies else {})
        specialty = primary_tax.get("desc", taxonomy)

        providers.append(
            Provider(
                name=name,
                specialty=specialty,
                address=address or "Address on file with provider",
                phone=phone,
                accepts_insurance=_synth_accepts(npi) if insurance else True,
                next_slot=_synth_slot(npi),
                npi=npi,
            )
        )
        if len(providers) >= limit:
            break

    return providers


# Static fallback so a demo never hard-fails if NPPES is unreachable.
def fallback_providers(taxonomy: str, city: str = "", limit: int = 3) -> List[Provider]:
    base = [
        ("Bay Area Family Health", "(510) 555-0142"),
        ("Bear Flag Medical Group", "(510) 555-0188"),
        ("Telegraph Avenue Clinic", "(510) 555-0173"),
    ]
    where = f"{city}, CA" if city else "Berkeley, CA"
    out = []
    for i, (name, phone) in enumerate(base[:limit]):
        out.append(
            Provider(
                name=name,
                specialty=taxonomy,
                address=f"{1200 + i * 30} Center St, {where}",
                phone=phone,
                accepts_insurance=True,
                next_slot=_SLOTS[i % len(_SLOTS)],
                npi="",
            )
        )
    return out
