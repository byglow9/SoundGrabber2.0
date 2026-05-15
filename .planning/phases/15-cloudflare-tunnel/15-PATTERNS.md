# Phase 15: Cloudflare Tunnel - Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** `docker-compose.yml`, `scripts/deploy.sh`, `.env.example`, `api/main.py`, prior phase contexts

---

## File Classification

| File / Artifact | Role | Data Flow | Closest Analog | Quality |
|-----------------|------|-----------|----------------|---------|
| `15-01-PLAN.md` | ops plan | manual checkpoint | `14-CONTEXT.md` + `scripts/deploy.sh` | exact |
| `15-02-PLAN.md` | validation plan | public request/response | `api/main.py` `/health` + Phase 14 E2E gates | exact |
| `cloudflared` install steps | host operation | shell/manual | `scripts/notebook-setup.sh` and `scripts/deploy.sh` patterns | role-match |
| public frontend E2E checklist | UAT | browser/manual | Phase 14 E2E validation context | role-match |

---

## Pattern Assignments

### Host operation checklist

**Analog:** `scripts/deploy.sh`

Relevant pattern:
- `set -e` and explicit shell commands for host operations.
- Host-side changes requiring sudo are operator-controlled and should be checkpointed.
- Credentials are not managed by deploy scripts.

Phase 15 implication:
- Do not create a permanent `cloudflared` service automatically.
- Provide commands, pause for the operator, then verify outputs.

### Compose readiness before exposure

**Analog:** `docker-compose.yml`

Relevant pattern:
- `api` is the only service with host port mapping: `8000:8000`.
- `redis` and `bgutil` remain internal with no host `ports:`.
- `api` and `worker` read `.env`.

Phase 15 implication:
- Tunnel origin is `http://localhost:8000`.
- Validate Compose and local `/health` before starting `cloudflared`.
- Do not add `cloudflared` to Compose in this phase.

### Health endpoint

**Analog:** `api/main.py`

Relevant pattern:
- `GET /health` returns `{"status": "ok"}` with HTTP 200 when Redis responds.
- This is already the platform liveness signal.

Phase 15 implication:
- Use `/health` as both local and public smoke test.
- If public `/health` fails but local `/health` passes, focus debugging on `cloudflared`/URL/network.

### Environment credential gate

**Analog:** `.env.example`

Relevant defaults:
- `ADMIN_PASSWORD=change-me-locally`
- `ADMIN_SESSION_SECRET=change-me-to-a-long-random-secret`

Phase 15 implication:
- Before public tunnel starts, block if the real notebook `.env` uses either example value.
- Do not print actual secret values in summaries or planning artifacts.

### Manual E2E validation

**Analog:** Phase 14 E2E context

Relevant pattern:
- Live YouTube/cookies validation is a human gate.
- Success is not just API response; WAV must be downloadable and analysis output must exist.

Phase 15 implication:
- The primary E2E proof is browser-driven through the public URL.
- API/curl is diagnostic only.
