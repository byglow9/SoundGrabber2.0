---
created: 2026-05-29T00:00:00-03:00
title: Plan relational storage for editorial content
area: infra
files:
  - api/main.py
  - api/config.py
  - docker-compose.yml
---

## Problem

SoundGrabber currently stores editorial content in Redis with JSON fallback files:

- Som da Semana current release and history
- System updates / changelog

This is appropriate for the current lightweight workflow, but future editorial features may need relational storage for durable history, richer filtering, audits, drafts, tags, and migrations.

## Future Plan

Create a future phase to add a relational database for persistent editorial content while keeping Redis for operational data.

Candidate tables:

- `featured_releases`
- `system_updates`
- `editorial_links`
- `artists`
- `producers`
- `admin_audit_log`

Redis should remain responsible for:

- Celery broker/result backend
- rate limiting
- job registry
- short-lived operational cache

The relational database should become responsible for:

- Som da Semana current/history records
- SoundGrabber system updates
- future curated editorial content
- admin audit history

## Notes

Do not introduce the database until the editorial surface grows enough to justify migrations, backups, deployment config, and maintenance overhead.
