# OpenStreetMap discovery connector
This is a bounded, read-only connector for publicly available OpenStreetMap POI data via a shared Overpass API instance.

- User specifies coordinates, radius (100–3000m), and category; no collection of personal phone numbers or emails.
- Endpoint: `POST /api/discovery/osm`. Output up to 50 named POIs, includes source URLs; **not inserted automatically**.
- User reviews and selects results; `POST /api/discovery/osm/commit` requires explicit confirmation, validates OSM object links, deduplicates by merchant name/city and source URL, and creates an audit event with attribution.
- Public endpoint usage guarded by a 65-second in-process cooldown, no redirects, 25-second timeout, and 1MB maximum response. This pilot is not designed for bulk harvesting or a production crawler.
- Public OSM data is incomplete, may be stale, and may not accurately reflect business activity. Never infer revenue, ownership, marketing budgets, operational status, or consent to marketing.
- **Attribution required in any exported/published derivative:** © OpenStreetMap contributors; ODbL. See https://www.openstreetmap.org/copyright for database license and share-alike provisions. A business/legal review is required before a commercial release using an integrated OSM-derived dataset.
- Live Overpass calls are not tested in GitHub CI. Tests use deterministic mocks; success means program logic works, not that the upstream service is reachable.
