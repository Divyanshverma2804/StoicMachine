"""
scheduler.py — APScheduler background worker.
  • Every 60s:  pick one PENDING job → render it (subprocess-safe via thread)
  • Every 60s:  pick RENDERED jobs whose upload_time <= now → upload to YT
  • Every 5m:   watchdog — reset jobs stuck in 'rendering' for > 20 minutes
  • Every 6h:   refresh YT view counts for all done jobs
  • Every 24h:  delete output video files for old uploaded jobs
                (keeps the N most-recent done jobs on disk, deletes the rest)
Runs inside the FastAPI process via lifespan.
"""
import logging, json, os
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

from .models import Session, ReelJob, ReelDraft, JobStatus
from .renderer import render_reel
from .uploader import upload_video, build_yt_title_and_description, extract_tags_from_script, fetch_video_stats

log = logging.getLogger("scheduler")

# A job stuck in 'rendering' for longer than this is considered dead
RENDER_TIMEOUT_MINUTES = int(os.environ.get("RENDER_TIMEOUT_MINUTES", "20"))

MAX_RETRY = int(os.environ.get("RENDER_MAX_RETRY", "3"))


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
        output_path = render_reel(job2.reel_name, job2.script, job2.sections_json, voice=job2.voice)
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
        job2.status     = JobStatus.failed if job2.retry_count >= MAX_RETRY else JobStatus.pending
        job2.error_msg  = str(e)
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
            title, description = build_yt_title_and_description(
                reel_name         = job.reel_name,
                script            = job.script,
                extra_description = job.script[:500],
            )
            tags = extract_tags_from_script(job.script)
            video_id = upload_video(
                video_path       = job.output_path,
                title            = title,
                description      = description,
                tags             = tags,
                privacy_override = job.privacy,   # None → falls back to YT_PRIVACY env
            )
            job.yt_video_id = video_id
            job.status      = JobStatus.done
            job.error_msg   = None
            job.updated_at  = _utcnow()
            db.commit()   # commit before diary so job.script is readable
            # Auto-save script to diary (idempotent)
            try:
                if not db.query(ReelDraft).filter(ReelDraft.reel_job_id == job.id).first():
                    db.add(ReelDraft(
                        title       = job.reel_name,
                        content     = job.script or "",
                        source      = "posted",
                        reel_job_id = job.id,
                        tag         = job.category or "uncategorized",
                    ))
                    db.commit()
            except Exception as diary_exc:
                log.warning(f"[scheduler] diary auto-save failed for job #{job.id}: {diary_exc}")
        except Exception as e:
            log.error(f"[scheduler] upload FAILED job #{job.id}: {e}")
            job.retry_count += 1
            job.status    = JobStatus.failed if job.retry_count >= MAX_RETRY else JobStatus.rendered
            job.error_msg = str(e)
        finally:
            job.updated_at = _utcnow()
            db.commit()

    db.close()


# ── Watchdog tick ─────────────────────────────────────────

def watchdog_tick():
    """
    Detects jobs silently stuck in 'rendering' status.

    A job is considered stuck when:
      - status == rendering
      - updated_at has not changed for > RENDER_TIMEOUT_MINUTES

    This happens when the renderer process is OOM-killed, the Docker
    container restarts mid-render, or Chatterbox crashes without raising
    a catchable exception. The job status never transitions and it freezes
    in 'rendering' forever until this watchdog resets it.

    Recovery logic:
      - retry_count < MAX_RETRY  → reset to 'pending' (auto-retries next render_tick)
      - retry_count >= MAX_RETRY → mark as 'failed' (shows Retry button on portal)
    """
    db = Session()
    try:
        cutoff = _utcnow() - timedelta(minutes=RENDER_TIMEOUT_MINUTES)

        stuck_jobs = (
            db.query(ReelJob)
            .filter(
                ReelJob.status     == JobStatus.rendering,
                ReelJob.updated_at <= cutoff,
            )
            .all()
        )

        if not stuck_jobs:
            return

        log.warning(f"[watchdog] Found {len(stuck_jobs)} stuck job(s) — resetting.")

        for job in stuck_jobs:
            minutes_stuck = int((_utcnow() - job.updated_at).total_seconds() / 60)
            log.warning(
                f"[watchdog] Job #{job.id} '{job.reel_name}' stuck for "
                f"~{minutes_stuck}m (retry_count={job.retry_count})"
            )

            job.retry_count += 1

            if job.retry_count >= MAX_RETRY:
                # Exhausted retries — mark failed, show Retry button on portal
                job.status    = JobStatus.failed
                job.error_msg = (
                    f"Render timeout — job was stuck in rendering for over "
                    f"{minutes_stuck} minutes and has exhausted {MAX_RETRY} retries. "
                    f"Click Retry to reprocess manually."
                )
                log.warning(
                    f"[watchdog] Job #{job.id} → failed "
                    f"(retry_count={job.retry_count} >= MAX_RETRY={MAX_RETRY})"
                )
            else:
                # Still has retries left — reset to pending for auto-retry
                job.status    = JobStatus.pending
                job.error_msg = (
                    f"Render timeout — was stuck for ~{minutes_stuck}m. "
                    f"Auto-retrying (attempt {job.retry_count} of {MAX_RETRY})."
                )
                log.warning(
                    f"[watchdog] Job #{job.id} → pending for auto-retry "
                    f"(attempt {job.retry_count} of {MAX_RETRY})"
                )

            job.updated_at = _utcnow()

        db.commit()
        log.info(f"[watchdog] Reset {len(stuck_jobs)} stuck job(s).")

    except Exception as e:
        log.error(f"[watchdog] watchdog_tick error: {e}")
        db.rollback()
    finally:
        db.close()


