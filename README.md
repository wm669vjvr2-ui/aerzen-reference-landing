# AERZEN reference landing

Separate Python/FastAPI/Jinja2/SQLite project on branch `codex/reference-landing`. The existing `aerzen-psk-arus` repository and its branches are not used as a remote for this project. The new site was created from a sanitized tracked-file snapshot; no original Git history, environment files, database or runtime state was copied.

Latest selected direction (14 October 2026): a separate supplier site based on the verified structure of Erstvak.com, with a black/yellow palette and AERZEN models. The previous main-site layout and photos are no longer rendered. Home includes a multi-row header, industrial hero, applications, equipment categories, six work steps, services, company information, technical articles and an engineering request. New thematic photographs use the free Unsplash License; exact sources and limitations are in `docs/photo-sources.md`. AERZEN model pages use text nameplates pending verified model photographs.

The reference home, rotary category and product page yielded readable structure; browser visual access failed. This is a structural adaptation, not a verified pixel-identical copy. Erstvak business claims, reviews, prices, contacts, brand identity and project claims are not represented as the client's. All navigation and requests stay on this independent site.

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

No public HTTPS hosting is configured. Before launch: approve business data/privacy documents and retention, configure a compatible Python host with persistent private SQLite storage, permanent secret and HTTPS origin. Old unused media remain in source history and are not part of the displayed interface; exclude unapproved legacy assets from a production package. Do not expose server code, .env, .git or database files; do not change the Python stack for hosting. No temporary tunnel or owner-only preview counts as the public handoff.

## Model comparisons added 14 October 2026

`/alternatives` and three family pages cover 17 Chinese Huadong HDSR / Mingtian RSR models and six ERSTVAK ERB models. ERSTVAK Chinese origin is unconfirmed. These are reference comparisons, explicitly not supplied inventory; they never become cart/feed offers. Requests stay on this separate site; there are no links or redirects to the main company website. Search frequency rankings are not established.

Primary sources and access/licensing limits: `docs/chinese-models-sources.md`. Verification: `docs/alternatives-verification.md`. No additional dependencies were installed.

The price follow-up also includes Chinese models. `docs/price-verification.md` records live primary-page checks: no comparable numerical prices were confirmed, so no unsupported 30% discount or sale price was published. Reference pages show quote-only primary-source pricing with the checked date and source link.

## Checks

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app tests
.venv/bin/python -m pip_audit -r requirements.txt
```

Evidence and remaining gaps: `docs/storefront-verification.md` (current) and `docs/verification.md` (13 October snapshot). Content/photo provenance: `docs/content-sources.md`, `docs/photo-sources.md`. Current selection and styling: `.ui-pattern-forge/selected-concept.json`, `docs/design-system.md`, `static/css/storefront.css`. Older motion documents and styles are historical; no 3D runtime is loaded by the current interface.
