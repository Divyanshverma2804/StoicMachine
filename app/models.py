"""
models.py — SQLAlchemy models + DB init
"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Text, DateTime, Enum as SAEnum
)
from sqlalchemy.orm import declarative_base, sessionmaker
import enum, os, logging

DB_PATH = os.environ.get("DB_PATH", "data/reelforge.db")
engine  = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base    = declarative_base()


class JobStatus(str, enum.Enum):
    pending   = "pending"
    rendering = "rendering"
    rendered  = "rendered"
    uploading = "uploading"
    done      = "done"
    failed    = "failed"


class ReelJob(Base):
    __tablename__ = "reel_jobs"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    batch_id      = Column(String(64), nullable=False, index=True)
    reel_name     = Column(String(256), nullable=False)
    script        = Column(Text, nullable=False)
    sections_json = Column(Text, nullable=True)   # JSON string of sections dict

    status        = Column(SAEnum(JobStatus), default=JobStatus.pending, nullable=False)
    upload_time   = Column(DateTime, nullable=True)   # scheduled YT upload time
    output_path   = Column(String(512), nullable=True)

    yt_video_id   = Column(String(64), nullable=True)
    error_msg     = Column(Text, nullable=True)
    retry_count   = Column(Integer, default=0)

    category      = Column(String(64), nullable=True, default="uncategorized")
    views         = Column(Integer, nullable=True, default=0)
    privacy       = Column(String(16), nullable=True, default=None)  # None = use YT_PRIVACY env

    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def as_dict(self):
        return {
            "id":           self.id,
            "batch_id":     self.batch_id,
            "reel_name":    self.reel_name,
            "status":       self.status.value,   # emit plain string e.g. 'rendered', not 'JobStatus.rendered'
            "upload_time":  self.upload_time.isoformat() if self.upload_time else None,
            "output_path":  self.output_path,
            "yt_video_id":  self.yt_video_id,
            "error_msg":    self.error_msg,
            "retry_count":  self.retry_count,
            "category":     self.category or "uncategorized",
            "views":        self.views or 0,
            "privacy":      self.privacy or None,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
        }


class ReelDraft(Base):
    """Reel Diary — stores scripts as persistent notes (drafts or auto-saved posted reels)."""
    __tablename__ = "diary_drafts"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    title       = Column(String(256), nullable=False)           # reel name / user-given title
    content     = Column(Text, nullable=False)                  # the full content.md script text
    source      = Column(String(16), default="draft")           # "draft" | "posted"
    reel_job_id = Column(Integer, nullable=True)                # links to ReelJob.id if source=posted
    tag         = Column(String(64), nullable=True)             # optional colour tag / category

    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def as_dict(self):
        return {
            "id":          self.id,
            "title":       self.title,
            "content":     self.content,
            "source":      self.source,
            "reel_job_id": self.reel_job_id,
            "tag":         self.tag,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
            "updated_at":  self.updated_at.isoformat() if self.updated_at else None,
        }


def init_db():
    Base.metadata.create_all(engine)
    # Safe migration: add new columns to existing databases that lack them
    _log = logging.getLogger("models")
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            result    = conn.execute(text("PRAGMA table_info(reel_jobs)"))
            col_names = [row[1] for row in result]
            for col_def in [
                ("category", "VARCHAR(64) DEFAULT 'uncategorized'"),
                ("views",    "INTEGER DEFAULT 0"),
                ("privacy",  "VARCHAR(16) DEFAULT NULL"),
            ]:
                col_name, col_spec = col_def
                if col_name not in col_names:
                    conn.execute(
                        text(f"ALTER TABLE reel_jobs ADD COLUMN {col_name} {col_spec}")
                    )
                    conn.commit()
                    _log.info(f"Migration: added '{col_name}' column to reel_jobs")
    except Exception as exc:
        _log.warning(f"Column migration skipped: {exc}")