# ── Stats refresh tick ───────────────────────────────────────

def stats_tick():
    """
    Fetch up-to-date view / like / comment counts for every 'done' job
    that has a yt_video_id.  Runs every 6 hours.
    YouTube Data API v3 quota cost: 1 unit per videos.list call.
    """
    db = Session()
    try:
        jobs = (
            db.query(ReelJob)
            .filter(
                ReelJob.status      == JobStatus.done,
                ReelJob.yt_video_id != None,
            )
            .all()
        )
    except Exception as e:
        log.error(f"[scheduler] stats_tick DB error: {e}")
        db.close()
        return

    for job in jobs:
        try:
            stats = fetch_video_stats(job.yt_video_id)
            job.views      = stats["viewCount"]
            job.updated_at = _utcnow()
            log.info(
                f"[scheduler] stats_tick job #{job.id} '{job.reel_name}' "
                f"→ {stats['viewCount']} views"
            )
        except Exception as e:
            log.warning(f"[scheduler] stats_tick failed for job #{job.id}: {e}")

    try:
        db.commit()
    except Exception as e:
        log.error(f"[scheduler] stats_tick commit error: {e}")
        db.rollback()
    finally:
        db.close()


# ── Cleanup tick ─────────────────────────────────────────

# How many recently-uploaded reels to keep on disk (configurable via env var)
_KEEP_RECENT = int(os.environ.get("CLEANUP_KEEP_RECENT", "5"))


def cleanup_tick():
    """
    Delete rendered output video files for old 'done' jobs to reclaim disk space.

    Rules
    ─────
    • Only jobs with status == 'done' are eligible.
    • The N most-recent done jobs (by updated_at DESC) are always kept on disk.
    • For everything older: the local file at job.output_path is deleted, and
      job.output_path is set to None in the DB so the portal doesn't show a
      broken path.
    • The DB row itself is NEVER deleted — yt_video_id, views, category, etc.
      remain fully visible in the portal.
    • Jobs in any other status (pending, rendering, rendered, uploading, failed)
      are completely untouched.
    """
    db = Session()
    try:
        done_jobs = (
            db.query(ReelJob)
            .filter(
                ReelJob.status      == JobStatus.done,
                ReelJob.output_path != None,   # only rows that still have a file path
            )
            .order_by(ReelJob.updated_at.desc())   # newest first
            .all()
        )
    except Exception as e:
        log.error(f"[scheduler] cleanup_tick DB error: {e}")
        db.close()
        return

    # Skip the N most-recent; the rest are candidates for file deletion
    candidates = done_jobs[_KEEP_RECENT:]

    if not candidates:
        log.info(f"[scheduler] cleanup_tick — nothing to clean (≤{_KEEP_RECENT} done jobs on disk)")
        db.close()
        return

    deleted_count = 0
    freed_bytes   = 0

    for job in candidates:
        path = job.output_path
        try:
            if path and os.path.isfile(path):
                size = os.path.getsize(path)
                os.remove(path)
                freed_bytes   += size
                deleted_count += 1
                log.info(
                    f"[scheduler] cleanup_tick — deleted '{path}' "
                    f"({size / 1_048_576:.1f} MB) for job #{job.id} '{job.reel_name}'"
                )
            # Clear the path in DB regardless (file may have already been gone)
            job.output_path = None
            job.updated_at  = _utcnow()
        except Exception as e:
            log.warning(f"[scheduler] cleanup_tick failed for job #{job.id}: {e}")

    try:
        db.commit()
        log.info(
            f"[scheduler] cleanup_tick complete — "
            f"{deleted_count} file(s) removed, "
            f"{freed_bytes / 1_048_576:.1f} MB freed"
        )
    except Exception as e:
        log.error(f"[scheduler] cleanup_tick commit error: {e}")
        db.rollback()
    finally:
        db.close()


# ── Scheduler lifecycle ───────────────────────────────────

_scheduler = BackgroundScheduler(timezone="UTC")

def start_scheduler():
    _scheduler.add_job(render_tick,   "interval", seconds=60,
                       id="render_tick",   replace_existing=True)
    _scheduler.add_job(upload_tick,   "interval", seconds=60,
                       id="upload_tick",   replace_existing=True)
    _scheduler.add_job(watchdog_tick, "interval", minutes=5,
                       id="watchdog_tick", replace_existing=True)
    _scheduler.add_job(stats_tick,    "interval", hours=6,
                       id="stats_tick",    replace_existing=True)
    _scheduler.add_job(cleanup_tick,  "interval", hours=24,
                       id="cleanup_tick",  replace_existing=True)
    _scheduler.start()
    log.info(
        f"[scheduler] Started — render+upload every 60s | "
        f"watchdog every 5m (timeout={RENDER_TIMEOUT_MINUTES}m, max_retry={MAX_RETRY}) | "
        f"stats every 6h | cleanup every 24h (keep {_KEEP_RECENT} recent)"
    )


def stop_scheduler():
    _scheduler.shutdown(wait=False)
    log.info("[scheduler] Stopped")