# CareLoop Scheduler Agent

![domain:healthcare](https://img.shields.io/badge/domain-healthcare-2ea44f)
![output:ical](https://img.shields.io/badge/output-iCalendar-blue)

Finalizes a booking: generates a confirmation code, a human-readable summary,
and a real **iCalendar (.ics)** invite the patient can add to any calendar.

(The booking itself is mocked for the hackathon; the calendar invite is real
and importable.)

## Input / Output
- **Input** `BookingRequest`: `{ session_id, provider_name, provider_address, slot, patient_name, reason }`
- **Output** `BookingResult`: `{ confirmation_code, summary, ics }`

Part of the **CareLoop** multi-agent system (UC Berkeley AI Hackathon 2026).
