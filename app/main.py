"""
main.py — FastAPI web portal for ReelForge
"""
import re, json, uuid, logging, os, secrets, threading
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ── Rate limiting ─────────────────────────────────────────
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .models import init_db, Session, ReelJob, ReelDraft, JobStatus
from .scheduler import start_scheduler, stop_scheduler
from .uploader import upload_video, build_yt_title_and_description, extract_tags_from_script, fetch_video_stats

log = logging.getLogger("main")

# ── HTTP Basic Auth ───────────────────────────────────────
_security    = HTTPBasic()
_PORTAL_USER = os.environ.get("PORTAL_USER",     "admin")
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

# ── Scan detector ─────────────────────────────────────────
_SCAN_PATHS = {
    "/.env", "/.env.local", "/.env.production", "/.env.development",
    "/.env.backup", "/.env.bak", "/.env.old", "/.env.save",
    "/.git/config", "/.git/logs/head",
    "/wp-config.php", "/wp-config.php.bak",
    "/credentials.json", "/secrets.json", "/secrets.yaml", "/secrets.yml",
    "/.aws/credentials", "/root/.aws/credentials",
    "/docker-compose.yml", "/docker-compose.yaml",
    "/actuator/env", "/actuator/configprops",
    "/proc/self/environ",
    "/solr/admin/info/system",
    "/v2/_catalog",
    "/anthropic/v1/models",
    "/v1/messages",
}

# ── Lifespan ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


# ── App + rate limiter ────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app     = FastAPI(title="ReelForge", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ── Scan trap middleware ──────────────────────────────────
@app.middleware("http")
async def scan_trap(request: Request, call_next):
    path = request.url.path.lower()
    if path in _SCAN_PATHS:
        client_ip = request.client.host if request.client else "unknown"
        log.warning(f"[scan_trap] Blocked scan attempt: {client_ip} → {path}")
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    if "../" in path or "%2f" in path.lower() or "%252f" in path.lower():
        client_ip = request.client.host if request.client else "unknown"
        log.warning(f"[scan_trap] Blocked path traversal: {client_ip} → {path}")
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return await call_next(request)


# ── Content-script parser ─────────────────────────────────

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

        cat_match = re.search(r"#\s*Category\s*:\s*(.+)", block, re.IGNORECASE)
        category  = cat_match.group(1).strip() if cat_match else "uncategorized"

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

        reels.append({"name": reel_name, "script": script, "sections": sections, "category": category})
    return reels


# ── Routes ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
@limiter.limit("60/minute")
async def index(request: Request, _user: str = Depends(require_auth)):
    db     = Session()
    jobs   = db.query(ReelJob).order_by(ReelJob.created_at.desc()).limit(100).all()
    counts = {s.value: 0 for s in JobStatus}
    for j in jobs:
        counts[j.status] = counts.get(j.status, 0) + 1
    db.close()
    return templates.TemplateResponse("index.html", {"request": request, "jobs": jobs, "counts": counts})


@app.post("/submit")
@limiter.limit("20/minute")
async def submit_content(
    request: Request,
    content_md: str  = Form(...),
    upload_time: str = Form(""),
    per_reel_times: str = Form("{}"),
    privacy: str     = Form(""),
    _user: str = Depends(require_auth),
):
    reels = parse_content_md(content_md)
    if not reels:
        raise HTTPException(400, "No reels found. Check your content.md format.")

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
            category      = reel.get("category", "uncategorized"),
            privacy       = privacy if privacy in {"public", "private", "unlisted"} else None,
        )
        db.add(job)
        created.append(reel["name"])

    db.commit()
    db.close()

    try:
        from datetime import timezone as _tz
        _now_ist = datetime.now(_tz(timedelta(hours=5, minutes=30)))
        _title   = f"Batch · {len(created)} reel{'s' if len(created) != 1 else ''} · {_now_ist.strftime('%d %b %Y %H:%M IST')}"
        _db2 = Session()
        _db2.add(ReelDraft(
            title   = _title,
            content = content_md,
            source  = "queued",
            tag     = None,
        ))
        _db2.commit()
        _db2.close()
    except Exception as _diary_exc:
        logging.getLogger("diary").warning(f"Auto-save queued batch to diary failed: {_diary_exc}")

    return RedirectResponse(url=f"/?batch={batch_id}", status_code=303)


