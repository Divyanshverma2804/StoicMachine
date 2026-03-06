"""
scheduler.py — APScheduler background worker.
  • Every 60s: pick one PENDING job → render it (subprocess-safe via thread)
  • Every 60s: pick RENDERED jobs whose upload_time <= now → upload to YT
Runs inside the FastAPI process via lifespan.
"""
import logging, json
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler

from .models import Session, ReelJob, JobStatus
from .renderer import render_reel
from .uploader import upload_video

log = logging.getLogger("scheduler")


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)   # naive UTC for SQLite


# ── Render tick ───────────────────────────────────────────

def render_tick():
    db = Session()
    try:
        job = (db.query(ReelJob)
               .filter(ReelJob.status == JobStatus.pending)
               .order_by(ReelJob.created_at)
               .with_for_update(skip_locked=True)
               .first())
        if not job:
            return

        log.info(f"[scheduler] render_tick → job #{job.id} '{job.reel_name}'")
        job.status     = JobStatus.rendering
        job.updated_at = _utcnow()
        db.commit()
        job_id = job.id

    except Exception as e:
        log.error(f"[scheduler] render_tick DB error: {e}")
        db.rollback()
        return
    finally:
        db.close()

    # Render outside the DB session
    db2 = Session()
    try:
        job2 = db2.query(ReelJob).filter(ReelJob.id == job_id).first()
        output_path = render_reel(job2.reel_name, job2.script, job2.sections_json)
        job2.status      = JobStatus.rendered
        job2.output_path = output_path
        job2.error_msg   = None
        job2.updated_at  = _utcnow()
        db2.commit()
        log.info(f"[scheduler] job #{job_id} → rendered OK")

    except Exception as e:
        log.error(f"[scheduler] render FAILED job #{job_id}: {e}")
        db2.rollback()
        db2.refresh(job2)
        job2.retry_count += 1
        job2.status    = JobStatus.failed if job2.retry_count >= 3 else JobStatus.pending
        job2.error_msg = str(e)
        job2.updated_at = _utcnow()
        db2.commit()
    finally:
        db2.close()


# ── Upload tick ───────────────────────────────────────────

def upload_tick():
    db = Session()
    try:
        now  = _utcnow()
        jobs = (db.query(ReelJob)
                .filter(
                    ReelJob.status == JobStatus.rendered,
                    ReelJob.upload_time != None,
                    ReelJob.upload_time <= now,
                )
                .order_by(ReelJob.upload_time)
                .all())
    except Exception as e:
        log.error(f"[scheduler] upload_tick DB error: {e}")
        db.close()
        return

    for job in jobs:
        log.info(f"[scheduler] upload_tick → job #{job.id} '{job.reel_name}'")
        job.status     = JobStatus.uploading
        job.updated_at = _utcnow()
        db.commit()

        try:
            video_id = upload_video(
                video_path  = job.output_path,
                title       = job.reel_name.replace("_"," ").title(),
                description = job.script[:500],
            )
            job.yt_video_id = video_id
            job.status      = JobStatus.done
            job.error_msg   = None
        except Exception as e:
            log.error(f"[scheduler] upload FAILED job #{job.id}: {e}")
            job.retry_count += 1
            job.status    = JobStatus.failed if job.retry_count >= 3 else JobStatus.rendered
            job.error_msg = str(e)
        finally:
            job.updated_at = _utcnow()
            db.commit()

    db.close()


# ── Scheduler lifecycle ───────────────────────────────────

_scheduler = BackgroundScheduler(timezone="UTC")

def start_scheduler():
    _scheduler.add_job(render_tick, "interval", seconds=60,
                       id="render_tick", replace_existing=True)
    _scheduler.add_job(upload_tick, "interval", seconds=60,
                       id="upload_tick", replace_existing=True)
    _scheduler.start()
    log.info("[scheduler] Started — render + upload ticks every 60s")


def stop_scheduler():
    _scheduler.shutdown(wait=False)
    log.info("[scheduler] Stopped")
