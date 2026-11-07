# Decision log

- 2026-11-06: Plan v1 written (docs/plan.md). Decisions H1–H8 recorded there.
- 2026-11-06: Scaffold + USGS snapshot (Claude Code). Choices the plan left open:
  - `monitoring-locations` filters on `id=USGS-<site>`; `monitoring_location_id` returns HTTP 400 there. The other two collections use `monitoring_location_id`.
  - Fetcher follows `next` hrefs verbatim (channel-measurements' links point at `/ogcapi/v1/` even when v0 is requested). Page limit 10000; pagination verified live on 03459500 at limit=500 (same counts).
  - Snapshot layout: `{site, fetched_at, api_base, collections: {name: [raw features]}}`, UTF-8, atomic write. Refuses to write if field-measurements or monitoring-locations is empty. `make snapshot` refuses unless `SOURCE=live`.
  - `requires-python >=3.11` (laptop venv is 3.13; stack targets 3.11). Agents/API deps installed via `make install` extras.
  - `field-measurements` row counts include both stage (00065) and discharge (00060) rows; pairing comes later.
  - **Site-name mismatch found in the API metadata:** 03459500 is "PIGEON RIVER NEAR HEPCO, NC" (Canton is 03456500), and 03463300 is "SOUTH TOE RIVER NEAR CELO, NC" (not North Toe at Altapass). Site IDs left as-is pending Grace's call.
- 2026-11-06 (Pi job #1, M1): pairing. Stage = MeanGageHeight on same field_visit_id + exact time; fallback = nearest MeanGageHeight in the same visit within 2 h (recorded per row in `Measurement.pairing`); else dropped. On the current snapshot all 6,436 discharges across the 8 sites match exactly, so the fallback never fires. Added `Measurement.weight` and `Measurement.pairing` to the schema. Unknown `measurement_rated` values map to "Unspecified" (weight 1.5). Reference windows live in `pairing.reference_window()`.
