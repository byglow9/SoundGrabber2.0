# Feature Landscape

**Domain:** YouTube audio downloader with music analysis (BPM + key detection) for underground/bedroom producers
**Researched:** 2026-04-29
**Confidence:** HIGH for table stakes (verified across multiple tools); MEDIUM for differentiators (community patterns + tool gaps); HIGH for anti-features (user complaint data)

---

## Table Stakes

Features users expect. Missing = product feels incomplete or untrustworthy.

| Feature | Why Expected | Complexity | Underground Producer Relevance | Dependencies |
|---|---|---|---|---|
| Paste URL and trigger download | Every tool does this; it's the entry point | Low | Core: producers find beats on YouTube, not via file upload | None |
| Real-time processing feedback (progress indicator) | Downloading + converting + analyzing takes 10-60s; silence reads as broken | Low-Med | High: producers are impatient, they close tabs fast | Download pipeline |
| Direct WAV file download (no email, no signup) | Cobalt, y2mate, snapsave — all offer no-account download; gating = drop-off | Low | Critical: underground producers distrust signup walls | Conversion pipeline |
| BPM display after analysis | TuneReveal, vocalremover.org, tunebat all show BPM as baseline output | Med | Critical: producers need BPM before setting DAW tempo | Audio analysis |
| Musical key display (e.g. F# minor) | Every key/BPM tool shows key; standard expectation in 2025 | Med | Critical: producers need key before writing chords or picking samples to layer | Audio analysis |
| Mobile-usable layout | 40-60% of web traffic is mobile; producers browse YouTube on phone | Low-Med | Medium: bedroom producers often reference YouTube on phone while working at desk | None |
| HTTPS / no sketchy redirects | y2mate, snapsave reputation destroyed by malware + redirects; users are alert to this | Low | High: underground community spreads word fast about shady tools | Infrastructure |
| Fast result (under 60 seconds end-to-end) | Competing tools can often return in 15-30s; anything over 90s loses users | High (infra) | High: producers iterate fast; waiting kills flow state | Infra + analysis pipeline |

---

## Differentiators

Features that set SoundGrabber apart. Not expected by users, but meaningfully valued when present.

| Feature | Value Proposition | Complexity | Underground Producer Relevance | Dependencies |
|---|---|---|---|---|
| Retro Y2K / 2000s internet aesthetic (phpBB / Tibia / Orkut feel) | No other downloader does this; it's a cultural statement, not just a skin — it signals "this was made for us, not for everyone" | Low-Med (CSS/design work) | Very high: underground producers grew up in this era; the aesthetic creates instant belonging | None — pure design |
| Combined download + analysis in one workflow | Current tools are siloed: download somewhere, then upload to tunebat or vocalremover to get key/BPM; SoundGrabber collapses this into one step | Med (orchestration) | Critical differentiator: this is the exact pain point — producers go to 2-3 tools to do what SoundGrabber does in one | Download + Analysis must be coupled |
| Camelot wheel notation alongside standard key | Producers who use harmonic mixing (common in hip-hop, lo-fi, trap, house) need Camelot codes (e.g. 4A instead of just "Ab minor") — Mixed In Key popularized this | Low (mapping table, no extra analysis needed) | High: any producer doing sample-based work or layering tracks uses Camelot | Key detection result |
| Confidence indicator on BPM/key results | Librosa and Essentia can be wrong — especially on complex or unconventional beats; showing "95% confidence" or flagging low-confidence results builds trust and manages expectations | Med (expose model confidence scores) | Medium: producers who have been burned by wrong BPM detection will appreciate honesty | Audio analysis pipeline |
| Clean waveform thumbnail of the audio | A simple visual representation of the track (peaks, energy distribution) gives producers instant pattern recognition — is it a 4-bar loop? Does it have a drop? | Med-High (wavesurfer.js or similar in-browser) | Medium: useful for referencing structure, but not blocking | Download + WAV file |
| Half-time / double-time BPM toggle | Many hip-hop and lo-fi beats are detected at double their "feel" BPM (e.g. a 70 BPM track detected as 140 BPM); a simple ÷2 / ×2 button solves this without re-analysis | Low (UI toggle, math only) | High: extremely common problem in hip-hop production where swing and half-time patterns confuse detectors | BPM display |
| Copy BPM / Copy key buttons | Producers immediately need these values in their clipboard to paste into FL Studio, Ableton, or their notes | Low | High: small UX detail but removes friction in the workflow handoff | Results display |

---

## Anti-Features

Features to deliberately NOT build. They add noise, complexity, or contradict the core value.

| Anti-Feature | Why Avoid | What to Do Instead | Cost of Building It |
|---|---|---|---|
| User accounts / login / history | Contradicts the "zero friction" core value — every extra click loses a user; SoundGrabber is a utility, not a platform | Stay stateless; browser can remember nothing, user doesn't need to | High: auth systems = auth surface, GDPR concerns, maintenance burden |
| Multiple format exports (MP3, FLAC, OGG) | WAV is the right choice for producers (lossless container, DAW-ready); adding formats creates format picker UI, more conversion jobs, more storage, more complexity | Export only WAV; if users need MP3, they can convert in DAW | Med: transcoding pipelines, format validation, storage per format |
| Playlist / batch download | Underground producers are looking at one beat at a time; playlist support means dealing with multi-file UX, job queuing, and server load spikes | Keep it single-URL; add a "try another" CTA after download | High: job queue, zip bundling, timeouts, abuse surface |
| Vocal remover / stem separation | Competitors like vocalremover.org offer this — but it's a different product; stem separation is compute-heavy and expensive; SoundGrabber isn't Moises.ai | Resist feature creep; reference stem tools in the results page if needed | Very high: GPU inference, long processing times, cost per track |
| SoundCloud / Instagram / TikTok support | Cobalt does multi-platform and it adds maintenance burden as each platform changes their API; YouTube is the specific community library for this audience | Lock to YouTube; "YouTube only" is a feature, not a limitation — it sets a clear expectation | High: each platform = separate extraction logic, separate breakage surface |
| Download history / library / saved tracks | Feels like a platform feature; underground producers don't want their activity tracked or stored | Ephemeral: download, done, gone — privacy by default | Med-High: database, storage, UI, session management |
| Subscription / paywall | Kills viral word-of-mouth in underground communities which run on mutual sharing; v1 must be free | No monetization in v1; consider non-intrusive options (Ko-fi link) only after trust is built | Low to build, high cost to community trust |
| AI-generated beat suggestions / recommendations | Scope creep into a recommendation engine; not the tool's job | Focus on the tool that already found the beat; trust the producer's taste | Very high: ML infrastructure, cold start problem, irrelevant to the use case |
| In-browser playback before download | Sounds convenient but adds audio player state management, buffering UX, and delays the download — the producer wants the file, not a preview | Show waveform thumbnail as static image instead | Med: streaming, buffering, player controls, mobile audio constraints |
| Dark mode toggle | Y2K aesthetic is part of the identity — a dark mode toggle breaks the visual coherence and signals "generic app"; one strong aesthetic is more memorable | Commit to a single, deliberate look | Low to build, high cost to visual identity |

---

## Feature Dependencies

```
URL input
  └── Download pipeline (yt-dlp)
        ├── WAV conversion (ffmpeg)
        │     └── WAV file download (direct HTTP)
        │     └── Audio analysis
        │           ├── BPM detection (librosa / essentia)
        │           │     ├── BPM display
        │           │     ├── Half-time / double-time toggle (depends on BPM display)
        │           │     └── Confidence indicator (depends on analysis pipeline)
        │           ├── Key detection (librosa / essentia)
        │           │     ├── Key display (standard notation)
        │           │     └── Camelot notation (depends on key display, simple mapping)
        │           └── Copy buttons (depends on results display existing)
        └── Progress feedback (wraps the whole pipeline)

Design system (Y2K aesthetic)
  └── Applied across all UI surfaces (no dependency on features)
```

---

## MVP Recommendation

**Prioritize (v1 — everything needed for the core value prop):**

1. URL input + yt-dlp download + WAV conversion (the download pipeline)
2. BPM + key detection using librosa/essentia server-side, displayed inline
3. Direct WAV download link with no auth
4. Progress indicator covering all stages (download, convert, analyze)
5. Y2K aesthetic applied to the UI
6. Copy-to-clipboard buttons on BPM and key values

**Add in v1.1 (low complexity, high value):**

7. Camelot wheel notation alongside standard key
8. Half-time / double-time BPM toggle

**Defer to v2 or never:**

- Waveform thumbnail (wavesurfer.js adds JS weight and complexity)
- Confidence indicator (requires surfacing internal model metadata; adds implementation complexity before core is validated)
- Any anti-feature listed above

---

## Competitor Feature Gap Analysis

| Tool | Download WAV | BPM | Key | No Account | No Ads | Combined UX | Y2K Aesthetic |
|---|---|---|---|---|---|---|---|
| y2mate | Yes (MP3/MP4 focus) | No | No | Yes | No (aggressive ads) | No | No |
| cobalt.tools | Yes (WAV supported) | No | No | Yes | Yes | No | No |
| TuneReveal | No (analysis only) | Yes | Yes | Yes | Yes | No | No |
| tunebat | No (DB lookup) | Yes | Yes | No (pro) | Partial | No | No |
| vocalremover.org | No | Yes (upload) | Yes (upload) | Yes | Partial | No | No |
| **SoundGrabber** | **Yes (WAV only)** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |

The gap SoundGrabber fills is real: no existing tool combines download-to-WAV with automatic BPM and key detection in a single zero-friction workflow. TuneReveal is the closest conceptually (YouTube URL in, analysis out) but delivers no downloadable file. Cobalt delivers the file but does no analysis.

---

## Sources

- [Cobalt.tools About](https://cobalt.tools/about/general) — MEDIUM confidence (official page)
- [TuneReveal GitHub](https://github.com/duardodev/tunereveal) — HIGH confidence (source code)
- [Tunebat Analyzer](https://tunebat.com/Analyzer) — HIGH confidence (official product)
- [Tunebat Review — Producer Hive](https://producerhive.com/buyer-guides/dj-gear/tunebat-review/) — MEDIUM confidence
- [vocalremover.org Key/BPM Finder](https://vocalremover.org/key-bpm-finder) — MEDIUM confidence (product page)
- [StemSplit: YouTube to WAV Guide](https://stemsplit.io/blog/youtube-to-wav) — MEDIUM confidence
- [BPM/Key Detection — StemSplit](https://stemsplit.io/blog/bpm-key-detection-feature) — MEDIUM confidence
- [BPM Finder Tunebat Alternative Benchmark](https://bpm-finder.net/posts/tunebat-bpm-alternative) — LOW confidence (single source, third-party benchmark)
- [Camelot Wheel Guide — DJ.Studio](https://dj.studio/blog/camelot-wheel) — HIGH confidence
- [Essentia.js Audio Analysis on Web — ISMIR](https://transactions.ismir.net/articles/10.5334/tismir.111) — HIGH confidence (peer-reviewed)
- [Y2Mate Review — Cedric Hsu](https://www.cedric-hsu.com/en/blog/y2mate-youtube-to-mp3-converter-review-2025) — MEDIUM confidence
- [YouTube Downloader Malware — Huntress](https://www.huntress.com/threat-library/malware/ytdownloader) — HIGH confidence (security research)
- [Mixed In Key Harmonic Mixing 2025](https://futuresoundacademy.com/blog/mixed-in-key-2025) — MEDIUM confidence
