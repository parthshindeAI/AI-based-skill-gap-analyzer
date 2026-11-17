# SkillForge AI — Skill Gap Analyzer

A FastAPI and vanilla-JavaScript career guidance app for students and training-and-placement teams. It supports account creation, skill assessments, skill-gap analysis, personalized roadmaps, progress tracking, resume parsing/PDF generation, and an admin workspace.

## Features

- Student registration, login, and profile updates
- Batch and adaptive skill assessments
- Role-based skill-gap analysis and readiness estimates
- Personalized learning roadmaps and stage completion tracking
- PDF/DOCX resume parsing and ATS-oriented PDF generation
- Admin role/question management, custom test assignment, student analytics, and roadmap assignment
- PostgreSQL-backed application-state persistence for hosted deployments
- Docker Compose development/deployment setup and CI test workflow

## Run locally

Requirements: Python 3.12 or later and Docker Desktop (for the PostgreSQL-backed setup).

1. From the project folder, create and activate a virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Create a local environment file and change the demo values:

   ```powershell
   Copy-Item .env.example .env
   ```

   `.env` is ignored by Git. The sample admin password is for local development only.

4. Start the app and PostgreSQL:

   ```powershell
   docker compose up --build
   ```

5. Visit:

   - App: <http://127.0.0.1:8000/>
   - Admin panel: <http://127.0.0.1:8000/admin>
   - API docs: <http://127.0.0.1:8000/docs>
   - Health: <http://127.0.0.1:8000/health>

The Compose setup uses the production configuration checks. Set `ADMIN_PASSWORD` to a unique value of at least 16 characters before starting it. For local development without Docker, set `APP_ENV=development` and run `uvicorn backend.api.main:app --reload`; without `DATABASE_URL`, data is in memory and resets when the process restarts.

## Deployment

Run the app and PostgreSQL together for local container testing:

```sh
docker compose up --build
```

For a hosted deployment:

- Configure `APP_ENV=production`, `ADMIN_USERNAME`, a unique `ADMIN_PASSWORD` (at least 16 characters), `DATABASE_URL`, and `ALLOWED_ORIGINS` in the hosting provider's secret/environment settings. Do not commit `.env`.
- Use a managed PostgreSQL database and keep backups enabled.
- The container listens on `PORT` (8000 by default), so platforms can supply their assigned port.
- Use HTTPS at the hosting provider/reverse proxy.
- Keep the service to one running application instance for this MVP's shared-state model. The database lock prevents conflicting snapshot writes, but serializes API requests; this design is for a small portfolio deployment, not high-throughput production. A larger service should replace the aggregate snapshot with normalized, per-feature database tables and migrations.

No cloud resources are provisioned by this repository. Choose a hosting provider, connect its PostgreSQL database, set the environment variables, and deploy the container. `compose.yaml` is intended for local validation and small demos, not as production high-availability infrastructure.

### Deploying on Render

1. Push the `mini_p` project directory (the directory containing this README and `Dockerfile`) to a Git provider. Do not push `.env`, virtual environments, or `backend/services/auth_data.json`.
2. Create a Render PostgreSQL database and a Docker Web Service from that repository. Use the same region for both.
3. Set the Web Service health check path to `/health` and add these environment variables:
   - `APP_ENV=production`
   - `ADMIN_USERNAME` and a unique `ADMIN_PASSWORD` of at least 16 characters
   - `DATABASE_URL` set to the database's **internal** connection URL
   - `ALLOWED_ORIGINS` set to the exact public app origin (for example, `https://your-service.onrender.com`, with no trailing slash)
   - `MIGRATE_LEGACY_AUTH_DATA=0`
4. Deploy and verify `/health`, registration, login, assessment, roadmap, and resume flows. Check Render logs for startup or database errors.

The app uses Render's assigned `PORT` when provided and defaults to port 8000 for local Compose runs. Keep a database backup before changing or deleting the database. Review Render's current plan limits and pricing before creating resources.

## Persistence and security notes

- With `DATABASE_URL` set, student accounts, active sessions, assessments, resume-derived data, progress, and admin-managed state are saved in PostgreSQL. The application initializes its state table on startup.
- To explicitly import legacy local accounts, set `MIGRATE_LEGACY_AUTH_DATA=1` before the first database startup. The import runs only when the database state table is empty, and old sessions are invalidated. Keep the legacy JSON file private; never commit or copy it to a hosted environment.
- Without `DATABASE_URL`, local development uses in-memory state. The legacy `backend/services/auth_data.json` path is not used when database persistence is configured.
- The production configuration refuses to start without a database URL and a non-default admin password.
- Configure exact trusted origins in `ALLOWED_ORIGINS` if a separate frontend needs cross-origin access. The bundled frontend is served by the same app.
- The current token/session approach is suitable for a portfolio MVP. Before handling real student data, add session expiry/revocation, rate limiting, audit logging, privacy/retention policies, and a security review.

## Tests

Run the backend tests:

```powershell
python -m pytest -q
```

Or, from a POSIX shell:

```sh
sh scripts/run-tests.sh
```

The GitHub Actions workflow runs tests against PostgreSQL. JavaScript syntax can be checked without a frontend build:

```powershell
Get-ChildItem .\frontend\assets\*.js | ForEach-Object { node --check $_.FullName }
```

## API overview

- `POST /api/register`, `POST /api/login`, `GET /api/profile`
- `GET /api/assessment/start`, `POST /api/assessment/submit`
- `POST /api/assessment/adaptive/start`, `POST /api/assessment/adaptive/answer`
- `GET /api/skill-gap/analyze`, `GET /api/roadmap`
- `GET /api/progress`, `POST /api/progress/complete`
- `POST /api/resume/parse`, `POST /api/resume/preview`, `POST /api/resume/generate`
- `/api/admin/*` for admin authentication and management APIs

OpenAPI/Swagger documentation is available at `/docs` when the service is running.
