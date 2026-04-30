"""FastAPI app — POST /jobs, GET /jobs/{id}, GET /files/{id}. Plans 02/03 implement the bodies."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class JobRequest(BaseModel):
    youtube_url: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Plan 03 (Wave 3) starts the WAV sweeper thread here.
    yield


app = FastAPI(title="SoundGrabber API", version="0.2.0", lifespan=lifespan)


@app.post("/jobs", status_code=202)
def submit_job(request: JobRequest) -> dict:
    """Plan 02 (Wave 2) — validate YouTube URL and enqueue Celery task."""
    raise HTTPException(status_code=501, detail="Not implemented — Plan 02")


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    """Plan 03 (Wave 3) — read AsyncResult and return job status."""
    raise HTTPException(status_code=501, detail="Not implemented — Plan 03")


@app.get("/files/{job_id}")
def download_file(job_id: str):
    """Plan 03 (Wave 3) — stream WAV via FileResponse."""
    raise HTTPException(status_code=501, detail="Not implemented — Plan 03")
