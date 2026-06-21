# CareLoop Cost-Estimator Agent

![domain:healthcare](https://img.shields.io/badge/domain-healthcare-2ea44f)
![type:estimate](https://img.shields.io/badge/output-estimate-orange)

Produces a plain-language **out-of-pocket cost range** for a visit, combining an
average billed amount per visit type with simplified plan cost-sharing (copay,
coinsurance, remaining deductible) for Medicare, Medicaid, PPO, HMO,
high-deductible, and self-pay.

Always presented as an **estimate**, never a quote.

## Input / Output
- **Input** `CostRequest`: `{ session_id, visit_type, insurance }`
- **Output** `CostResult`: `{ estimate_low, estimate_high, explanation }`

Part of the **CareLoop** multi-agent system (UC Berkeley AI Hackathon 2026).
