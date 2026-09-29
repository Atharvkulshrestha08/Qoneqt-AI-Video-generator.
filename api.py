import asyncio
import glob
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline import JobRunner, JobState, JOBS_DIR
from llm import llm_client, TrendAnglesResult, clean_and_parse_json
from moderation import load_prompt

logger = logging.getLogger("qoneqtreel.api")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

app = FastAPI(title="QoneqtReel Engine API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class CreateJobRequest(BaseModel):
    topic: str
    style: str = "energetic explainer"
    trend: str = ""


class BatchJobRequest(BaseModel):
    topics: List[str]


class TrendExpandRequest(BaseModel):
    trend: str


def run_pipeline_task(job_id: str):
    state_file = JOBS_DIR / f"{job_id}.json"
    if not state_file.exists():
        return
    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    job_state = JobState(**data)
    runner = JobRunner(job_state)
    runner.execute()


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "QoneqtReel Engine",
        "llm_provider": os.getenv("LLM_PROVIDER", "gemini"),
        "has_gemini_key": bool(os.getenv("GEMINI_API_KEY")),
        "has_groq_key": bool(os.getenv("GROQ_API_KEY")),
        "has_pexels_key": bool(os.getenv("PEXELS_API_KEY")),
    }


@app.post("/api/jobs")
def create_job(req: CreateJobRequest, bg_tasks: BackgroundTasks):
    clean_topic = req.topic.strip()
    if not clean_topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty")

    job_id = f"job_{int(os.times().elapsed * 1000)}_{uuid.uuid4().hex[:6]}"
    state = JobState(job_id=job_id, topic=clean_topic, style=req.style, trend=req.trend)
    # Save initial queued state
    with open(JOBS_DIR / f"{job_id}.json", "w", encoding="utf-8") as f:
        f.write(state.model_dump_json(indent=2))

    bg_tasks.add_task(run_pipeline_task, job_id)
    return {"job_id": job_id, "status": "queued"}


@app.post("/api/batch")
def create_batch(req: BatchJobRequest, bg_tasks: BackgroundTasks):
    topics = [t.strip() for t in req.topics if t.strip()]
    if not topics:
        raise HTTPException(status_code=400, detail="No valid topics provided")

    job_ids = []
    for topic in topics:
        job_id = f"job_{int(os.times().elapsed * 1000)}_{uuid.uuid4().hex[:6]}"
        state = JobState(job_id=job_id, topic=topic)
        with open(JOBS_DIR / f"{job_id}.json", "w", encoding="utf-8") as f:
            f.write(state.model_dump_json(indent=2))
        job_ids.append(job_id)

    # Process jobs sequentially in background
    def run_all():
        for j_id in job_ids:
            run_pipeline_task(j_id)

    bg_tasks.add_task(run_all)
    return {"count": len(job_ids), "job_ids": job_ids}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    state_file = JOBS_DIR / f"{job_id}.json"
    if not state_file.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    with open(state_file, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/jobs")
def list_jobs():
    files = sorted(glob.glob(str(JOBS_DIR / "*.json")), key=os.path.getmtime, reverse=True)
    results = []
    for f in files[:30]:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                results.append({
                    "job_id": data.get("job_id"),
                    "topic": data.get("topic"),
                    "status": data.get("status"),
                    "stage": data.get("stage"),
                    "created_at": data.get("created_at"),
                    "finished_at": data.get("finished_at"),
                    "overall_score": data.get("scores", {}).get("overall"),
                })
        except Exception:
            continue
    return results


@app.get("/api/jobs/{job_id}/video")
def get_video(job_id: str):
    video_path = JOBS_DIR / job_id / "final_reel.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found or generation not finished")
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"qoneqt_{job_id}.mp4",
    )


@app.post("/api/trend/expand")
def expand_trend(req: TrendExpandRequest):
    trend_kw = req.trend.strip()
    if not trend_kw:
        raise HTTPException(status_code=400, detail="Trend cannot be empty")

    if llm_client.gemini_key or llm_client.groq_key:
        try:
            template = load_prompt("trend_expander.txt")
            prompt = template.format(trend=trend_kw)
            return llm_client.query_json(prompt)
        except Exception as e:
            logger.warning(f"Trend expander failed: {e}")

    # Fallback angles
    return {
        "angles": [
            {"topic": f"The hidden science of {trend_kw}", "why_it_works": "Curiosity and educational appeal"},
            {"topic": f"How {trend_kw} is changing everyday life in India", "why_it_works": "High cultural resonance"},
            {"topic": f"3 things everyone gets wrong about {trend_kw}", "why_it_works": "Strong scroll-stopping tension"},
        ]
    }


@app.get("/", response_class=HTMLResponse)
def index():
    html_file = STATIC_DIR / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<h1>QoneqtReel Engine API</h1><p>UI loading...</p>"