@app.get("/jobs", response_class=JSONResponse)
@limiter.limit("120/minute")
async def list_jobs(request: Request, batch_id: str = None, _user: str = Depends(require_auth)):
    db = Session()
    q  = db.query(ReelJob)
    if batch_id:
        q = q.filter(ReelJob.batch_id == batch_id)
    jobs = q.order_by(ReelJob.created_at.desc()).all()
    db.close()
    return [j.as_dict() for j in jobs]


# ── BULK SCHEDULE ─────────────────────────────────────────

@app.post("/jobs/bulk_schedule", response_class=JSONResponse)
@limiter.limit("30/minute")
async def bulk_schedule(
    request:  Request,
    job_ids:  str = Form(...),   # comma-separated list of job IDs
    span_hrs: float = Form(...), # total spread in hours e.g. 8.0
    privacy:  str = Form(""),    # optional privacy override for all selected
    _user: str = Depends(require_auth),
):
    """
    Distribute selected rendered jobs evenly across a time span.

    Timing logic:
      - First video starts NOW + 5 minutes (safety margin so the user
        can still be interacting with the UI without risking an immediate upload)
      - Remaining videos spread evenly across [first_time, first_time + span_hrs]
      - Gap = span_hrs / (n - 1) when n > 1, or span_hrs when n == 1
      - All times are UTC naive datetimes stored to the DB

    Only jobs with status == 'rendered' are accepted.
    Job IDs that don't exist or aren't rendered are silently skipped.
    Returns the list of scheduled jobs with their assigned upload times.
    """
    # Parse job ID list
    try:
        ids = [int(x.strip()) for x in job_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "job_ids must be comma-separated integers")

    if not ids:
        raise HTTPException(400, "No job IDs provided")

    if span_hrs <= 0 or span_hrs > 168:   # max 1 week span
        raise HTTPException(400, "span_hrs must be between 0 and 168")

    db = Session()
    try:
        # Fetch only rendered jobs from the provided IDs, preserve user's selection order
        jobs = []
        for jid in ids:
            job = db.query(ReelJob).filter(
                ReelJob.id == jid,
                ReelJob.status == JobStatus.rendered,
            ).first()
            if job:
                jobs.append(job)

        if not jobs:
            raise HTTPException(400, "No rendered jobs found in the provided IDs")

        n = len(jobs)
        now_utc    = datetime.utcnow()
        first_time = now_utc + timedelta(minutes=5)   # 5-min safety margin

        # Gap between uploads
        # If only one reel: upload at first_time (span is irrelevant)
        # If multiple: spread evenly so last one is at first_time + span_hrs
        gap_seconds = (span_hrs * 3600) / (n - 1) if n > 1 else 0

        scheduled = []
        for i, job in enumerate(jobs):
            upload_at = first_time + timedelta(seconds=gap_seconds * i)
            job.upload_time = upload_at
            job.updated_at  = now_utc
            if privacy in {"public", "private", "unlisted"}:
                job.privacy = privacy

            scheduled.append({
                "id":          job.id,
                "reel_name":   job.reel_name,
                "upload_time": upload_at.isoformat(),
                "slot":        i + 1,
            })

        db.commit()
        log.info(
            f"[bulk_schedule] Scheduled {n} reels across {span_hrs}h "
            f"starting {first_time.isoformat()} UTC"
        )
        return {"ok": True, "scheduled": scheduled, "count": n}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"[bulk_schedule] Error: {e}")
        raise HTTPException(500, f"Bulk schedule failed: {e}")
    finally:
        db.close()


