# Omnidoc Nexus

A private vault for personal and family documents (Aadhaar, PAN, passport and others) that you can **ask questions in plain language**. Upload a document, and the app reads it, stores it encrypted, and lets you chat with it: "What is my PAN number?", "Send my passport to my brother."

Everything runs on free tiers, every user's data is isolated from every other user's, and the AI never sees your ID numbers.

## What it does

- **Upload and read.** PDFs and photos are read with text extraction and OCR (Tesseract). The type of document, and the numbers in it, are detected automatically.
- **Check numbers.** Aadhaar numbers are validated with the Verhoeff checksum. A number that fails the check is flagged, and you can type it in by hand.
- **Family members.** File documents under yourself, your spouse, your parents and so on.
- **Chat with your documents.** Questions are answered from your own document text only (retrieval-augmented generation). When you ask for a number, the app returns it directly, so the language model never receives it.
- **Email from the chat.** The app prepares the email and an attachment, shows a card, and sends **only after you click Send**. Senders: Gmail SMTP, Gmail API, and sendlib (disabled until its API details are added), tried in order with fallback.
- **Choose your AI.** Groq, Mistral, Gemini or OpenRouter, selectable in the app, with fallback.
- **Safe by default.** Per-user rate limits, upload limits, lock-out after repeated failed logins, and nothing sensitive in logs.

## How your data is protected

| Layer | What it does |
|---|---|
| Login | Passwords hashed with bcrypt; sessions use signed tokens (JWT). The user is taken from the token only, never from the request body. |
| Isolation | Every table carries a `user_id`; every query filters by it; asking for someone else's item returns "not found". The vector search is filtered by `user_id` as well. |
| Encryption | Files, extracted text and detected numbers are encrypted with a key derived separately for each user (HKDF from one master `VAULT_KEY`, Fernet). |
| Vector store | Pinecone holds only vectors, ids and small filter fields. Document text stays encrypted in Postgres. |
| Network | In production only Caddy is reachable (ports 80 and 443). The database, API and UI are internal. HTTPS is automatic. |
| API surface | The interactive API docs are off in production. |

## Architecture

```
Browser ──HTTPS──> Caddy ──> Streamlit UI ──> FastAPI (/v1) ──> Postgres (encrypted text, records)
                      └─────── /api/* ────────────┘      ├──> Pinecone (vectors only)
                                                          ├──> Encrypted file vault (volume)
                                                          ├──> LLM provider (Groq / Mistral / Gemini / OpenRouter)
                                                          └──> Email (SMTP / Gmail API / sendlib)
```

Project layout:

```
omnidoc/
  api/         FastAPI app, routes, errors, per-user rate limits
  core/        settings, encryption, security helpers
  db/          SQLAlchemy models and sessions
  ingestion/   file reading, OCR, chunking, number detection
  providers/   swappable back ends: llm, embeddings, vectorstore, email, storage
  services/    business logic: documents, people, chat, retrieval, email
  ui/          Streamlit chat app and its API client
scripts/       init_db, try_api (full test run), reindex, gmail_authorize, ...
deploy/        production compose file, Caddyfile, update and backup scripts
.github/       CI: tests, then build and publish the Docker image
```

## API versioning

All endpoints live under `/v1` (for example `/v1/auth/login`, `/v1/documents`, `/v1/chat`). Only `/health` is unversioned. Every response carries an `X-API-Version` header. A change that would break existing clients goes into a new `/v2` next to `/v1`; compatible additions stay in `/v1`.

## Run it on your computer

You need Python 3.12, Docker, and Tesseract OCR.

```bash
# 1. Install
python -m venv .venv
.venv\Scripts\activate            # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

# 2. Configure
copy .env.example .env            # then fill it in (see "Settings" below)

# 3. Start the database
docker compose up -d db

# 4. Create the tables, then start the API and the app (two terminals)
python -m scripts.init_db
uvicorn omnidoc.api.main:app --reload
streamlit run omnidoc/ui/app.py
```

The database connection uses the pure-Python `pg8000` driver (`postgresql+pg8000://...`), which also works on locked-down Windows machines. If you run Postgres in Docker and connect from your own computer, publish the port to your machine only, in a `docker-compose.override.yml` that you keep out of Git:

```yaml
services:
  db:
    ports:
      - "127.0.0.1:5432:5432"
```

