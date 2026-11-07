# Decision log

- 2026-11-06: Plan v1 written (docs/plan.md). Decisions H1–H8 recorded there.
- 2026-11-06: Scaffold + USGS snapshot (Claude Code). Choices the plan left open:
  - `monitoring-locations` filters on `id=USGS-<site>`; `monitoring_location_id` returns HTTP 400 there. The other two collections use `monitoring_location_id`.
  - Fetcher follows `next` hrefs verbatim (channel-measurements' links point at `/ogcapi/v1/` even when v0 is requested). Page limit 10000; pagination verified live on 03459500 at limit=500 (same counts).
  - Snapshot layout: `{site, fetched_at, api_base, collections: {name: [raw features]}}`, UTF-8, atomic write. Refuses to write if field-measurements or monitoring-locations is empty. `make snapshot` refuses unless `SOURCE=live`.
  - `requires-python >=3.11` (laptop venv is 3.13; stack targets 3.11). Agents/API deps installed via `make install` extras.
  - `field-measurements` row counts include both stage (00065) and discharge (00060) rows; pairing comes later.
  - **Site-name mismatch found in the API metadata:** 03459500 is "PIGEON RIVER NEAR HEPCO, NC" (Canton is 03456500), and 03463300 is "SOUTH TOE RIVER NEAR CELO, NC" (not North Toe at Altapass). Site IDs left as-is pending Grace's call.
- 2026-11-06 23:05: Site names corrected everywhere (plan, playbook, prompts): 03459500 = Pigeon River near Hepco (not Canton); 03463300 = South Toe River near Celo (not North Toe at Altapass). Site IDs kept — the Friday-night drift numbers were computed for these IDs. docs/prompts/pi_job1.md + launch_job1.sh written for thoth.