@app.get("/calendar/events", response_class=JSONResponse)
@limiter.limit("60/minute")
async def calendar_events(request: Request, _user: str = Depends(require_auth)):
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
@limiter.limit("30/minute")
async def reschedule_job(
    request: Request,
    job_id: int,
    new_time: str = Form(...),
    _user: str = Depends(require_auth),
):
    db  = Session()
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(404, "Job not found")
    try:
        job.upload_time = datetime.fromisoformat(new_time.replace("Z", ""))
    except ValueError:
        raise HTTPException(400, "Invalid datetime format")
    job.updated_at = datetime.utcnow()
    db.commit()
    db.close()
    return {"ok": True}


@app.post("/jobs/{job_id}/retry")
@limiter.limit("20/minute")
async def retry_job(request: Request, job_id: int, _user: str = Depends(require_auth)):
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
    from datetime import timezone
    def _utcnow():
        return datetime.now(timezone.utc).replace(tzinfo=None)

    db  = Session()
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job or not job.output_path:
        db.close()
        logging.getLogger("upload_now").error(f"Job #{job_id} not found or no output_path")
        return

    _log = logging.getLogger("upload_now")
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
        privacy  = job.privacy
        video_id = upload_video(
            video_path       = job.output_path,
            title            = title,
            description      = description,
            tags             = tags,
            privacy_override = privacy,
        )
        job.yt_video_id = video_id
        job.status      = JobStatus.done
        job.error_msg   = None
        _log.info(f"[upload_now] job #{job_id} uploaded → {video_id}")
        db.commit()
        _auto_save_diary(job_id)
    except Exception as e:
        _log.error(f"[upload_now] FAILED job #{job_id}: {e}")
        job.retry_count += 1
        job.status    = JobStatus.failed if job.retry_count >= 3 else JobStatus.rendered
        job.error_msg = str(e)
    finally:
        job.updated_at = _utcnow()
        db.commit()
        db.close()


@app.post("/jobs/{job_id}/upload_now")
@limiter.limit("10/minute")
async def upload_now(
    request: Request,
    job_id: int,
    _user: str = Depends(require_auth),
):
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
        raise HTTPException(400, "No output file found for this job yet")
    db.close()

    t = threading.Thread(target=_do_upload_now, args=(job_id,), daemon=True)
    t.start()
    return {"ok": True, "job_id": job_id, "message": "Upload started — check status in a few seconds"}


@app.post("/jobs/{job_id}/set_upload_time")
@limiter.limit("30/minute")
async def set_upload_time(request: Request, job_id: int, upload_time: str = Form(...), _user: str = Depends(require_auth)):
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


@app.post("/jobs/{job_id}/set_privacy")
@limiter.limit("30/minute")
async def set_privacy(request: Request, job_id: int, privacy: str = Form(...), _user: str = Depends(require_auth)):
    _VALID = {"public", "private", "unlisted"}
    if privacy not in _VALID:
        raise HTTPException(400, f"privacy must be one of {_VALID}")
    db  = Session()
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(404, "Job not found")
    job.privacy    = privacy
    job.updated_at = datetime.utcnow()
    db.commit()
    db.close()
    return {"ok": True, "privacy": privacy}


@app.delete("/jobs/{job_id}")
@limiter.limit("20/minute")
async def delete_job(request: Request, job_id: int, _user: str = Depends(require_auth)):
    db  = Session()
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(404, "Job not found")
    db.delete(job)
    db.commit()
    db.close()
    return {"ok": True}


