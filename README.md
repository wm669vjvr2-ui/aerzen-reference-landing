# AERZEN reference landing

Separate Python/FastAPI/Jinja2/SQLite project on branch `codex/reference-landing`. The existing `aerzen-psk-arus` repository and its branches are not used as a remote for this project. The new site was created from a sanitized tracked-file snapshot; no original Git history, environment files, database or runtime state was copied.

The user requested close reproduction from four supplier sites, without new design concepts and without catalog emphasis. Home now focuses on quotation, selection, supply, parts/service, repair, applications and company contacts, with actual client photos. Inner routes, secure request handling and operator tools are retained. All four links are recorded in `docs/reference-evidence.md`; only two yielded readable text. Exact visual matching remains blocked by reference access.

## Local launch

Use Python 3.12 or newer:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
AERZEN_SECURE_COOKIES=false AERZEN_PREVIEW_MODE=true AERZEN_BASE_URL=http://127.0.0.1:8027 .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8027 --no-access-log
```

Local URL: http://127.0.0.1:8027/. Data defaults to `~/.local/share/aerzen-reference-landing`, outside static files and separate from the original project's data.

During this session the existing installed Python runtime was used read-only from the neighboring project; no dependencies or settings there were changed.

## Operation and publication

Phone/email links work. Backend form submission, purchases and analytics are disabled by default. The request section provides a working mailto action; it opens the user's mail app and does not send a message automatically. Enabling server-side lead handling requires confirmed owner/privacy settings and actual operator delivery. The disabled form is labeled.

No public HTTPS hosting is configured. Before launch: obtain visible versions of the missing references, confirm material rights, approve business data/privacy documents and retention, configure a compatible Python host with persistent private SQLite storage, permanent secret and HTTPS origin. Do not expose server code, .env, .git or database files; do not change the Python stack for hosting. No temporary tunnel or owner-only preview counts as the public handoff.

## Model comparisons added 14 October 2026

`/alternatives` and three family pages cover 17 Chinese Huadong HDSR / Mingtian RSR models and six ERSTVAK ERB models. ERSTVAK Chinese origin is unconfirmed. These are reference comparisons, explicitly not supplied inventory; they never become cart/feed offers. Requests stay on this separate site; there are no links or redirects to the main company website. Search frequency rankings are not established.

Primary sources and access/licensing limits: `docs/chinese-models-sources.md`. Verification: `docs/alternatives-verification.md`. No additional dependencies were installed.

## Checks

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app tests
.venv/bin/python -m pip_audit -r requirements.txt
```

Evidence and remaining gaps: `docs/verification.md`. Content/photo provenance: `docs/content-sources.md`, `content/asset-manifest.json`. Current selection and styling: `.ui-pattern-forge/selected-concept.json`, `docs/design-system.md`. Older motion documents describe retained optional inner-page assets, not this homepage.
