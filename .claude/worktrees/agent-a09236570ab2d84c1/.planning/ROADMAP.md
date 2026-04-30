# Roadmap — SoundGrabber

**Project:** SoundGrabber
**Milestone:** v1 — Public launch
**Granularity:** Standard
**Coverage:** 19/19 requirements mapped
**Last updated:** 2026-04-29

---

## Phases

- [ ] **Phase 1: Processing Pipeline** - Prove yt-dlp + FFmpeg + librosa work end-to-end from the target host before building anything else
- [ ] **Phase 2: API Layer** - Wrap the working pipeline in FastAPI + Celery + Redis with a job-queue HTTP contract
- [ ] **Phase 3: Hardening** - Rate limiting, URL validation, duration caps, and disk safety before public exposure
- [ ] **Phase 4: Frontend** - Browser-based user flow built against the real, hardened API
- [ ] **Phase 5: Visual Identity** - Y2K / phpBB / Tibia authentic 2000s aesthetic applied to the complete frontend

---

## Phase Details

### Phase 1: Processing Pipeline
**Goal**: A standalone Python script proves the download-convert-analyze pipeline works from the production host
**Depends on**: Nothing (first phase)
**Requirements**: CORE-03, CORE-04, CORE-05, ANALYSIS-01, ANALYSIS-02, ANALYSIS-03, ANALYSIS-04
**Success Criteria** (what must be TRUE):
  1. Running the script with a YouTube URL produces a valid WAV file with no manual intervention
  2. The script correctly refuses URLs pointing to videos longer than 15 minutes and prints an explanatory message
  3. BPM is detected and printed; the value is plausible (within 30% of the track's actual feel-tempo across trap, lo-fi, and house test URLs)
  4. Musical key is detected and printed in both standard notation and Camelot notation
  5. Half-time and double-time BPM values are computed and displayed alongside the primary BPM without re-running analysis
**Plans**: TBD

### Phase 2: API Layer
**Goal**: The pipeline is accessible over HTTP via a job-queue contract exercisable by curl
**Depends on**: Phase 1
**Requirements**: CORE-01, CORE-02, CORE-06
**Success Criteria** (what must be TRUE):
  1. POST /jobs with a valid YouTube URL returns a job ID immediately (under 300ms)
  2. GET /jobs/{id} polled every 2 seconds returns status transitions (queued → downloading → converting → analyzing → done) and, when done, includes BPM, key, and a download URL
  3. GET /files/{id} streams the WAV to disk without loading the entire file into server memory
  4. Three concurrent curl jobs submitted simultaneously all complete without the API becoming unresponsive
**Plans**: TBD

### Phase 3: Hardening
**Goal**: The API safely handles abuse, malformed input, and resource exhaustion before users reach it
**Depends on**: Phase 2
**Requirements**: UX-03, UX-04
**Success Criteria** (what must be TRUE):
  1. Submitting a non-YouTube URL or a malformed URL returns a clear error response (not a 500) explaining what was wrong
  2. Submitting a YouTube URL for a video longer than 15 minutes is rejected before the download starts, with an error message stating the duration limit
  3. A single IP submitting more than 3 jobs per minute receives a 429 response with a human-readable message
  4. Killing a worker mid-job leaves no orphaned files in /tmp after the next background sweeper cycle (within 20 minutes)
**Plans**: TBD

### Phase 4: Frontend
**Goal**: Users can complete the full workflow in a browser without using curl or reading API docs
**Depends on**: Phase 3
**Requirements**: CORE-01, UX-01, UX-02
**Success Criteria** (what must be TRUE):
  1. A user can paste a YouTube URL, click one button, and see real-time stage labels (Downloading... / Converting... / Analyzing...) update as the job progresses
  2. Before clicking download, the page displays the estimated WAV file size so the user knows what to expect
  3. BPM, key, Camelot notation, and half-time/double-time values are all visible on the result card without scrolling
  4. The download button triggers a direct WAV file save with no account, no email, and no redirect to an external site
**Plans**: TBD
**UI hint**: yes

### Phase 5: Visual Identity
**Goal**: The site looks and feels like it was literally built in 2000-2005, not like a modern site imitating the past
**Depends on**: Phase 4
**Requirements**: VISUAL-01, VISUAL-02, VISUAL-03, VISUAL-04, VISUAL-05
**Success Criteria** (what must be TRUE):
  1. Before writing any CSS, the phase begins with a documented research step: inspecting Wayback Machine snapshots of real phpBB, Tibia fansites, and Orkut pages from 2000-2005 to capture exact construction patterns (table layouts, hex palettes, border styles, font stacks)
  2. The layout is built with HTML tables — not flexbox, not grid — with no CSS variables or custom properties anywhere in the stylesheet
  3. Fonts render in a bitmap/pixel face (VT323, Fixedsys, or Courier New) with font-smoothing explicitly disabled; no Google Fonts CDN call introduces modern rendering
  4. The dark-mode color palette is expressed entirely in raw hex values (no hsl(), no rgba() with floats, no CSS variables) drawn from actual period references
  5. A developer unfamiliar with the project can open the HTML source and reasonably believe it was written in 2002
**Plans**: TBD
**UI hint**: yes

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Processing Pipeline | 0/? | Not started | - |
| 2. API Layer | 0/? | Not started | - |
| 3. Hardening | 0/? | Not started | - |
| 4. Frontend | 0/? | Not started | - |
| 5. Visual Identity | 0/? | Not started | - |

---

## Coverage Map

| Requirement | Phase |
|-------------|-------|
| CORE-01 | Phase 2 |
| CORE-02 | Phase 2 |
| CORE-03 | Phase 1 |
| CORE-04 | Phase 1 |
| CORE-05 | Phase 1 |
| CORE-06 | Phase 2 |
| ANALYSIS-01 | Phase 1 |
| ANALYSIS-02 | Phase 1 |
| ANALYSIS-03 | Phase 1 |
| ANALYSIS-04 | Phase 1 |
| UX-01 | Phase 4 |
| UX-02 | Phase 4 |
| UX-03 | Phase 3 |
| UX-04 | Phase 3 |
| VISUAL-01 | Phase 5 |
| VISUAL-02 | Phase 5 |
| VISUAL-03 | Phase 5 |
| VISUAL-04 | Phase 5 |
| VISUAL-05 | Phase 5 |

**Mapped: 19/19**

---

*Roadmap created: 2026-04-29*
