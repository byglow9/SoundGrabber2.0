# Repository Guidelines

## Project Structure & Module Organization

SoundGrabber is a Python 3.11 service with a small static frontend. The FastAPI app lives in `api/`: routes in `api/main.py`, Celery jobs in `api/tasks.py`, and settings in `api/config.py`. Core download, conversion, and audio analysis logic is in `pipeline.py`. Frontend HTML, CSS, JavaScript, fonts, and image assets are under `static/`; source border assets also exist in `bordas/`. Tests are in `tests/`, with fixtures in `tests/fixtures/`. Operational scripts are in `scripts/`.

## Build, Test, and Development Commands

- `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt`: create and populate the local virtualenv.
- `cp .env.example .env`: create local configuration. Keep real secrets out of Git.
- `./start.sh`: starts Redis if needed, runs a Celery worker, and serves FastAPI/Uvicorn at `http://127.0.0.1:8000`.
- `.venv/bin/python -m pytest`: run the default test suite defined by `pytest.ini`.
- `.venv/bin/python -m pytest -m integration`: run tests that need FFmpeg and fixture WAV files.
- `docker compose up --build`: run the containerized stack for deploy-like validation.
- `scripts/predeploy-check.sh`: run production deploy gates, security checks, and deploy tests.

## Coding Style & Naming Conventions

Use 4-space indentation for Python and keep type hints on changed functions where practical. Follow the existing style: constants in `UPPER_SNAKE_CASE`, functions and variables in `snake_case`, and Pydantic models in `PascalCase`. Keep comments useful, especially around auth, rate limiting, temporary files, and deploy constraints. Frontend code is vanilla HTML/CSS/JS; keep filenames lowercase and reuse existing assets.

## Testing Guidelines

Pytest discovers `tests/test_*.py`, `Test*` classes, and `test_*` functions. Mark environment-heavy tests with existing markers: `integration` for FFmpeg/fixture WAV coverage and `e2e` for live YouTube, cookies, Redis, and worker dependencies. Prefer mocks for yt-dlp, Redis, and Celery in unit tests. Add regression tests when changing validation, job status contracts, file streaming, security gates, or pipeline errors.

## Commit & Pull Request Guidelines

Git history uses short imperative messages, often with Conventional Commit scopes such as `fix(ui): ...` and `docs(readme): ...`; follow that pattern when possible. Keep commits focused. Pull requests should explain the behavior change, list tests run, call out config or deploy impacts, link issues, and include screenshots or recordings for visible frontend changes.

## Security & Configuration Tips

Never commit `.env`, cookies, Redis dumps, tokens, or generated private data. Use `.env.example` for documented defaults only. Production must keep `DEV_MODE=false`, strong admin secrets, passworded Redis URLs, and protected `YTDLP_CACHE_DIR`.