On Windows, set `TESSERACT_CMD` to the full path of `tesseract.exe` if it is not on your PATH.

## Settings

Set these in `.env`. Never commit that file.

| Setting | Purpose |
|---|---|
| `DATABASE_URL`, `POSTGRES_PASSWORD` | Database connection and password (they must match) |
| `VAULT_KEY` | Master encryption key (a Fernet key). **Losing it makes stored documents unreadable.** |
| `VAULT_DIR` | Where encrypted files are stored |
| `JWT_SECRET` | Signing key for logins, at least 32 characters |
| `PINECONE_API_KEY`, `PINECONE_INDEX`, `PINECONE_REGION` | Vector store |
| `GROQ_API_KEY`, `MISTRAL_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY` | AI providers (set the ones you use) |
| `DEFAULT_LLM` and the `*_MODEL` overrides | Which model answers by default |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Email through Gmail with an app password |
| `EMAIL_PROVIDER_ORDER` | Order in which email senders are tried, for example `smtp,gmail` |
| `ENABLE_DOCS` | `true` shows the API docs at `/docs` (keep `false` in production) |
| `TESSERACT_CMD` | Path to Tesseract if it is not on your PATH |

To generate keys:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # VAULT_KEY
openssl rand -base64 48                                                                    # JWT_SECRET
```

## Tests

`scripts/try_api.py` runs the whole API against a real database with fake AI, email and vector services. It checks login, uploads, isolation between users, chat, email confirmation, rate limits and deletion.

```bash
python -m scripts.try_api
```

Every line should end in `OK`. The same script runs in CI on every push.

## Deployment

Pushing to `main` runs the tests, builds one Docker image (used for both the API and the app), and publishes it to GitHub Container Registry. The server pulls the new image by itself every 5 minutes, so no deploy keys are needed.

On the server (`~/omnidoc`):

| File | Purpose |
|---|---|
| `docker-compose.yml` | Database, API, app and Caddy (from `deploy/docker-compose.prod.yml`) |
| `Caddyfile` | HTTPS, security headers, and routing `/api/*` to the API |
| `.env` | Production secrets (server only, `chmod 600`) |
| `update.sh` | Pulls the new image and restarts (run by cron every 5 minutes) |
| `backup.sh` | Nightly database dump and vault archive, 7 days kept |

See `deploy/env.production.example` for the production settings. Use new secrets in production, not your development ones.

### Backups and restore

`backup.sh` writes `~/backups/db-<time>.sql.gz` and `vault-<time>.tar.gz`. The `.env` file is deliberately not included: keep a copy of it in a password manager, because without `VAULT_KEY` the vault cannot be decrypted.

To test a restore without touching live data:

```bash
cd ~/omnidoc
docker compose exec -T db psql -U omnidoc -d postgres -c "CREATE DATABASE restore_test;"
gunzip -c ~/backups/db-<time>.sql.gz | docker compose exec -T db psql -U omnidoc -d restore_test -q
docker compose exec -T db psql -U omnidoc -d postgres -c "DROP DATABASE restore_test;"
```

### Logs

Containers log to the system journal (kept for 2 weeks):

```bash
journalctl -t omnidoc-api-1 --since "1 hour ago"
docker compose logs api --tail 50
```

### Rebuilding the search index

If the Pinecone index is lost, emptied or replaced, rebuild it from the database. This never changes the database, and running it twice is harmless.

```bash
docker compose exec api python -m scripts.reindex --dry-run   # count only
docker compose exec api python -m scripts.reindex             # rebuild
```

If you change to an embedding model with a different vector size, point `PINECONE_INDEX` at a new empty index first.

## Optional: Gmail API

Email works through SMTP by default. To use the Gmail API instead, create an OAuth "Desktop app" client in Google Cloud, save it as `data/gmail/credentials.json`, then run `python -m scripts.gmail_authorize` and sign in once. Publish the consent screen so the sign-in does not expire after 7 days.

## Status

Working: sign-up and login, uploads, family members, chat, email with confirmation, versioned API, automatic deployment, backups, log retention, re-indexing.
Not enabled: the sendlib email sender (waiting for its API details).
Ideas for later: single-use email confirmation tokens, database migrations (Alembic), automatic off-server backup copies.
