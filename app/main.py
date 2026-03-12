"""
main.py — FastAPI web portal for ReelForge
"""
import re, json, uuid, logging, os, secrets, threading
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .models import init_db, Session, ReelJob, JobStatus
from .scheduler import start_scheduler, stop_scheduler
from .uploader import upload_video, build_yt_title_and_description, extract_tags_from_script

# ── HTTP Basic Auth ───────────────────────────────────────
_security = HTTPBasic()
_PORTAL_USER = os.environ.get("PORTAL_USER", "admin")
_PORTAL_PASS = os.environ.get("PORTAL_PASSWORD", "reelforge")

def require_auth(creds: HTTPBasicCredentials = Depends(_security)):
    ok_user = secrets.compare_digest(creds.username.encode(), _PORTAL_USER.encode())
    ok_pass = secrets.compare_digest(creds.password.encode(), _PORTAL_PASS.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic realm='ReelForge'"},
        )
    return creds.username

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
async def index(request: Request, _user: str = Depends(require_auth)):
    db     = Session()
    jobs   = db.query(ReelJob).order_by(ReelJob.created_at.desc()).limit(100).all()
    counts = {s.value: 0 for s in JobStatus}
    for j in jobs:
        counts[j.status] = counts.get(j.status, 0) + 1
    db.close()
    return templates.TemplateResponse("index.html", {"request": request, "jobs": jobs, "counts": counts})


@app.post("/submit")
async def submit_content(
    request: Request,
    content_md: str  = Form(...),
    upload_time: str = Form(""),       # ISO datetime string, optional global default
    per_reel_times: str = Form("{}"),  # JSON: {"reel_name": "ISO datetime", ...}
    _user: str = Depends(require_auth),
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
async def list_jobs(batch_id: str = None, _user: str = Depends(require_auth)):
    db = Session()
    q  = db.query(ReelJob)
    if batch_id:
        q = q.filter(ReelJob.batch_id == batch_id)
    jobs = q.order_by(ReelJob.created_at.desc()).all()
    db.close()
    return [j.as_dict() for j in jobs]


@app.get("/calendar/events", response_class=JSONResponse)
async def calendar_events(_user: str = Depends(require_auth)):
    """
    Returns all jobs that have an upload_time, formatted for FullCalendar.
    Also returns jobs without upload_time as 'unscheduled' for the sidebar.
    """
    db   = Session()
    jobs = db.query(ReelJob).order_by(ReelJob.created_at.desc()).limit(200).all()
    db.close()

    STATUS_COLORS = {
        "pending":   "#d29922",
        "rendering": "#bc8cff",
        "rendered":  "#3fb950",
        "uploading": "#58a6ff",
        "done":      "#39d353",
        "failed":    "#f85149",
    }

    events = []
    for j in jobs:
        if j.upload_time:
            events.append({
                "id":              str(j.id),
                "title":           j.reel_name.replace("_", " "),
                "start":           j.upload_time.isoformat() + "Z",
                "backgroundColor": STATUS_COLORS.get(j.status, "#58a6ff"),
                "borderColor":     STATUS_COLORS.get(j.status, "#58a6ff"),
                "textColor":       "#0d1117",
                "extendedProps": {
                    "status":      j.status,
                    "batch_id":    j.batch_id,
                    "yt_video_id": j.yt_video_id,
                    "job_id":      j.id,
                },
            })
    return events


@app.post("/jobs/{job_id}/reschedule", response_class=JSONResponse)
async def reschedule_job(
    job_id: int,
    new_time: str = Form(...),
    _user: str = Depends(require_auth),
):
    """Called by FullCalendar drag-and-drop with the new ISO datetime."""
    db  = Session()
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(404, "Job not found")
    try:
        # new_time arrives as ISO 8601 with Z suffix from FullCalendar
        job.upload_time = datetime.fromisoformat(new_time.replace("Z", ""))
    except ValueError:
        raise HTTPException(400, "Invalid datetime format")
    job.updated_at = datetime.utcnow()
    db.commit()
    db.close()
    return {"ok": True}


@app.post("/jobs/{job_id}/retry")
async def retry_job(job_id: int, _user: str = Depends(require_auth)):
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


def _do_upload_now(job_id: int):
    """
    Worker function run in a background thread by upload_now endpoint.
    Builds smart title/description/tags from the reel script, then uploads.
    """
    from datetime import timezone
    def _utcnow():
        return datetime.now(timezone.utc).replace(tzinfo=None)

    db  = Session()
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job or not job.output_path:
        db.close()
        logging.getLogger("upload_now").error(f"Job #{job_id} not found or no output_path")
        return

    log = logging.getLogger("upload_now")
    job.status     = JobStatus.uploading
    job.updated_at = _utcnow()
    db.commit()

    try:
        title, description = build_yt_title_and_description(
            reel_name         = job.reel_name,
            script            = job.script,
            extra_description = job.script[:500],
        )
        tags     = extract_tags_from_script(job.script)
        video_id = upload_video(
            video_path  = job.output_path,
            title       = title,
            description = description,
            tags        = tags,
        )
        job.yt_video_id = video_id
        job.status      = JobStatus.done
        job.error_msg   = None
        log.info(f"[upload_now] job #{job_id} uploaded → {video_id}")
    except Exception as e:
        log.error(f"[upload_now] FAILED job #{job_id}: {e}")
        job.retry_count += 1
        job.status    = JobStatus.failed if job.retry_count >= 3 else JobStatus.rendered
        job.error_msg = str(e)
    finally:
        job.updated_at = _utcnow()
        db.commit()
        db.close()


@app.post("/jobs/{job_id}/upload_now")
async def upload_now(
    job_id: int,
    _user: str = Depends(require_auth),
):
    """
    Immediately start uploading a rendered reel to YouTube without waiting
    for the scheduler.  The upload runs in a background thread so the
    response returns instantly and the UI can poll for status.
    """
    db  = Session()
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(404, "Job not found")
    if job.status not in (JobStatus.rendered, JobStatus.failed):
        db.close()
        raise HTTPException(400, f"Job is {job.status!r} — can only upload from 'rendered' or 'failed' state")
    if not job.output_path:
        db.close()
        raise HTTPException(400, "No output file found for this job yet — please wait for rendering to complete")
    db.close()

    # Kick off upload in a daemon thread so FastAPI response isn't blocked
    t = threading.Thread(target=_do_upload_now, args=(job_id,), daemon=True)
    t.start()
    return {"ok": True, "job_id": job_id, "message": "Upload started — check status in a few seconds"}


@app.post("/jobs/{job_id}/set_upload_time")
async def set_upload_time(job_id: int, upload_time: str = Form(...), _user: str = Depends(require_auth)):
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
async def delete_job(job_id: int, _user: str = Depends(require_auth)):
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
