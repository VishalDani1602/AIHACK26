# CareLoop Clinical-Evidence Agent

![domain:healthcare](https://img.shields.io/badge/domain-healthcare-2ea44f)
![data:ClinicalTrials.gov](https://img.shields.io/badge/data-ClinicalTrials.gov-blue)
![data:openFDA](https://img.shields.io/badge/data-openFDA-blue)

When triage identifies a **serious or chronic condition**, this agent surfaces
real, current evidence the patient can take to their clinician:

- **Recruiting clinical trials** near the patient — live from the
  [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api).
- **Drug-safety / interaction** notes for mentioned medications — from the
  [openFDA drug-label API](https://open.fda.gov/apis/drug/label/).

Education and navigation only — **not** medical advice. Results are options to
discuss with a doctor.

## Input / Output
- **Input** `EvidenceRequest`: `{ session_id, condition, medications, city, state, limit }`
- **Output** `EvidenceResult`: `{ trials[{nct_id, title, status, phase, location, url}], drug_notes[{drug, info, url}], note }`

Part of the **CareLoop** multi-agent system (UC Berkeley AI Hackathon 2026).
