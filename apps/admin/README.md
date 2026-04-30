# Admin App

Reserved for the future lightweight editorial review interface. There is no standalone admin UI
implemented here yet.

Current editorial/admin capability lives in:

- FastAPI admin routes under `apps/api/poi_curator_api/routes/admin.py`
- editorial mutation services under `packages/editorial`
- database tables for POI editorials, aliases, evidence, match diagnostics, and theme review
- CSV/Markdown/JSON exports under `reports`

Build a UI here only when the API/export workflow is too slow for recurring review work.
