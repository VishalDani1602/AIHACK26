# CareLoop Triage Agent

![domain:healthcare](https://img.shields.io/badge/domain-healthcare-2ea44f)
![safety:red-flags](https://img.shields.io/badge/safety-911%20red--flags-e5484d)

Decides **how urgently** someone should be seen and **which clinician** is the
right first stop. Navigation only — never a diagnosis.

Hard-coded red-flag rules (chest pain, stroke signs, trouble breathing, severe
bleeding, suicidal ideation, etc.) run **before** the LLM and force an immediate
911 escalation. Otherwise ASI:One picks an urgency level and a specialty from a
fixed allow-list.

## Input / Output
- **Input** `TriageRequest`: `{ session_id, symptoms, patient_age? }`
- **Output** `TriageResult`: `{ urgency, recommended_specialty, taxonomy, red_flags[], advice, emergency }`

Part of the **CareLoop** multi-agent system (UC Berkeley AI Hackathon 2026).
