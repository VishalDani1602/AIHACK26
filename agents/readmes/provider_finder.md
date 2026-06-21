# CareLoop Provider-Finder Agent

![domain:healthcare](https://img.shields.io/badge/domain-healthcare-2ea44f)
![data:NPPES](https://img.shields.io/badge/data-CMS%20NPPES-blue)

Finds **real, registered US healthcare providers** by querying the public
[CMS NPPES NPI Registry](https://npiregistry.cms.hhs.gov/api/) for a given
taxonomy (specialty) and location.

NPPES has no scheduling or insurance-network data, so appointment slots and
plan acceptance are **synthesized deterministically** and clearly labeled as
estimates in the UI. Falls back to a sample list if NPPES is unreachable.

## Input / Output
- **Input** `ProviderRequest`: `{ session_id, taxonomy, city, state, postal_code, insurance, limit }`
- **Output** `ProviderResult`: `{ providers[{name, specialty, address, phone, accepts_insurance, next_slot, npi}], note }`

Part of the **CareLoop** multi-agent system (UC Berkeley AI Hackathon 2026).
