"""
main.py — FastAPI web portal for ReelForge
"""
import re, json, uuid, logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .models import init_db, Session, ReelJob, JobStatus
from .scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

# ── Lifespan: init DB + start scheduler ──────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="ReelForge", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ── Content-script parser (same logic as before) ─────────

def parse_content_md(raw: str) -> list[dict]:
    reels  = []
    blocks = re.split(r"\n---+\n?", raw)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        name_match = re.search(r"#\s*ReelName\s*:\s*(.+)", block, re.IGNORECASE)
        if not name_match:
            continue
        reel_name = name_match.group(1).strip()

        hook_m     = re.search(r"##\s*Hook\s*:\s*\n(.+?)(?=##|\Z)",     block, re.IGNORECASE|re.DOTALL)
        conflict_m = re.search(r"##\s*Conflict\s*:\s*\n(.+?)(?=##|\Z)", block, re.IGNORECASE|re.DOTALL)
        shift_m    = re.search(r"##\s*Shift\s*:\s*\n(.+?)(?=##|\Z)",    block, re.IGNORECASE|re.DOTALL)
        punch_m    = re.search(r"##\s*Punch\s*:\s*\n(.+?)(?=##|\Z)",    block, re.IGNORECASE|re.DOTALL)
        engage_m   = re.search(r"##\s*Engage\s*:\s*\n(.+?)(?=##|\Z)",   block, re.IGNORECASE|re.DOTALL)

        if hook_m:
            sections = {
                "hook":     hook_m.group(1).strip()     if hook_m     else "",
                "conflict": conflict_m.group(1).strip() if conflict_m else "",
                "shift":    shift_m.group(1).strip()    if shift_m    else "",
                "punch":    punch_m.group(1).strip()    if punch_m    else "",
                "engage":   engage_m.group(1).strip()   if engage_m   else "",
            }
            script = "\n".join(v for v in sections.values() if v)
        else:
            content_match = re.search(r"##\s*Content\s*:\s*\n([\s\S]+)", block, re.IGNORECASE)
            if not content_match:
                continue
            script   = content_match.group(1).strip()
            sections = None

        reels.append({"name": reel_name, "script": script, "sections": sections})
    return reels


# ── Routes ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db   = Session()
    jobs = db.query(ReelJob).order_by(ReelJob.created_at.desc()).limit(100).all()
    db.close()
    return templates.TemplateResponse("index.html", {"request": request, "jobs": jobs})


@app.post("/submit")
async def submit_content(
    request: Request,
    content_md: str  = Form(...),
    upload_time: str = Form(""),       # ISO datetime string, optional global default
    per_reel_times: str = Form("{}"),  # JSON: {"reel_name": "ISO datetime", ...}
):
    reels = parse_content_md(content_md)
    if not reels:
        raise HTTPException(400, "No reels found. Check your content.md format.")

    # Parse optional time overrides
    try:
        per_times: dict = json.loads(per_reel_times) if per_reel_times.strip() else {}
    except json.JSONDecodeError:
        per_times = {}

    global_time: Optional[datetime] = None
    if upload_time.strip():
        try:
            global_time = datetime.fromisoformat(upload_time.strip())
        except ValueError:
            pass

    batch_id = str(uuid.uuid4())[:8]
    db = Session()
    created = []

    for reel in reels:
        # Per-reel time > global time > None
        reel_time = per_times.get(reel["name"])
        if reel_time:
            try:
                upload_dt = datetime.fromisoformat(reel_time)
            except ValueError:
                upload_dt = global_time
        else:
            upload_dt = global_time

        job = ReelJob(
            batch_id      = batch_id,
            reel_name     = reel["name"],
            script        = reel["script"],
            sections_json = json.dumps(reel["sections"]) if reel["sections"] else None,
            upload_time   = upload_dt,
            status        = JobStatus.pending,
        )
        db.add(job)
        created.append(reel["name"])

    db.commit()
    db.close()

    return RedirectResponse(url=f"/?batch={batch_id}", status_code=303)


@app.get("/jobs", response_class=JSONResponse)
async def list_jobs(batch_id: str = None):
    db = Session()
    q  = db.query(ReelJob)
    if batch_id:
        q = q.filter(ReelJob.batch_id == batch_id)
    jobs = q.order_by(ReelJob.created_at.desc()).all()
    db.close()
    return [j.as_dict() for j in jobs]


@app.post("/jobs/{job_id}/retry")
async def retry_job(job_id: int):
    db  = Session()
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(404, "Job not found")
    job.status      = JobStatus.pending
    job.retry_count = 0
    job.error_msg   = None
    job.updated_at  = datetime.utcnow()
    db.commit()
    db.close()
    return {"ok": True, "job_id": job_id}


@app.post("/jobs/{job_id}/set_upload_time")
async def set_upload_time(job_id: int, upload_time: str = Form(...)):
    db  = Session()
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(404, "Job not found")
    try:
        job.upload_time = datetime.fromisoformat(upload_time)
    except ValueError:
        raise HTTPException(400, "Invalid datetime format (use ISO 8601)")
    job.updated_at = datetime.utcnow()
    db.commit()
    db.close()
    return {"ok": True}


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: int):
    db  = Session()
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(404, "Job not found")
    db.delete(job)
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}