@app.post("/jobs/{job_id}/refresh_stats")
@limiter.limit("20/minute")
async def refresh_stats(request: Request, job_id: int, _user: str = Depends(require_auth)):
    db  = Session()
    job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(404, "Job not found")
    if not job.yt_video_id:
        db.close()
        raise HTTPException(400, "No YouTube video ID for this job yet")
    yt_id = job.yt_video_id
    db.close()

    stats = fetch_video_stats(yt_id)

    db2  = Session()
    job2 = db2.query(ReelJob).filter(ReelJob.id == job_id).first()
    if job2:
        job2.views      = stats["viewCount"]
        job2.updated_at = datetime.utcnow()
        db2.commit()
    db2.close()

    return {
        "ok":           True,
        "job_id":       job_id,
        "yt_video_id":  yt_id,
        "viewCount":    stats["viewCount"],
        "likeCount":    stats["likeCount"],
        "commentCount": stats["commentCount"],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/analytics/categories", response_class=JSONResponse)
@limiter.limit("30/minute")
async def analytics_categories(request: Request, _user: str = Depends(require_auth)):
    db   = Session()
    jobs = db.query(ReelJob).all()
    db.close()

    summary: dict[str, dict] = {}
    for job in jobs:
        cat = job.category or "uncategorized"
        if cat not in summary:
            summary[cat] = {
                "category":    cat,
                "total":       0,
                "done":        0,
                "failed":      0,
                "avg_views":   0,
                "_view_sum":   0,
                "_done_views": 0,
            }
        summary[cat]["total"] += 1
        if job.status == JobStatus.done:
            summary[cat]["done"]        += 1
            summary[cat]["_view_sum"]   += job.views or 0
            summary[cat]["_done_views"] += 1
        elif job.status == JobStatus.failed:
            summary[cat]["failed"] += 1

    result = []
    for rec in summary.values():
        done_with_views = rec.pop("_done_views")
        view_sum        = rec.pop("_view_sum")
        rec["avg_views"] = round(view_sum / done_with_views, 1) if done_with_views > 0 else 0
        result.append(rec)

    return sorted(result, key=lambda x: x["total"], reverse=True)


# ═══════════════════════════════════════════════════════════
# DIARY API
# ═══════════════════════════════════════════════════════════

def _auto_save_diary(job_id: int):
    db  = Session()
    try:
        job = db.query(ReelJob).filter(ReelJob.id == job_id).first()
        if not job:
            return
        exists = db.query(ReelDraft).filter(ReelDraft.reel_job_id == job_id).first()
        if exists:
            return
        entry = ReelDraft(
            title       = job.reel_name,
            content     = job.script or "",
            source      = "posted",
            reel_job_id = job_id,
            tag         = job.category or "uncategorized",
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        logging.getLogger("diary").warning(f"Auto-save diary failed for job #{job_id}: {exc}")
    finally:
        db.close()


@app.get("/diary", response_class=JSONResponse)
@limiter.limit("60/minute")
async def list_diary(request: Request, _user: str = Depends(require_auth)):
    db      = Session()
    entries = db.query(ReelDraft).order_by(ReelDraft.updated_at.desc()).all()
    db.close()
    return [e.as_dict() for e in entries]


@app.post("/diary", response_class=JSONResponse)
@limiter.limit("20/minute")
async def save_draft(
    request: Request,
    title:   str = Form(...),
    content: str = Form(...),
    tag:     str = Form(""),
    _user: str   = Depends(require_auth),
):
    db    = Session()
    entry = ReelDraft(
        title   = title.strip() or "Untitled",
        content = content,
        source  = "draft",
        tag     = tag.strip() or None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    result = entry.as_dict()
    db.close()
    return result


@app.patch("/diary/{entry_id}", response_class=JSONResponse)
@limiter.limit("20/minute")
async def update_draft(
    request: Request,
    entry_id: int,
    title:    str = Form(""),
    content:  str = Form(""),
    tag:      str = Form(""),
    _user: str    = Depends(require_auth),
):
    db    = Session()
    entry = db.query(ReelDraft).filter(ReelDraft.id == entry_id).first()
    if not entry:
        db.close()
        raise HTTPException(404, "Diary entry not found")
    if title.strip():
        entry.title   = title.strip()
    if content:
        entry.content = content
    if tag.strip():
        entry.tag = tag.strip()
    entry.updated_at = datetime.utcnow()
    db.commit()
    result = entry.as_dict()
    db.close()
    return result


@app.delete("/diary/{entry_id}", response_class=JSONResponse)
@limiter.limit("20/minute")
async def delete_diary_entry(request: Request, entry_id: int, _user: str = Depends(require_auth)):
    db    = Session()
    entry = db.query(ReelDraft).filter(ReelDraft.id == entry_id).first()
    if not entry:
        db.close()
        raise HTTPException(404, "Diary entry not found")
    db.delete(entry)
    db.commit()
    db.close()
    return {"ok": True}