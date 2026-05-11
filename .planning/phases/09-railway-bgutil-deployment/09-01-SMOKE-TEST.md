# 09-01 Smoke Test — Railway bgutil Deployment Verification

**Date:** 2026-05-11
**Phase:** 09-railway-bgutil-deployment
**Plan:** 01
**Executor:** Claude (sequential)

---

## Task 1 — Celery Worker Deployment 10ec98b3

> Note: deployment `10ec98b3` was REMOVED/superseded by a newer redeploy triggered after BGUTIL_BASE_URL was set. The active deployment as of 2026-05-11 is `2d871c8e-ece4-44a9-9fa9-f0c4b65021c9`.

**deployment_status: SUCCESS**
**deployment_id:** 2d871c8e-ece4-44a9-9fa9-f0c4b65021c9
**created_at:** 2026-05-11T17:07:39.188Z
**completed_at:** 2026-05-11T17:11:49.309Z
**attempts_until_success:** 1 (already SUCCESS on first query)

### Deployment Logs (last 35 lines)

```
Starting Container                                          [2026-05-11T17:11:47.794Z]
[INFO] MusicExtractorSVM: no classifier models were configured by default
System ffprobe not found via shutil.which(); falling back to imageio-ffmpeg path:
  /app/.venv/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffprobe
/app/.venv/.../celery/platforms.py:841: SecurityWarning: You're running the worker
  with superuser privileges: this is absolutely not recommended!
--- ***** -----
-- ******* ---- Linux-6.18.15+deb13-cloud-amd64-x86_64-with-glibc2.36 2026-05-11 17:11:48
- *** --- * ---
- ** ---------- [config]
- ** ---------- .> app:         soundgrabber:0x7f44005cdd30
- ** ---------- .> transport:   redis://default:**@redis.railway.internal:6379//
- ** ---------- .> results:     redis://default:**@redis.railway.internal:6379/
- *** --- * --- .> concurrency: 3 (prefork)
 -------------- celery@069e1c303810 v5.6.3 (recovery)
-- ******* ---- .> task events: OFF (enable -E to monitor tasks in this worker)
--- ***** -----
 -------------- [queues]
                .> celery           exchange=celery(direct) key=celery

[tasks]
  . soundgrabber.process_job

[2026-05-11 17:11:48,384: INFO/MainProcess] Connected to redis://default:**@redis.railway.internal:6379//
[2026-05-11 17:11:48,418: INFO/MainProcess] mingle: searching for neighbors
[2026-05-11 17:11:49,480: INFO/MainProcess] mingle: sync with 1 nodes
[2026-05-11 17:11:49,480: INFO/MainProcess] mingle: sync complete
[2026-05-11 17:11:49,549: INFO/MainProcess] celery@069e1c303810 ready.
```

### Gate Checks

| Gate | Expected | Result |
|------|----------|--------|
| celery@ present | yes | PASS — `celery@069e1c303810 v5.6.3` |
| ready. present | yes | PASS — `celery@069e1c303810 ready.` |
| [tasks] + process_job | yes | PASS — `soundgrabber.process_job` registered |
| forbidden-string-1: bgutil env var missing msg | absent | PASS — not found in logs |
| forbidden-string-2: tcp refused error | absent | PASS — not found in logs |
| forbidden-string-3: py socket exception | absent | PASS — not found in logs |
| forbidden-string-4: bgutil connect fail msg | absent | PASS — not found in logs |
| forbidden-string-5: bgutil dns not known | absent | PASS — not found in logs |

**Task 1 result: ALL GATES PASSED**

---

## Task 2 — Uvicorn Deployment 02cda13b — deployment_status: SUCCESS

> Note: deployment `02cda13b` was REMOVED/superseded. The active Uvicorn deployment is `498fa759-a330-4aa1-bd9f-8b7a14a0f60d`.

**deployment_status: SUCCESS**
**deployment_id:** 498fa759-a330-4aa1-bd9f-8b7a14a0f60d
**created_at:** 2026-05-11T17:07:38.792Z
**completed_at:** 2026-05-11T17:08:25.107Z

### Deployment Logs (startup)

```
Starting Container                                          [2026-05-11T17:08:20.777Z]
[INFO] MusicExtractorSVM: no classifier models were configured by default
System ffprobe not found via shutil.which(); falling back to imageio-ffmpeg path:
  /app/.venv/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffprobe
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.              <<< POSITIVE GATE ✓
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)  <<< POSITIVE GATE ✓
INFO:     100.64.0.2:47227 - "GET /health HTTP/1.1" 200 OK
```

### Gate Checks

| Gate | Expected | Result |
|------|----------|--------|
| `Application startup complete` | present | PASS |
| `Uvicorn running on` | present | PASS — `Uvicorn running on http://0.0.0.0:8080` |
| forbidden-string-1: bgutil env var missing msg | absent | PASS — not found in logs |
| forbidden-string-2: tcp refused error | absent | PASS — not found in logs |
| forbidden-string-3: py socket exception | absent | PASS — not found in logs |
| forbidden-string-4: bgutil connect fail msg | absent | PASS — not found in logs |

**Task 2 result: ALL GATES PASSED**

---

## Task 3 — Uvicorn Public URL — health check 200 (responding)

**discovery_method:** Railway GraphQL API — `service.serviceInstances.edges.node.domains.serviceDomains`
**hostname:** soundgrabber-test.up.railway.app
**public_url:** https://soundgrabber-test.up.railway.app

### Health Check Verification

```
curl -sS -o /dev/null -w '%{http_code}' https://soundgrabber-test.up.railway.app/health
→ 200

curl -sS https://soundgrabber-test.up.railway.app/health
→ {"status":"ok"}
```

**health_status: 200 OK** — GET /health → 200 (health endpoint responding)

Result: `health` endpoint returned status code `200`

**Task 3 result: PASSED — URL descoberta e /health=200 confirmado**

---

## Task 4 — End-to-End Smoke Test

> Awaiting user-provided YouTube beat URL. This section will be completed after the checkpoint:human-verify.

**status:** pending_human_input

---

*File created by executor agent — 2026-05-11T17:49:57Z*
